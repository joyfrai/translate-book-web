from __future__ import annotations

import html
import logging
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
    collect_translation_usage,
    run_translation,
)
from .security import UploadSecurityError, VirusTotalError, VirusTotalScanner, validate_payload
from .book_metadata import filename_book_metadata, pipeline_book_metadata
from .site_styles import SITE_STYLES as APPROVED_SITE_STYLES


MAX_UPLOAD_BYTES = 30 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".epub"}
BASE_PATH = os.getenv("TRANSLATE_BOOK_BASE_PATH", "").rstrip("/")
STATIC_ROOT = (Path(__file__).resolve().parent / "static").resolve()
STATIC_CONTENT_TYPES = {
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
}
STATUS_LABELS = {
    "queued": "В очереди",
    "processing": "Обрабатывается",
    "done": "Готово",
    "failed": "Ошибка",
}
LOGGER = logging.getLogger(__name__)
RUSSIAN_LANGUAGE_NAMES = {
    "ru": "Русский",
    "en": "Английский",
    "zh": "Китайский",
    "ja": "Японский",
    "ko": "Корейский",
    "fr": "Французский",
    "de": "Немецкий",
    "es": "Испанский",
}


def _log_filename(value: str | Path) -> str:
    return Path(value).name.replace("\n", "\\n").replace("\r", "\\r")


def language_select_label(code: str, name: str) -> str:
    russian_name = RUSSIAN_LANGUAGE_NAMES.get(code)
    if not russian_name or russian_name.casefold() == name.casefold():
        return name
    return f"{name} ({russian_name})"


def app_url(path: str = "/") -> str:
    if path == "/":
        return f"{BASE_PATH}/" if BASE_PATH else "/"
    return f"{BASE_PATH}{path}" if BASE_PATH else path


def asset_url(path: str) -> str:
    return app_url(f"/assets/{path.lstrip('/')}")


FAVICON_MARKUP = f'<link rel="icon" type="image/webp" href="{asset_url("atmosphere/translate-book-crest.webp")}">'


def icon(name: str, class_name: str = "ui-icon") -> str:
    return f'<img class="{class_name}" src="{asset_url(f"icons/{name}.svg")}" alt="" aria-hidden="true">'


def cover_theme_index(job_id: str) -> int:
    try:
        return int(job_id[:8], 16) % 20
    except ValueError:
        return sum(ord(character) for character in job_id) % 20


def book_count_label(count: int) -> str:
    remainder_100 = count % 100
    remainder_10 = count % 10
    if 11 <= remainder_100 <= 14:
        word = "книг"
    elif remainder_10 == 1:
        word = "книга"
    elif remainder_10 in {2, 3, 4}:
        word = "книги"
    else:
        word = "книг"
    return f"{count} {word}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def attachment_header(filename: str) -> str:
    ascii_name = "".join(character if character.isascii() and (character.isalnum() or character in "._-") else "_" for character in filename)
    ascii_name = ascii_name.strip("._") or "download"
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename, safe="")}'


