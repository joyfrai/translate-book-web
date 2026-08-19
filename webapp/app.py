from __future__ import annotations

import html
import os
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from .translate_job import (
    DEFAULT_SOURCE_CODE,
    DEFAULT_SOURCE_LANGUAGE,
    DEFAULT_TARGET_CODE,
    DEFAULT_TARGET_LANGUAGE,
    SOURCE_LANGUAGES,
    SUPPORTED_LANGUAGES,
    run_translation,
)
from .security import UploadSecurityError, VirusTotalError, VirusTotalScanner, validate_payload


MAX_UPLOAD_BYTES = 30 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".epub"}
BASE_PATH = os.getenv("TRANSLATE_BOOK_BASE_PATH", "").rstrip("/")
STATUS_LABELS = {
    "queued": "В очереди",
    "processing": "Обрабатывается",
    "done": "Готово",
    "failed": "Ошибка",
}


def app_url(path: str = "/") -> str:
    if path == "/":
        return f"{BASE_PATH}/" if BASE_PATH else "/"
    return f"{BASE_PATH}{path}" if BASE_PATH else path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def attachment_header(filename: str) -> str:
    ascii_name = "".join(character if character.isascii() and (character.isalnum() or character in "._-") else "_" for character in filename)
    ascii_name = ascii_name.strip("._") or "download"
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename, safe="")}'


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.jobs_dir = data_dir / "jobs"
        self.db_path = data_dir / "jobs.sqlite3"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    original_name TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    result_path TEXT,
                    size_bytes INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    target_code TEXT NOT NULL DEFAULT 'ru',
                    target_language TEXT NOT NULL DEFAULT 'Русский',
                    source_code TEXT NOT NULL DEFAULT 'en',
                    source_language TEXT NOT NULL DEFAULT 'English'
                )
                """
            )
            columns = {row["name"] for row in db.execute("PRAGMA table_info(jobs)")}
            if "target_code" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN target_code TEXT NOT NULL DEFAULT 'ru'")
            if "target_language" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN target_language TEXT NOT NULL DEFAULT 'Русский'")
            if "source_code" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN source_code TEXT NOT NULL DEFAULT 'en'")
            if "source_language" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN source_language TEXT NOT NULL DEFAULT 'English'")
            db.execute(
                "UPDATE jobs SET status='queued', updated_at=? WHERE status='processing'",
                (utc_now(),),
            )

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def add(
        self,
        job_id: str,
        original_name: str,
        source_path: Path,
        size_bytes: int,
        source_code: str = DEFAULT_SOURCE_CODE,
        source_language: str = DEFAULT_SOURCE_LANGUAGE,
        target_code: str = DEFAULT_TARGET_CODE,
        target_language: str = DEFAULT_TARGET_LANGUAGE,
    ) -> None:
        now = utc_now()
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO jobs(
                    id, original_name, source_path, size_bytes, status,
                    created_at, updated_at, source_code, source_language,
                    target_code, target_language
                )
                VALUES(?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    original_name,
                    str(source_path),
                    size_bytes,
                    now,
                    now,
                    source_code,
                    source_language,
                    target_code,
                    target_language,
                ),
            )

    def progress(self, job: sqlite3.Row) -> tuple[int, int]:
        temp_dir = self.jobs_dir / job["id"] / "work" / f"{Path(job['source_path']).stem}_temp"
        if not temp_dir.is_dir():
            return (0, 0)
        total = len(list(temp_dir.glob("chunk*.md")))
        completed = sum(
            1
            for output in temp_dir.glob("output_chunk*.md")
            if output.is_file() and output.read_text(encoding="utf-8", errors="ignore").strip()
        )
        return (min(completed, total), total)

    def list(self) -> list[sqlite3.Row]:
        with self.connect() as db:
            return db.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()

    def list_finished(self) -> list[sqlite3.Row]:
        with self.connect() as db:
            return db.execute(
                "SELECT * FROM jobs WHERE status='done' AND result_path IS NOT NULL ORDER BY created_at DESC"
            ).fetchall()

    def get(self, job_id: str) -> sqlite3.Row | None:
        with self.connect() as db:
            return db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()

    def claim(self) -> sqlite3.Row | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                db.commit()
                return None
            db.execute(
                "UPDATE jobs SET status='processing', updated_at=?, error=NULL WHERE id=?",
                (utc_now(), row["id"]),
            )
            db.commit()
            return self.get(row["id"])

    def finish(self, job_id: str, result_path: Path) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET status='done', result_path=?, updated_at=? WHERE id=?",
                (str(result_path), utc_now(), job_id),
            )

    def fail(self, job_id: str, error: str) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET status='failed', error=?, updated_at=? WHERE id=?",
                (error[-4000:], utc_now(), job_id),
            )


class Worker(threading.Thread):
    def __init__(self, store: Store, repo_root: Path):
        super().__init__(name="translate-book-worker", daemon=True)
        self.store = store
        self.repo_root = repo_root
        self.stop_event = threading.Event()

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        while not self.stop_event.is_set():
            job = self.store.claim()
            if job is None:
                self.stop_event.wait(1)
                continue
            try:
                result_path = run_translation(
                    repo_root=self.repo_root,
                    job_dir=self.store.jobs_dir / job["id"],
                    source_path=Path(job["source_path"]),
                    source_code=job["source_code"],
                    source_language=job["source_language"],
                    target_code=job["target_code"],
                    target_language=job["target_language"],
                )
                self.store.finish(job["id"], result_path)
            except Exception as exc:  # keep the durable queue alive
                self.store.fail(job["id"], str(exc))


class App:
    def __init__(
        self,
        repo_root: Path,
        data_dir: Path,
        scanner: VirusTotalScanner | None = None,
    ):
        self.repo_root = repo_root
        self.store = Store(data_dir)
        self.scanner = scanner
        self.worker = Worker(self.store, repo_root)


SITE_STYLES = """<style>
:root {
  color-scheme: light;
  --bg: #f5f7fb;
  --surface: #ffffff;
  --surface-soft: #f8f9fc;
  --ink: #172033;
  --muted: #687386;
  --faint: #96a0b2;
  --line: #e4e8f0;
  --brand: #4658d8;
  --brand-strong: #3446c4;
  --brand-soft: #eef0ff;
  --success: #087f67;
  --success-soft: #e8f7f1;
  --warning: #9a6410;
  --warning-soft: #fff5dc;
  --danger: #b54646;
  --danger-soft: #fff0f0;
  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-lg: 24px;
  --shadow-sm: 0 8px 24px rgba(35, 47, 76, .06);
  --shadow-md: 0 18px 55px rgba(35, 47, 76, .10);
  --max-width: 1080px;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* { box-sizing: border-box; }
html { min-width: 320px; background: var(--bg); }
body {
  min-width: 320px;
  margin: 0;
  color: var(--ink);
  background:
    radial-gradient(circle at 85% 0%, rgba(70, 88, 216, .09), transparent 28rem),
    var(--bg);
  font-size: 15px;
  line-height: 1.55;
}
a { color: inherit; }
button, input, select { font: inherit; }
:focus-visible { outline: 3px solid rgba(70, 88, 216, .34); outline-offset: 3px; }
.site-shell { width: min(100% - 40px, var(--max-width)); margin: 0 auto; }
.site-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 26px 0 22px;
}
.brand { display: inline-flex; align-items: center; gap: 11px; text-decoration: none; }
.brand-mark {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border-radius: 12px;
  color: #fff;
  background: var(--brand);
  box-shadow: 0 8px 18px rgba(70, 88, 216, .23);
  font-size: 20px;
  font-weight: 700;
}
.brand-copy { display: grid; gap: 0; line-height: 1.15; }
.brand-copy strong { font-size: 15px; letter-spacing: -.02em; }
.brand-copy small { margin: 4px 0 0; color: var(--muted); font-size: 11px; }
.site-nav { display: flex; align-items: center; gap: 5px; }
.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 9px 12px;
  border-radius: 10px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 650;
  text-decoration: none;
}
.nav-link:hover, .nav-link.active { color: var(--brand-strong); background: var(--brand-soft); }
.nav-count { min-width: 20px; padding: 1px 6px; border-radius: 999px; color: var(--brand-strong); background: #dfe3ff; font-size: 11px; text-align: center; }
.hero { max-width: 760px; padding: 58px 0 34px; }
.eyebrow { display: inline-flex; align-items: center; gap: 8px; color: var(--brand-strong); font-size: 11px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
.eyebrow::before { width: 22px; height: 2px; border-radius: 99px; background: var(--brand); content: ""; }
h1, h2, h3, p { margin-top: 0; }
h1, h2 { font-family: Georgia, "Times New Roman", serif; letter-spacing: -.04em; }
h1 { max-width: 700px; margin: 15px 0 14px; font-size: clamp(38px, 6vw, 66px); line-height: 1.02; }
h2 { margin-bottom: 6px; font-size: clamp(24px, 3vw, 32px); line-height: 1.1; }
.lede { max-width: 620px; margin-bottom: 21px; color: var(--muted); font-size: 17px; }
.hero-note { display: inline-flex; align-items: center; gap: 9px; color: var(--muted); font-size: 12px; }
.hero-note-icon { display: grid; width: 22px; height: 22px; place-items: center; border-radius: 50%; color: var(--success); background: var(--success-soft); font-size: 13px; font-weight: 800; }
.process-strip { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 0 0 23px; }
.process-step { padding: 12px 14px; border: 1px solid var(--line); border-radius: 12px; background: rgba(255, 255, 255, .62); }
.process-step strong { display: block; color: var(--brand-strong); font-size: 11px; letter-spacing: .02em; }
.process-step span { display: block; margin-top: 3px; color: var(--muted); font-size: 11px; }
.panel { border: 1px solid var(--line); border-radius: var(--radius-lg); background: rgba(255, 255, 255, .92); box-shadow: var(--shadow-md); }
.upload-panel { padding: clamp(22px, 4vw, 38px); }
.panel-heading { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 28px; }
.panel-icon { display: grid; flex: 0 0 auto; width: 42px; height: 42px; place-items: center; border-radius: 13px; color: var(--brand-strong); background: var(--brand-soft); font-size: 20px; }
.panel-heading p { margin: 0; color: var(--muted); font-size: 13px; }
.upload-form { display: grid; gap: 22px; }
.field-label { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 8px; color: var(--ink); font-size: 13px; font-weight: 750; }
.field-hint { color: var(--faint); font-size: 11px; font-weight: 550; }
.file-input { position: absolute; width: 1px; height: 1px; overflow: hidden; opacity: 0; }
.file-drop {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 84px;
  padding: 16px 18px;
  border: 1px dashed #b9c2d5;
  border-radius: var(--radius-md);
  color: var(--muted);
  background: var(--surface-soft);
  cursor: pointer;
  transition: border-color .18s ease, background .18s ease, transform .18s ease;
}
.file-drop:hover { border-color: var(--brand); background: #f5f6ff; transform: translateY(-1px); }
.file-input:focus-visible + .file-drop { outline: 3px solid rgba(70, 88, 216, .34); outline-offset: 3px; }
.file-drop.has-file { border-color: var(--brand); background: var(--brand-soft); }
.file-icon { display: grid; flex: 0 0 auto; width: 40px; height: 40px; place-items: center; border-radius: 11px; color: var(--brand-strong); background: #e4e7ff; font-size: 18px; }
.file-copy { display: grid; gap: 2px; }
.file-copy strong { color: var(--ink); font-size: 13px; }
.file-copy span { font-size: 12px; }
.file-limit { margin-left: auto; color: var(--faint); font-size: 11px; white-space: nowrap; }
.file-feedback { min-height: 18px; margin: 7px 0 0; color: var(--muted); font-size: 11px; }
.file-feedback.is-error { color: var(--danger); }
.language-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.select-wrap { position: relative; }
.select-wrap::after { position: absolute; top: 50%; right: 14px; color: var(--muted); content: "⌄"; pointer-events: none; transform: translateY(-55%); }
select { width: 100%; appearance: none; padding: 12px 38px 12px 13px; border: 1px solid var(--line); border-radius: var(--radius-sm); color: var(--ink); background: var(--surface); }
select:hover { border-color: #bcc5d7; }
.form-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-top: 2px; }
.security-note { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 11px; }
.security-note strong { color: var(--success); font-size: 14px; }
.button { display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: 44px; padding: 11px 17px; border: 0; border-radius: 11px; font-size: 13px; font-weight: 750; text-decoration: none; cursor: pointer; transition: background .18s ease, box-shadow .18s ease, transform .18s ease; }
.button:hover { transform: translateY(-1px); }
.button-primary { color: #fff; background: var(--brand); box-shadow: 0 9px 20px rgba(70, 88, 216, .23); }
.button-primary:hover { background: var(--brand-strong); box-shadow: 0 12px 25px rgba(70, 88, 216, .28); }
.button-secondary { color: var(--brand-strong); background: var(--brand-soft); }
.button-secondary:hover { background: #e2e6ff; }
.section { padding: 62px 0 80px; }
.section-head { display: flex; align-items: end; justify-content: space-between; gap: 18px; margin-bottom: 16px; }
.section-head p { margin: 0; color: var(--muted); font-size: 13px; }
.text-link { color: var(--brand-strong); font-size: 12px; font-weight: 750; text-decoration: none; }
.text-link:hover { text-decoration: underline; }
.job-list { overflow: hidden; padding: 0 22px; }
.job { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px 24px; padding: 20px 0; border-bottom: 1px solid var(--line); }
.job:last-child { border-bottom: 0; }
.job-main { min-width: 0; }
.job-title { display: flex; align-items: center; gap: 9px; min-width: 0; }
.job-title strong { overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.status { display: inline-flex; flex: 0 0 auto; align-items: center; padding: 4px 8px; border-radius: 999px; font-size: 10px; font-weight: 800; letter-spacing: .03em; text-transform: uppercase; }
.status-queued { color: var(--warning); background: var(--warning-soft); }
.status-processing { color: #7353a7; background: #f2ecff; }
.status-done { color: var(--success); background: var(--success-soft); }
.status-failed { color: var(--danger); background: var(--danger-soft); }
.job-meta { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 5px; color: var(--muted); font-size: 11px; }
.progress-wrap { display: flex; align-items: center; gap: 10px; max-width: 350px; margin-top: 12px; }
.progress-track { flex: 1; height: 6px; overflow: hidden; border-radius: 99px; background: #edf0f5; }
.progress-track span { display: block; width: var(--progress); height: 100%; border-radius: inherit; background: var(--brand); }
.progress-label { color: var(--muted); font-size: 10px; white-space: nowrap; }
.job-actions { display: flex; align-items: center; justify-content: flex-end; }
.error { grid-column: 1 / -1; padding: 10px 12px; border-radius: 9px; color: var(--danger); background: var(--danger-soft); font-size: 12px; white-space: pre-wrap; }
.notice { margin-bottom: 20px; padding: 12px 15px; border: 1px solid #f1ddb1; border-radius: 12px; color: var(--warning); background: var(--warning-soft); font-size: 13px; }
.empty { padding: 30px 0; color: var(--muted); text-align: center; }
.library-hero { padding-bottom: 26px; }
.library-hero h1 { max-width: 760px; }
.library-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.book-card { display: grid; grid-template-columns: 92px minmax(0, 1fr); gap: 18px; padding: 18px; border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--surface); box-shadow: var(--shadow-sm); }
.book-cover { display: flex; flex-direction: column; justify-content: space-between; min-height: 132px; padding: 13px; border-radius: 11px; color: #fff; background: linear-gradient(155deg, #5d6be0, #3446bd); box-shadow: inset 0 0 0 1px rgba(255,255,255,.16); }
.book-cover span:first-child { font-family: Georgia, serif; font-size: 26px; font-weight: 700; letter-spacing: -.08em; }
.book-cover span:last-child { color: rgba(255,255,255,.75); font-size: 9px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }
.book-card-body { display: flex; min-width: 0; flex-direction: column; align-items: flex-start; }
.book-card-meta { display: flex; flex-wrap: wrap; gap: 7px; color: var(--faint); font-size: 10px; }
.book-card-meta strong { color: var(--brand-strong); font-weight: 800; }
.book-card h2 { width: 100%; overflow: hidden; margin: 11px 0 7px; font-family: inherit; font-size: 15px; font-weight: 750; letter-spacing: -.02em; text-overflow: ellipsis; white-space: nowrap; }
.book-card p { margin-bottom: 14px; color: var(--muted); font-size: 11px; }
.book-card .button { margin-top: auto; min-height: 37px; padding: 9px 12px; font-size: 11px; }
.book-downloads { display: flex; flex-wrap: wrap; gap: 8px; margin-top: auto; }
.book-downloads .button { margin-top: 0; }
.site-footer { padding: 0 0 30px; color: var(--faint); font-size: 11px; }
@media (max-width: 740px) {
  .site-shell { width: min(100% - 28px, var(--max-width)); }
  .site-header { align-items: flex-start; padding-top: 18px; }
  .site-nav { gap: 0; }
  .nav-link { padding: 8px 7px; font-size: 11px; }
  .hero { padding: 42px 0 25px; }
  h1 { font-size: clamp(38px, 12vw, 54px); }
  .lede { font-size: 15px; }
  .process-strip, .language-grid, .library-grid { grid-template-columns: 1fr; }
  .process-step { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
  .form-actions { align-items: stretch; flex-direction: column; }
  .form-actions .button { width: 100%; }
  .security-note { justify-content: center; order: 2; }
  .job { grid-template-columns: 1fr; }
  .job-actions { justify-content: flex-start; }
  .job-actions .button { width: 100%; }
  .section { padding-top: 44px; }
}
@media print {
  body { background: #fff; }
  .site-header, .upload-panel, .text-link, .button { display: none; }
  .site-shell { width: 100%; }
  .panel, .book-card { box-shadow: none; }
}
</style>"""


def site_header(active: str, library_count: int) -> str:
    upload_class = "nav-link active" if active == "upload" else "nav-link"
    library_class = "nav-link active" if active == "library" else "nav-link"
    return f"""<header class="site-header">
  <a class="brand" href="{app_url('/')}" aria-label="Translate Book — загрузка">
    <span class="brand-mark" aria-hidden="true">↗</span>
    <span class="brand-copy"><strong>Translate Book</strong><small>Перевод книг</small></span>
  </a>
  <nav class="site-nav" aria-label="Основная навигация">
    <a class="{upload_class}" href="{app_url('/')}">Загрузить</a>
    <a class="{library_class}" href="{app_url('/library')}">Библиотека <span class="nav-count">{library_count}</span></a>
  </nav>
</header>"""


def site_footer() -> str:
    return "<footer class=\"site-footer\">Translate Book · Светлая версия каталога</footer>"


def job_markup(app: App, job: sqlite3.Row) -> str:
    status = job["status"]
    completed, total = app.store.progress(job)
    if total:
        progress_label = f"{completed / total * 100:.1f}% ({completed}/{total})"
        progress_value = min(completed / total * 100, 100)
    elif status == "done":
        progress_label, progress_value = "100%", 100
    elif status == "queued":
        progress_label, progress_value = "Ожидает", 0
    else:
        progress_label, progress_value = "Подготовка", 0
    result = ""
    if status == "done" and job["result_path"] and Path(job["result_path"]).is_file():
        result = f'<a class="button button-secondary" href="{app_url(f"/download/{job["id"]}")}">Скачать ZIP <span aria-hidden="true">↗</span></a>'
    error = f'<div class="error">{html.escape(job["error"])}</div>' if job["error"] else ""
    return f"""<li class="job">
  <div class="job-main">
    <div class="job-title"><strong title="{html.escape(job["original_name"])}">{html.escape(job["original_name"])}</strong><span class="status status-{html.escape(status)}">{html.escape(STATUS_LABELS.get(status, status))}</span></div>
    <div class="job-meta"><span>{job["size_bytes"] / 1024 / 1024:.1f} MB</span><span>{html.escape(job["source_language"])} → {html.escape(job["target_language"])}</span><span>{job["created_at"].replace("T", " ").replace("+00:00", " UTC")}</span></div>
    <div class="progress-wrap"><div class="progress-track" role="progressbar" aria-label="Прогресс перевода" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{progress_value:.0f}"><span style="--progress: {progress_value:.1f}%"></span></div><span class="progress-label">{progress_label}</span></div>
  </div>
  <div class="job-actions">{result}</div>
  {error}
</li>"""


def page(app: App, message: str = "") -> bytes:
    jobs = "".join(job_markup(app, job) for job in app.store.list()) or '<li class="empty">Файлов пока нет.</li>'
    notice = f'<div class="notice" role="status">{html.escape(message)}</div>' if message else ""
    source_options = "".join(
        f'<option value="{code}"{" selected" if code == DEFAULT_SOURCE_CODE else ""}>{html.escape(name)}</option>'
        for code, name in SOURCE_LANGUAGES.items()
    )
    language_options = "".join(
        f'<option value="{code}"{" selected" if code == DEFAULT_TARGET_CODE else ""}>{html.escape(name)}</option>'
        for code, name in SUPPORTED_LANGUAGES.items()
    )
    library_count = len(app.store.list_finished())
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#f5f7fb">
<title>Translate Book — перевод книг</title>{SITE_STYLES}</head><body>
<div class="site-shell">{site_header("upload", library_count)}
<main>
  <section class="hero">
    <span class="eyebrow">Перевод книг</span>
    <h1>Из исходника —<br>в новую библиотеку.</h1>
    <p class="lede">Загрузите книгу, выберите языки и получите готовый перевод в удобном ZIP-архиве.</p>
    <div class="hero-note"><span class="hero-note-icon" aria-hidden="true">✓</span>Каждый файл проходит проверку перед обработкой</div>
  </section>
  <section class="process-strip" aria-label="Как работает перевод">
    <div class="process-step"><strong>01 · Файл</strong><span>PDF, DOCX или EPUB</span></div>
    <div class="process-step"><strong>02 · Языки</strong><span>Источник и перевод</span></div>
    <div class="process-step"><strong>03 · Результат</strong><span>ZIP с готовой книгой</span></div>
  </section>
  {notice}
  <section class="panel upload-panel" aria-labelledby="upload-title">
    <div class="panel-heading"><span class="panel-icon" aria-hidden="true">＋</span><div><h2 id="upload-title">Новая книга</h2><p>Поддерживаются PDF, DOCX и EPUB до 30 MB.</p></div></div>
    <form class="upload-form" action="{app_url('/upload')}" method="post" enctype="multipart/form-data">
      <div class="field"><div class="field-label"><span>Файл книги</span><span class="field-hint">до 30 MB</span></div><input class="file-input" id="book" name="book" type="file" accept=".pdf,.docx,.epub" aria-describedby="file-feedback" required><label class="file-drop" id="file-drop" for="book"><span class="file-icon" aria-hidden="true">▤</span><span class="file-copy"><strong id="file-name">Выберите файл с устройства</strong><span id="file-meta">PDF, DOCX или EPUB</span></span><span class="file-limit">Обзор</span></label><p class="file-feedback" id="file-feedback" role="status" aria-live="polite">Файл появится здесь после выбора.</p></div>
      <div class="language-grid"><div><label class="field-label" for="source_language"><span>Язык оригинала</span></label><div class="select-wrap"><select id="source_language" name="source_language">{source_options}</select></div></div><div><label class="field-label" for="target_language"><span>Язык перевода</span></label><div class="select-wrap"><select id="target_language" name="target_language">{language_options}</select></div></div></div>
      <div class="form-actions"><div class="security-note"><strong aria-hidden="true">✓</strong><span>Проверка VirusTotal и защита от архивных угроз</span></div><button class="button button-primary" type="submit">Начать перевод <span aria-hidden="true">→</span></button></div>
    </form>
  </section>
  <section class="section" aria-labelledby="jobs-title">
    <div class="section-head"><div><h2 id="jobs-title">Последние задачи</h2><p>Статус обновится после перезагрузки страницы.</p></div><a class="text-link" href="{app_url('/')}">Обновить список ↻</a></div>
    <ul class="panel job-list">{jobs}</ul>
  </section>
</main>{site_footer()}</div>
<script>
  const bookInput = document.getElementById("book");
  if (bookInput) {{
    bookInput.addEventListener("change", () => {{
      const file = bookInput.files[0];
      if (!file) return;
      const fileDrop = document.getElementById("file-drop");
      const fileName = document.getElementById("file-name");
      const fileMeta = document.getElementById("file-meta");
      const feedback = document.getElementById("file-feedback");
      const sizeMb = file.size / (1024 * 1024);
      fileName.textContent = file.name;
      fileMeta.textContent = `${{sizeMb.toFixed(1)}} MB · файл выбран`;
      feedback.textContent = sizeMb <= 30 ? "Файл подходит по размеру. Можно запускать перевод." : "Файл больше лимита 30 MB.";
      feedback.classList.toggle("is-error", sizeMb > 30);
      fileDrop.classList.add("has-file");
    }});
  }}
</script>
</body></html>""".encode("utf-8")


def library_page(app: App) -> bytes:
    finished = []
    for job in app.store.list_finished():
        result_path = Path(job["result_path"])
        if result_path.is_file():
            finished.append(job)
    if finished:
        cards = []
        for job in finished:
            title = html.escape(job["original_name"])
            initials = html.escape("".join(part[0] for part in Path(job["original_name"]).stem.split()[:2]).upper() or "TB")
            job_id = html.escape(job["id"])
            source_language = html.escape(job["source_language"])
            target_language = html.escape(job["target_language"])
            cards.append(
                f"""<article class="book-card">
  <div class="book-cover" aria-hidden="true"><span>{initials}</span><span>Перевод</span></div>
  <div class="book-card-body"><div class="book-card-meta"><strong>{target_language}</strong><span>{job["created_at"].replace("T", " ").replace("+00:00", " UTC")}</span></div><h2 title="{title}">{title}</h2><p>{source_language} → {target_language} · готовый ZIP-архив</p><div class="book-downloads"><a class="button button-secondary" href="{app_url(f"/download/{job_id}/original")}">Скачать оригинал · {source_language} <span aria-hidden="true">↗</span></a><a class="button button-primary" href="{app_url(f"/download/{job_id}/translated")}">Скачать перевод · {target_language} <span aria-hidden="true">↗</span></a></div></div>
</article>"""
            )
        books = "".join(cards)
    else:
        books = '<div class="panel empty">Переведённых книг пока нет.</div>'
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#f5f7fb">
<title>Библиотека — Translate Book</title>{SITE_STYLES}</head><body>
<div class="site-shell">{site_header("library", len(finished))}
<main>
  <section class="hero library-hero"><span class="eyebrow">Публичный каталог</span><h1>Книги, которые<br>уже готовы.</h1><p class="lede">Здесь собраны переводы, доступные для скачивания. Без поиска и лишнего шума — только библиотека.</p></section>
  <section class="section" aria-labelledby="library-title"><div class="section-head"><div><h2 id="library-title">Все переводы</h2><p>{len(finished)} {"книга" if len(finished) == 1 else "книг"} в каталоге</p></div><a class="text-link" href="{app_url('/')}">Загрузить книгу →</a></div><div class="library-grid">{books}</div></section>
</main>{site_footer()}</div>
</body></html>""".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server: "WebServer"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)

    def send_bytes(self, body: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        if path == "/library":
            self.send_bytes(library_page(self.server.app), "text/html; charset=utf-8")
            return
        if path.startswith("/download/"):
            download_parts = path.removeprefix("/download/").split("/")
            job_id = unquote(download_parts[0])
            download_kind = download_parts[1] if len(download_parts) == 2 else "translated"
            if download_kind not in {"original", "translated"}:
                self.send_bytes(b"Not found", "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)
                return
            job = self.server.app.store.get(job_id)
            file_field = "source_path" if download_kind == "original" else "result_path"
            if not job or job["status"] != "done" or not job[file_field]:
                self.send_bytes(b"Not found", "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)
                return
            download_path = Path(job[file_field])
            jobs_root = self.server.app.store.jobs_dir.resolve()
            try:
                safe_download = download_path.resolve().is_relative_to(jobs_root)
            except OSError:
                safe_download = False
            if not safe_download or not download_path.is_file():
                self.send_bytes(b"Not found", "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)
                return
            if download_kind == "original":
                content_type = {
                    ".epub": "application/epub+zip",
                    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".pdf": "application/pdf",
                }.get(download_path.suffix.lower(), "application/octet-stream")
                filename = Path(job["original_name"]).name
            else:
                content_type = "application/zip"
                filename = "translated-book.zip"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", attachment_header(filename))
            self.send_header("Content-Length", str(download_path.stat().st_size))
            self.end_headers()
            with download_path.open("rb") as source:
                shutil.copyfileobj(source, self.wfile)
            return
        if path == "/":
            self.send_bytes(page(self.server.app), "text/html; charset=utf-8")
            return
        self.send_bytes(b"Not found", "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/upload":
            self.send_bytes(b"Not found", "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            self.send_bytes(b"Invalid Content-Length", "text/plain; charset=utf-8", HTTPStatus.BAD_REQUEST)
            return
        if content_length < 0 or content_length > MAX_UPLOAD_BYTES + 1024 * 1024:
            self.send_bytes(b"File is too large", "text/plain; charset=utf-8", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data"):
            self.send_bytes(b"Expected multipart upload", "text/plain; charset=utf-8", HTTPStatus.BAD_REQUEST)
            return
        body = self.rfile.read(content_length)
        message = BytesParser(policy=default).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
        )
        source_part = next(
            (part for part in message.iter_parts() if part.get_param("name", header="content-disposition") == "source_language"),
            None,
        )
        source_code = DEFAULT_SOURCE_CODE
        if source_part is not None:
            raw_source = source_part.get_payload(decode=True) or b""
            try:
                source_code = raw_source.decode(source_part.get_content_charset() or "utf-8").strip().lower()
            except UnicodeDecodeError:
                source_code = ""
        if source_code not in SOURCE_LANGUAGES:
            self.send_bytes(page(self.server.app, "Исходный язык не поддерживается."), "text/html; charset=utf-8", HTTPStatus.BAD_REQUEST)
            return
        source_language = SOURCE_LANGUAGES[source_code]
        language_part = next(
            (part for part in message.iter_parts() if part.get_param("name", header="content-disposition") == "target_language"),
            None,
        )
        target_code = DEFAULT_TARGET_CODE
        if language_part is not None:
            raw_language = language_part.get_payload(decode=True) or b""
            try:
                target_code = raw_language.decode(language_part.get_content_charset() or "utf-8").strip().lower()
            except UnicodeDecodeError:
                target_code = ""
        if target_code not in SUPPORTED_LANGUAGES:
            self.send_bytes(page(self.server.app, "Выбранный язык не поддерживается."), "text/html; charset=utf-8", HTTPStatus.BAD_REQUEST)
            return
        target_language = SUPPORTED_LANGUAGES[target_code]
        uploaded = next((part for part in message.iter_parts() if part.get_param("name", header="content-disposition") == "book"), None)
        if uploaded is None or not uploaded.get_filename():
            self.send_bytes(page(self.server.app, "Файл не выбран."), "text/html; charset=utf-8", HTTPStatus.BAD_REQUEST)
            return
        filename = Path(uploaded.get_filename()).name
        extension = Path(filename).suffix.lower()
        payload = uploaded.get_payload(decode=True) or b""
        if extension not in ALLOWED_EXTENSIONS:
            self.send_bytes(page(self.server.app, "Поддерживаются только PDF, DOCX и EPUB."), "text/html; charset=utf-8", HTTPStatus.BAD_REQUEST)
            return
        if not payload or len(payload) > MAX_UPLOAD_BYTES:
            self.send_bytes(page(self.server.app, "Размер файла должен быть от 1 байта до 30 MB."), "text/html; charset=utf-8", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        try:
            validate_payload(filename, payload)
        except UploadSecurityError as exc:
            self.send_bytes(page(self.server.app, str(exc)), "text/html; charset=utf-8", HTTPStatus.BAD_REQUEST)
            return
        if self.server.app.scanner is None:
            self.send_bytes(page(self.server.app, "VirusTotal не настроен: загрузка временно недоступна."), "text/html; charset=utf-8", HTTPStatus.SERVICE_UNAVAILABLE)
            return
        try:
            self.server.app.scanner.scan(filename, payload)
        except UploadSecurityError as exc:
            self.send_bytes(page(self.server.app, str(exc)), "text/html; charset=utf-8", HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        except VirusTotalError as exc:
            self.send_bytes(page(self.server.app, str(exc)), "text/html; charset=utf-8", HTTPStatus.SERVICE_UNAVAILABLE)
            return
        job_id = uuid.uuid4().hex
        job_dir = self.server.app.store.jobs_dir / job_id
        source_dir = job_dir / "input"
        source_dir.mkdir(parents=True, exist_ok=False)
        source_path = source_dir / filename
        source_path.write_bytes(payload)
        self.server.app.store.add(
            job_id,
            filename,
            source_path,
            len(payload),
            source_code,
            source_language,
            target_code,
            target_language,
        )
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", app_url("/"))
        self.end_headers()


class WebServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], app: App):
        super().__init__(address, Handler)
        self.app = app


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = Path(os.getenv("TRANSLATE_BOOK_DATA_DIR", str(repo_root / "data"))).resolve()
    host = os.getenv("TRANSLATE_BOOK_HOST", "127.0.0.1")
    port = int(os.getenv("TRANSLATE_BOOK_PORT", "3100"))
    app = App(repo_root, data_dir, scanner=VirusTotalScanner.from_env())
    app.worker.start()
    server = WebServer((host, port), app)
    try:
        print(f"translate-book-web listening on {host}:{port}", flush=True)
        server.serve_forever()
    finally:
        app.worker.stop()
        app.worker.join(timeout=5)
        server.server_close()


if __name__ == "__main__":
    main()