def format_display_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value.replace("T", " ").replace(" UTC", "").replace("Z", "").rsplit(":", 1)[0]


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
                    source_language TEXT NOT NULL DEFAULT 'English',
                    book_title TEXT NOT NULL DEFAULT '',
                    book_author TEXT NOT NULL DEFAULT '',
                    translation_requests INTEGER,
                    translation_tokens INTEGER
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
            if "book_title" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN book_title TEXT NOT NULL DEFAULT ''")
            if "book_author" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN book_author TEXT NOT NULL DEFAULT ''")
            if "translation_requests" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN translation_requests INTEGER")
            if "translation_tokens" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN translation_tokens INTEGER")
            db.execute(
                "UPDATE jobs SET status='queued', updated_at=? WHERE status='processing'",
                (utc_now(),),
            )
        LOGGER.info("store_initialized data_dir=%s status_counts=%s", data_dir, self.status_counts())

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
        book_title, book_author = filename_book_metadata(original_name)
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO jobs(
                    id, original_name, source_path, size_bytes, status,
                    created_at, updated_at, source_code, source_language,
                    target_code, target_language, book_title, book_author
                )
                VALUES(?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?)
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
                    book_title,
                    book_author,
                ),
            )

    def set_book_metadata(self, job_id: str, title: str, author: str) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET book_title=?, book_author=?, updated_at=? WHERE id=?",
                (title, author, utc_now(), job_id),
            )

    def set_translation_usage(self, job_id: str, requests: int, tokens: int) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET translation_requests=?, translation_tokens=?, updated_at=? WHERE id=?",
                (requests, tokens, utc_now(), job_id),
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

    def status_counts(self) -> dict[str, int]:
        with self.connect() as db:
            return {
                row["status"]: row["count"]
                for row in db.execute("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status")
            }

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
            job_id = job["id"]
            job_name = _log_filename(job["original_name"])
            LOGGER.info(
                "job_claimed job_id=%s filename=%s source_language=%s target_language=%s",
                job_id,
                job_name,
                job["source_language"],
                job["target_language"],
            )
            stage = "translation"
            try:
                LOGGER.info("job_translation_started job_id=%s", job_id)
                result_path = run_translation(
                    repo_root=self.repo_root,
                    job_dir=self.store.jobs_dir / job["id"],
                    source_path=Path(job["source_path"]),
                    source_code=job["source_code"],
                    source_language=job["source_language"],
                    target_code=job["target_code"],
                    target_language=job["target_language"],
                )
                LOGGER.info("job_translation_succeeded job_id=%s result=%s", job_id, _log_filename(result_path))
                stage = "metadata"
                LOGGER.info("job_metadata_started job_id=%s", job_id)
                title, author = pipeline_book_metadata(
                    self.store.jobs_dir / job["id"],
                    Path(job["source_path"]),
                    job["original_name"],
                )
                self.store.set_book_metadata(job["id"], title, author)
                LOGGER.info("job_metadata_succeeded job_id=%s title=%s author=%s", job_id, _log_filename(title), _log_filename(author))
                stage = "finish"
                self.store.finish(job["id"], result_path)
                LOGGER.info("job_completed job_id=%s result=%s", job_id, _log_filename(result_path))
            except Exception as exc:  # keep the durable queue alive
                LOGGER.exception("job_failed job_id=%s stage=%s error=%s", job_id, stage, exc)
                self.store.fail(job["id"], str(exc))
            finally:
                try:
                    requests, tokens = collect_translation_usage(self.store.jobs_dir / job_id)
                    self.store.set_translation_usage(job_id, requests, tokens)
                    LOGGER.info("job_usage_persisted job_id=%s requests=%d tokens=%d", job_id, requests, tokens)
                except Exception:
                    LOGGER.warning("job_usage_persist_failed job_id=%s", job_id, exc_info=True)


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
    return f"""<aside class="app-navigation lamp-is-on">
  <div class="brand-lockup">
    <a class="app-brand" href="{app_url('/')}" aria-label="Translate Book — загрузить книгу">
      <img src="{asset_url('atmosphere/translate-book-crest.webp')}" alt="">
      <span>Translate Book</span>
    </a>
    <button class="mobile-crest-toggle" type="button" aria-label="Разбудить библиотеку"></button>
  </div>
  <nav aria-label="Основная навигация">
    <a class="{upload_class}" href="{app_url('/')}">{icon('upload-simple', 'nav-icon')}<span>Загрузить</span></a>
    <a class="{library_class}" href="{app_url('/library')}">{icon('book-open', 'nav-icon')}<span>Библиотека</span><span class="nav-count">{library_count}</span></a>
  </nav>
  <button class="lamp-toggle" type="button" aria-label="Выключить лампу" aria-pressed="true"></button>
</aside>
<figure class="lamp-easter-egg-message" role="dialog" aria-labelledby="lamp-quote-text" aria-hidden="true">
  <button class="lamp-easter-egg-close" type="button" aria-label="Закрыть цитату"><span aria-hidden="true">×</span></button>
  <blockquote id="lamp-quote-text">«Многие упорны в отношении однажды избранного пути, немногие — в отношении цели».</blockquote>
  <figcaption>Фридрих Ницше</figcaption>
</figure>"""


def site_footer() -> str:
    return (
        '<footer class="site-footer">'
        'Develop by <a href="https://t.me/webbuildozer" target="_blank" rel="noopener noreferrer">'
        'https://t.me/webbuildozer</a> · Based on '
        '<a href="https://github.com/deusyu/translate-book" target="_blank" rel="noopener noreferrer">'
        'https://github.com/deusyu/translate-book</a>'
        '</footer>'
    )


def lamp_interaction_script() -> str:
    return """<script>
  (() => {
    const navigation = document.querySelector(".app-navigation");
    const toggle = document.querySelector(".lamp-toggle");
    const app = navigation?.closest(".library-app");
    const easterEggMessage = document.querySelector(".lamp-easter-egg-message");
    const closeEasterEgg = document.querySelector(".lamp-easter-egg-close");
    const mobileCrestToggle = document.querySelector(".mobile-crest-toggle");
    if (!navigation || !toggle || !app || !easterEggMessage || !closeEasterEgg || !mobileCrestToggle) return;

    const mobileEasterEggActive = "mobile-easter-egg-active";
    const dismissEasterEgg = () => {
      app.classList.remove("lamp-easter-egg-active", mobileEasterEggActive);
      easterEggMessage.setAttribute("aria-hidden", "true");
    };
    closeEasterEgg.addEventListener("click", dismissEasterEgg);

    let mobileTapCount = 0;
    let mobileTapTimer;
    const resetMobileTaps = () => {
      mobileTapCount = 0;
      window.clearTimeout(mobileTapTimer);
    };
    mobileCrestToggle.addEventListener("click", () => {
      if (!window.matchMedia("(max-width: 640px)").matches) return;
      if (app.classList.contains(mobileEasterEggActive)) return;
      if (mobileTapCount === 0) {
        mobileTapTimer = window.setTimeout(resetMobileTaps, 3000);
      }
      mobileTapCount += 1;
      if (mobileTapCount >= 7) {
        resetMobileTaps();
        app.classList.add(mobileEasterEggActive);
        easterEggMessage.setAttribute("aria-hidden", "false");
        closeEasterEgg.focus({ preventScroll: true });
      }
    });
    if (window.matchMedia("(max-width: 980px)").matches) return;

    let isOn = true;
    let isAnimating = false;
    let manualToggleCount = 0;
    toggle.addEventListener("pointerdown", () => toggle.dataset.pointerFocus = "true");
    toggle.addEventListener("blur", () => toggle.removeAttribute("data-pointer-focus"));
    const syncA11y = () => {
      toggle.setAttribute("aria-pressed", String(isOn));
      toggle.setAttribute("aria-label", isOn ? "Выключить лампу" : "Включить лампу");
    };
    const finish = (turnOn, animationClass) => {
      navigation.classList.remove(animationClass);
      navigation.classList.toggle("lamp-is-off", !turnOn);
      navigation.classList.toggle("lamp-is-on", turnOn);
      isOn = turnOn;
      isAnimating = false;
      syncA11y();
    };

    const setLampState = (turnOn) => {
      if (isAnimating || turnOn === isOn) return;
      const animationClass = turnOn ? "lamp-flicker-on" : "lamp-flicker-off";
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        finish(turnOn, animationClass);
        return;
      }
      isAnimating = true;
      navigation.classList.add(animationClass);
      navigation.addEventListener("animationend", (event) => {
        if (event.animationName !== animationClass) return;
        finish(turnOn, animationClass);
      }, { once: true });
    };

    const triggerEasterEgg = () => {
      app.classList.add("lamp-easter-egg-active");
      easterEggMessage.setAttribute("aria-hidden", "false");
      closeEasterEgg.focus({ preventScroll: true });
    };

    toggle.addEventListener("click", () => {
      if (isAnimating) return;
      manualToggleCount += 1;
      if (manualToggleCount % 16 === 0) triggerEasterEgg();
      setLampState(!isOn);
    });
    const scheduleAutoOff = () => window.setTimeout(() => setLampState(false), 1200);
    if (document.readyState === "complete") {
      scheduleAutoOff();
    } else {
      window.addEventListener("load", scheduleAutoOff, { once: true });
    }
  })();
</script>"""


def job_markup(app: App, job: sqlite3.Row) -> str:
    status = job["status"]
    completed, total = app.store.progress(job)
    progress_note = ""
    if total:
        progress_label = f"{completed / total * 100:.1f}% ({completed}/{total})"
        progress_value = min(completed / total * 100, 100)
        if status == "processing" and completed >= total:
            progress_note = '<span class="progress-note">Подготовка файлов…</span>'
    elif status == "done":
        progress_label, progress_value = "100%", 100
    elif status == "queued":
        progress_label, progress_value = "Ожидает", 0
    else:
        progress_label, progress_value = "Подготовка", 0
    result = ""
    if status == "done" and job["result_path"] and Path(job["result_path"]).is_file():
        result = f'<a class="button" href="{app_url(f"/download/{job["id"]}")}">{icon("download-simple")}<span>Скачать ZIP</span></a>'
    error = f'<div class="error">{html.escape(job["error"])}</div>' if job["error"] else ""
    usage = ""
    if job["translation_tokens"]:
        token_count = f'{job["translation_tokens"]:,}'.replace(",", " ")
        usage = f'<span class="job-usage" title="Фактический usage по логам Codex">{token_count} токенов · {job["translation_requests"]} запросов</span>'
    status_label = html.escape(STATUS_LABELS.get(status, status))
    status_icon = {
        "queued": "clock-countdown",
        "processing": "spinner-gap",
        "done": "check-circle",
        "failed": "warning-circle",
    }.get(status, "warning-circle")
    return f"""<li class="job">
  <div class="job-main"><div class="job-title"><strong title="{html.escape(job["original_name"])}">{html.escape(job["original_name"])}</strong><span class="status status-{html.escape(status)}" role="img" aria-label="{status_label}" title="{status_label}">{icon(status_icon, 'status-icon')}</span></div><div class="job-meta"><span>{job["size_bytes"] / 1024 / 1024:.1f} МБ</span><span>{html.escape(job["source_language"])} → {html.escape(job["target_language"])}</span><span>{format_display_time(job["created_at"])}</span>{usage}</div></div>
  <div class="progress-wrap"><div class="progress-track" role="progressbar" aria-label="Прогресс перевода" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{progress_value:.0f}"><span style="--progress: {progress_value:.1f}%"></span></div><span class="progress-label">{progress_label}</span>{progress_note}</div>
  <div class="job-actions">{result}</div>
  {error}
</li>"""


def page(app: App, message: str = "") -> bytes:
    job_rows = "".join(job_markup(app, job) for job in app.store.list())
    jobs = f'<ul class="job-list">{job_rows}</ul>' if job_rows else '<div class="empty-state"><strong>Файлов пока нет.</strong><span>После выбора книги задача появится здесь.</span></div>'
    notice = f'<div class="notice" role="status">{html.escape(message)}</div>' if message else ""
    refresh_href = f'{app_url("/")}?refresh={uuid.uuid4().hex}#jobs'
    source_options = "".join(
        f'<option value="{code}"{" selected" if code == DEFAULT_SOURCE_CODE else ""}>{html.escape(language_select_label(code, name))}</option>'
        for code, name in SOURCE_LANGUAGES.items()
    )
    language_options = "".join(
        f'<option value="{code}"{" selected" if code == DEFAULT_TARGET_CODE else ""}>{html.escape(language_select_label(code, name))}</option>'
        for code, name in SUPPORTED_LANGUAGES.items()
    )
    library_count = len(app.store.list_finished())
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#07100e">{FAVICON_MARKUP}
<title>Translate Book — загрузить книгу</title>{APPROVED_SITE_STYLES}</head><body>
<div class="library-app upload-app">{site_header("upload", library_count)}
<div class="app-content"><main>
  <header class="page-header"><div><h1>Загрузить книгу</h1><p>Загрузите файл, выберите языки и получите готовый перевод.</p></div><a class="quiet-link" href="{app_url('/library')}">{icon('book-open')}<span>Открыть библиотеку</span></a></header>
  {notice}
  <section class="service-explainer" aria-labelledby="service-title">
    <div class="service-explainer-heading"><h2 id="service-title">Как это работает</h2><p>От файла до готового перевода — три шага.</p></div>
    <div class="service-steps">
      <article class="service-step"><span class="service-step-icon">{icon('file-arrow-up')}</span><div><h3>Загрузите книгу</h3><p>PDF, DOCX или EPUB размером до 30 MB.</p></div></article>
      <article class="service-step"><span class="service-step-icon">{icon('arrows-left-right')}</span><div><h3>Выберите языки</h3><p>Укажите язык оригинала и язык перевода.</p></div></article>
      <article class="service-step"><span class="service-step-icon">{icon('download-simple')}</span><div><h3>Скачайте результат</h3><p>После обработки загрузите архив с готовыми файлами.</p></div></article>
    </div>
    <p class="service-note">Завершённые переводы появляются в публичной библиотеке вместе с оригиналом.</p>
  </section>
  <form class="upload-workspace" action="{app_url('/upload')}" method="post" enctype="multipart/form-data" aria-labelledby="upload-title">
    <span class="sr-only">Как работает перевод</span>
    <div class="file-dropzone"><div class="field-label"><span id="upload-title">Файл книги</span><span class="field-hint">до 30 MB</span></div><input class="file-input" id="book" name="book" type="file" accept=".pdf,.docx,.epub" aria-describedby="file-feedback" required><label class="file-picker" id="file-drop" for="book"><img class="file-visual" src="{asset_url('icons/file-arrow-up.svg')}" alt=""><strong id="file-name">Выберите или перетащите файл</strong><span id="file-meta">PDF, DOCX или EPUB</span></label><p class="file-feedback" id="file-feedback" role="status" aria-live="polite">Файл не выбран.</p></div>
    <div class="translation-settings">
      <div class="language-grid"><div><label class="field-label" for="source_language"><span>Язык оригинала</span></label><div class="select-wrap"><select id="source_language" name="source_language">{source_options}</select></div></div><div><label class="field-label" for="target_language"><span>Язык перевода</span></label><div class="select-wrap"><select id="target_language" name="target_language">{language_options}</select></div></div></div>
      <div class="form-actions"><button class="button button-primary" id="upload-submit" type="submit">{icon('upload-simple')}<span id="upload-submit-label">Начать перевод</span></button></div>
    </div>
  </form>
  <section class="tasks-section" id="jobs" aria-labelledby="jobs-title">
    <div class="section-heading"><div><h2 id="jobs-title">Текущие загрузки</h2></div><a class="refresh-link" href="{refresh_href}">{icon('arrow-clockwise')}<span>Обновить</span></a></div>
    {jobs}
  </section>
</main>{site_footer()}</div></div>
<script>
  const bookInput = document.getElementById("book");
  const fileDrop = document.getElementById("file-drop");
  let uploadLocked = false;
  if (bookInput) {{
    const fileName = document.getElementById("file-name");
    const fileMeta = document.getElementById("file-meta");
    const feedback = document.getElementById("file-feedback");
    const allowedFile = /\\.(pdf|docx|epub)$/i;

    const showFileError = (message) => {{
      bookInput.value = "";
      fileName.textContent = "Выберите или перетащите файл";
      fileMeta.textContent = "PDF, DOCX или EPUB";
      feedback.textContent = message;
      feedback.classList.add("is-error");
      fileDrop.classList.remove("has-file", "is-dragover");
    }};

    const renderFile = (file) => {{
      if (!file) return false;
      if (!allowedFile.test(file.name)) {{
        showFileError("Этот формат не поддерживается. Нужен PDF, DOCX или EPUB.");
        return false;
      }}
      const sizeMb = file.size / (1024 * 1024);
      fileName.textContent = file.name;
      fileMeta.textContent = `${{sizeMb.toFixed(1)}} MB · файл выбран`;
      feedback.textContent = sizeMb <= 30 ? "Файл выбран и готов к загрузке." : "Файл больше лимита 30 МБ.";
      feedback.classList.toggle("is-error", sizeMb > 30);
      fileDrop.classList.add("has-file");
      return true;
    }};

    const applyDroppedFile = (file) => {{
      if (!renderFile(file)) return;
      try {{
        const transfer = new DataTransfer();
        transfer.items.add(file);
        bookInput.files = transfer.files;
      }} catch (error) {{
        showFileError("Браузер не смог принять файл. Выберите его через проводник.");
      }}
    }};

    bookInput.addEventListener("change", () => {{
      renderFile(bookInput.files[0]);
    }});

    ["dragenter", "dragover"].forEach((eventName) => {{
      fileDrop.addEventListener(eventName, (event) => {{
        event.preventDefault();
        event.stopPropagation();
        if (uploadLocked) return;
        fileDrop.classList.add("is-dragover");
      }});
    }});

    ["dragleave", "dragend"].forEach((eventName) => {{
      fileDrop.addEventListener(eventName, (event) => {{
        event.preventDefault();
        fileDrop.classList.remove("is-dragover");
      }});
    }});

    fileDrop.addEventListener("drop", (event) => {{
      event.preventDefault();
      event.stopPropagation();
      fileDrop.classList.remove("is-dragover");
      if (uploadLocked) return;
      const file = event.dataTransfer && event.dataTransfer.files[0];
      if (file) {{
        applyDroppedFile(file);
      }} else {{
        showFileError("Не удалось получить файл из перетаскивания.");
      }}
    }});
  }}

  const uploadForm = document.querySelector(".upload-workspace");
  const uploadSubmit = document.getElementById("upload-submit");
  if (uploadForm && uploadSubmit) {{
    uploadForm.addEventListener("submit", (event) => {{
      if (uploadSubmit.disabled) {{
        event.preventDefault();
        return;
      }}
      uploadSubmit.disabled = true;
      uploadLocked = true;
      if (bookInput) {{
        bookInput.setAttribute("aria-disabled", "true");
      }}
      if (fileDrop) {{
        fileDrop.classList.add("is-disabled");
        fileDrop.setAttribute("aria-disabled", "true");
      }}
      uploadSubmit.setAttribute("aria-busy", "true");
      uploadSubmit.setAttribute("aria-label", "Книга загружается");
      const submitIcon = uploadSubmit.querySelector(".ui-icon");
      const submitLabel = document.getElementById("upload-submit-label");
      if (submitIcon) {{
        submitIcon.src = "{asset_url('icons/spinner-gap.svg')}";
        submitIcon.classList.add("button-progress-icon");
      }}
      if (submitLabel) {{
        submitLabel.textContent = "Книга загружается…";
      }}
    }});
  }}
</script>
{lamp_interaction_script()}
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
            original_name = job["original_name"]
            fallback_title, fallback_author = filename_book_metadata(original_name)
            book_title = job["book_title"] or fallback_title
            book_author = job["book_author"] or fallback_author
            title = html.escape(book_title)
            author = html.escape(book_author)
            original_title = html.escape(original_name)
            job_id = html.escape(job["id"])
            source_language = html.escape(job["source_language"])
            target_language = html.escape(job["target_language"])
            theme_index = cover_theme_index(job["id"])
            created_at = format_display_time(job["created_at"])
            cards.append(
                f"""<article class="catalog-book" data-title="{html.escape(f"{book_title} {book_author}".casefold(), quote=True)}">
  <div class="book-cover cover-theme-{theme_index}" aria-hidden="true"><div class="book-cover-frame"><span class="book-cover-title">{title}</span><span class="book-cover-rule"></span><span class="book-cover-author">{author}</span></div></div>
  <div class="catalog-book-info"><h2 title="{original_title}">{title}</h2><p class="book-author">{author}</p><p class="book-date">{created_at}</p><p class="book-language">{icon('arrows-left-right')}<span>{source_language} → {target_language}</span></p><div class="book-downloads"><a class="button" href="{app_url(f"/download/{job_id}/original")}">{icon('download-simple')}<span>Скачать оригинал · {source_language}</span></a><a class="button button-primary" href="{app_url(f"/download/{job_id}/translated")}">{icon('download-simple')}<span>Скачать перевод · {target_language}</span></a></div></div>
</article>"""
            )
        books = "".join(cards)
    else:
        books = '<div class="empty-state catalog-empty"><strong>Переведённых книг пока нет.</strong><span>Готовые переводы появятся здесь.</span></div>'
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#07100e">{FAVICON_MARKUP}
<title>Библиотека — Translate Book</title>{APPROVED_SITE_STYLES}</head><body>
<div class="library-app catalog-app">{site_header("library", len(finished))}
<div class="app-content"><main>
  <header class="page-header catalog-header"><div><h1>Библиотека</h1><p>Публичный каталог · {book_count_label(len(finished))}</p></div><div class="catalog-tools"><label class="search-field"><span class="sr-only">Найти книгу</span><img src="{asset_url('icons/magnifying-glass.svg')}" alt=""><input id="catalog-search" type="search" placeholder="Найти книгу" autocomplete="off"></label><a class="button button-primary" href="{app_url('/')}">{icon('upload-simple')}<span>Загрузить книгу</span></a></div></header>
  <section class="catalog-grid" id="catalog-grid" aria-label="Каталог книг">{books}</section>
  <p class="empty-state catalog-empty is-hidden" id="search-empty">Ничего не найдено.</p>
</main>{site_footer()}</div></div>
<script>
  const catalogSearch = document.getElementById("catalog-search");
  if (catalogSearch) {{
    const books = Array.from(document.querySelectorAll(".catalog-book"));
    const empty = document.getElementById("search-empty");
    catalogSearch.addEventListener("input", () => {{
      const query = catalogSearch.value.trim().toLocaleLowerCase();
      let visible = 0;
      books.forEach((book) => {{
        const matches = !query || book.dataset.title.includes(query);
        book.classList.toggle("is-hidden", !matches);
        if (matches) visible += 1;
      }});
      empty.classList.toggle("is-hidden", visible > 0 || books.length === 0);
    }});
  }}
</script>
{lamp_interaction_script()}
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
        if path.startswith("/assets/"):
            relative_path = unquote(path.removeprefix("/assets/"))
            asset_path = (STATIC_ROOT / relative_path).resolve()
            try:
                is_safe = asset_path.is_relative_to(STATIC_ROOT)
            except OSError:
                is_safe = False
            content_type = STATIC_CONTENT_TYPES.get(asset_path.suffix.lower())
            if not is_safe or content_type is None or not asset_path.is_file():
                self.send_bytes(b"Not found", "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)
                return
            payload = asset_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if path == "/favicon.ico":
            favicon = STATIC_ROOT / "atmosphere" / "translate-book-crest.webp"
            self.send_bytes(favicon.read_bytes(), "image/webp")
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
            LOGGER.warning("upload_rejected stage=request reason=invalid_content_length")
            self.send_bytes(b"Invalid Content-Length", "text/plain; charset=utf-8", HTTPStatus.BAD_REQUEST)
            return
        LOGGER.info("upload_received content_length=%d", content_length)
        if content_length < 0 or content_length > MAX_UPLOAD_BYTES + 1024 * 1024:
            LOGGER.warning("upload_rejected stage=request reason=content_length_limit content_length=%d", content_length)
            self.send_bytes(b"File is too large", "text/plain; charset=utf-8", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data"):
            LOGGER.warning("upload_rejected stage=request reason=invalid_content_type")
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
            LOGGER.warning("upload_rejected stage=language reason=unsupported_source source_code=%s", source_code)
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
            LOGGER.warning("upload_rejected stage=language reason=unsupported_target target_code=%s", target_code)
            self.send_bytes(page(self.server.app, "Выбранный язык не поддерживается."), "text/html; charset=utf-8", HTTPStatus.BAD_REQUEST)
            return
        target_language = SUPPORTED_LANGUAGES[target_code]
        uploaded = next((part for part in message.iter_parts() if part.get_param("name", header="content-disposition") == "book"), None)
        if uploaded is None or not uploaded.get_filename():
            LOGGER.warning("upload_rejected stage=parse reason=file_missing")
            self.send_bytes(page(self.server.app, "Файл не выбран."), "text/html; charset=utf-8", HTTPStatus.BAD_REQUEST)
            return
        filename = Path(uploaded.get_filename()).name
        log_filename = _log_filename(filename)
        extension = Path(filename).suffix.lower()
        payload = uploaded.get_payload(decode=True) or b""
        LOGGER.info("upload_file_received filename=%s extension=%s size_bytes=%d source_language=%s target_language=%s", log_filename, extension, len(payload), source_language, target_language)
        if extension not in ALLOWED_EXTENSIONS:
            LOGGER.warning("upload_rejected filename=%s stage=extension reason=unsupported_extension", log_filename)
            self.send_bytes(page(self.server.app, "Поддерживаются только PDF, DOCX и EPUB."), "text/html; charset=utf-8", HTTPStatus.BAD_REQUEST)
            return
        if not payload or len(payload) > MAX_UPLOAD_BYTES:
            LOGGER.warning("upload_rejected filename=%s stage=size size_bytes=%d", log_filename, len(payload))
            self.send_bytes(page(self.server.app, "Размер файла должен быть от 1 байта до 30 MB."), "text/html; charset=utf-8", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        try:
            LOGGER.info("upload_validation_started filename=%s", log_filename)
            validate_payload(filename, payload)
        except UploadSecurityError as exc:
            LOGGER.warning("upload_rejected filename=%s stage=validation reason=%s", log_filename, exc)
            self.send_bytes(page(self.server.app, str(exc)), "text/html; charset=utf-8", HTTPStatus.BAD_REQUEST)
            return
        LOGGER.info("upload_validation_succeeded filename=%s", log_filename)
        if self.server.app.scanner is None:
            LOGGER.error("upload_rejected filename=%s stage=virus_scan reason=scanner_not_configured", log_filename)
            self.send_bytes(page(self.server.app, "VirusTotal не настроен: загрузка временно недоступна."), "text/html; charset=utf-8", HTTPStatus.SERVICE_UNAVAILABLE)
            return
        try:
            LOGGER.info("upload_virus_scan_started filename=%s", log_filename)
            verdict = self.server.app.scanner.scan(filename, payload)
        except UploadSecurityError as exc:
            LOGGER.warning("upload_rejected filename=%s stage=virus_scan reason=threat error=%s", log_filename, exc)
            self.send_bytes(page(self.server.app, str(exc)), "text/html; charset=utf-8", HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        except VirusTotalError as exc:
            LOGGER.error("upload_rejected filename=%s stage=virus_scan reason=service_error error=%s", log_filename, exc)
            self.send_bytes(page(self.server.app, str(exc)), "text/html; charset=utf-8", HTTPStatus.SERVICE_UNAVAILABLE)
            return
        LOGGER.info(
            "upload_virus_scan_succeeded filename=%s analysis_id=%s status=%s malicious=%s suspicious=%s",
            log_filename,
            getattr(verdict, "analysis_id", "unknown"),
            getattr(verdict, "status", "unknown"),
            getattr(verdict, "malicious", "unknown"),
            getattr(verdict, "suspicious", "unknown"),
        )
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
        counts = self.server.app.store.status_counts()
        LOGGER.info("upload_enqueued job_id=%s filename=%s queue_depth=%d processing=%d", job_id, log_filename, counts.get("queued", 0), counts.get("processing", 0))
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", app_url("/"))
        self.end_headers()


class WebServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], app: App):
        super().__init__(address, Handler)
        self.app = app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = Path(os.getenv("TRANSLATE_BOOK_DATA_DIR", str(repo_root / "data"))).resolve()
    host = os.getenv("TRANSLATE_BOOK_HOST", "127.0.0.1")
    port = int(os.getenv("TRANSLATE_BOOK_PORT", "3100"))
    scanner = VirusTotalScanner.from_env()
    LOGGER.info("service_start host=%s port=%d data_dir=%s virus_total_configured=%s", host, port, data_dir, scanner is not None)
    app = App(repo_root, data_dir, scanner=scanner)
    app.worker.start()
    server = WebServer((host, port), app)
    try:
        LOGGER.info("service_listening host=%s port=%d", host, port)
        server.serve_forever()
    finally:
        LOGGER.info("service_stopping")
        app.worker.stop()
        app.worker.join(timeout=5)
        server.server_close()
        LOGGER.info("service_stopped")


if __name__ == "__main__":
    main()
