from __future__ import annotations

import base64
import html
import os
import secrets
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
from urllib.parse import unquote, urlparse

from .translate_job import DEFAULT_TARGET_CODE, DEFAULT_TARGET_LANGUAGE, SUPPORTED_LANGUAGES, run_translation


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".epub"}
STATUS_LABELS = {
    "queued": "В очереди",
    "processing": "Обрабатывается",
    "done": "Готово",
    "failed": "Ошибка",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
                    target_language TEXT NOT NULL DEFAULT 'Русский'
                )
                """
            )
            columns = {row["name"] for row in db.execute("PRAGMA table_info(jobs)")}
            if "target_code" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN target_code TEXT NOT NULL DEFAULT 'ru'")
            if "target_language" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN target_language TEXT NOT NULL DEFAULT 'Русский'")
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
        target_code: str = DEFAULT_TARGET_CODE,
        target_language: str = DEFAULT_TARGET_LANGUAGE,
    ) -> None:
        now = utc_now()
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO jobs(
                    id, original_name, source_path, size_bytes, status,
                    created_at, updated_at, target_code, target_language
                )
                VALUES(?, ?, ?, ?, 'queued', ?, ?, ?, ?)
                """,
                (job_id, original_name, str(source_path), size_bytes, now, now, target_code, target_language),
            )

    def list(self) -> list[sqlite3.Row]:
        with self.connect() as db:
            return db.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()

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
                    target_code=job["target_code"],
                    target_language=job["target_language"],
                )
                self.store.finish(job["id"], result_path)
            except Exception as exc:  # keep the durable queue alive
                self.store.fail(job["id"], str(exc))


class App:
    def __init__(self, repo_root: Path, data_dir: Path, username: str, password: str):
        self.repo_root = repo_root
        self.store = Store(data_dir)
        self.username = username
        self.password = password
        self.worker = Worker(self.store, repo_root)


def page(app: App, message: str = "") -> bytes:
    rows = []
    for job in app.store.list():
        status = job["status"]
        result = ""
        if status == "done" and job["result_path"] and Path(job["result_path"]).is_file():
            result = f'<a class="download" href="/download/{html.escape(job["id"])}">Скачать результат</a>'
        error = f'<div class="error">{html.escape(job["error"])}</div>' if job["error"] else ""
        rows.append(
            f"""<li class="job">
              <div><strong>{html.escape(job["original_name"])}</strong><span class="status {status}">{STATUS_LABELS.get(status, status)}</span></div>
              <small>{job["created_at"].replace("T", " ").replace("+00:00", " UTC")} · {job["size_bytes"] / 1024 / 1024:.1f} MB · {html.escape(job["target_language"])}</small>
              {result}{error}
            </li>"""
        )
    jobs = "".join(rows) or '<li class="empty">Файлов пока нет.</li>'
    notice = f'<div class="notice">{html.escape(message)}</div>' if message else ""
    language_options = "".join(
        f'<option value="{code}"{" selected" if code == DEFAULT_TARGET_CODE else ""}>{html.escape(name)}</option>'
        for code, name in SUPPORTED_LANGUAGES.items()
    )
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Translate Book</title>
<style>
  :root {{ color-scheme: dark; font-family: Inter, system-ui, sans-serif; background:#111827; color:#f3f4f6; }}
  body {{ max-width:760px; margin:0 auto; padding:44px 20px; }}
  h1 {{ margin:0 0 8px; font-size:32px; }} p {{ color:#9ca3af; }}
  .card {{ background:#1f2937; border:1px solid #374151; border-radius:14px; padding:20px; margin:22px 0; }}
  form {{ display:flex; gap:12px; align-items:center; flex-wrap:wrap; }}
  input[type=file], select {{ max-width:100%; background:#111827; color:#f3f4f6; border:1px solid #4b5563; border-radius:8px; padding:9px; }} button, .download {{ background:#7c3aed; color:white; border:0; border-radius:8px; padding:10px 14px; cursor:pointer; text-decoration:none; font-weight:600; }}
  button:hover, .download:hover {{ background:#8b5cf6; }}
  ul {{ list-style:none; margin:0; padding:0; }} .job {{ border-top:1px solid #374151; padding:16px 0; }} .job:first-child {{ border-top:0; }}
  .status {{ display:inline-block; margin-left:10px; padding:3px 8px; border-radius:999px; font-size:12px; background:#374151; }}
  .status.done {{ background:#065f46; }} .status.failed {{ background:#991b1b; }} .status.processing {{ background:#92400e; }}
  small {{ display:block; color:#9ca3af; margin:7px 0 12px; }} .error {{ color:#fca5a5; white-space:pre-wrap; font-size:13px; }} .notice {{ background:#064e3b; padding:10px 12px; border-radius:8px; }} .empty {{ color:#9ca3af; }}
</style></head><body>
<h1>Translate Book</h1><p>Перевод книги с английского на выбранный язык. Обрабатывается одна книга за раз.</p>
{notice}<section class="card"><form action="/upload" method="post" enctype="multipart/form-data"><input name="book" type="file" accept=".pdf,.docx,.epub" required><label for="target_language">Язык результата</label><select id="target_language" name="target_language">{language_options}</select><button type="submit">Загрузить</button></form><small>По умолчанию: русский · PDF, DOCX или EPUB · максимум 20 MB</small></section>
<section class="card"><h2>Файлы</h2><p><a href="/" style="color:#c4b5fd">Обновить список</a></p><ul>{jobs}</ul></section>
</body></html>""".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server: "WebServer"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)

    def authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header[6:], validate=True).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (ValueError, UnicodeDecodeError):
            return False
        return secrets.compare_digest(username, self.server.app.username) and secrets.compare_digest(password, self.server.app.password)

    def require_auth(self) -> bool:
        if self.authorized():
            return True
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="translate-book"')
        self.end_headers()
        return False

    def send_bytes(self, body: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self.require_auth():
            return
        path = urlparse(self.path).path
        if path == "/":
            self.send_bytes(page(self.server.app), "text/html; charset=utf-8")
            return
        if path.startswith("/download/"):
            job_id = unquote(path.removeprefix("/download/"))
            job = self.server.app.store.get(job_id)
            if not job or job["status"] != "done" or not job["result_path"]:
                self.send_bytes(b"Not found", "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)
                return
            result_path = Path(job["result_path"])
            if not result_path.is_file():
                self.send_bytes(b"Not found", "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", 'attachment; filename="translated-book.zip"')
            self.send_header("Content-Length", str(result_path.stat().st_size))
            self.end_headers()
            with result_path.open("rb") as source:
                shutil.copyfileobj(source, self.wfile)
            return
        self.send_bytes(b"Not found", "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self.require_auth():
            return
        if urlparse(self.path).path != "/upload":
            self.send_bytes(b"Not found", "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)
            return
        content_length = int(self.headers.get("Content-Length", "-1"))
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
            self.send_bytes(page(self.server.app, "Размер файла должен быть от 1 байта до 20 MB."), "text/html; charset=utf-8", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        job_id = uuid.uuid4().hex
        job_dir = self.server.app.store.jobs_dir / job_id
        source_dir = job_dir / "input"
        source_dir.mkdir(parents=True, exist_ok=False)
        source_path = source_dir / filename
        source_path.write_bytes(payload)
        self.server.app.store.add(job_id, filename, source_path, len(payload), target_code, target_language)
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", "/")
        self.end_headers()


class WebServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], app: App):
        super().__init__(address, Handler)
        self.app = app


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = Path(os.getenv("TRANSLATE_BOOK_DATA_DIR", str(repo_root / "data"))).resolve()
    username = os.getenv("TRANSLATE_BOOK_USERNAME", "joy")
    password = os.getenv("TRANSLATE_BOOK_PASSWORD")
    if not password:
        raise RuntimeError("TRANSLATE_BOOK_PASSWORD is required")
    port = int(os.getenv("TRANSLATE_BOOK_PORT", "3100"))
    app = App(repo_root, data_dir, username, password)
    app.worker.start()
    server = WebServer(("0.0.0.0", port), app)
    try:
        print(f"translate-book-web listening on 0.0.0.0:{port}", flush=True)
        server.serve_forever()
    finally:
        app.worker.stop()
        app.worker.join(timeout=5)
        server.server_close()


if __name__ == "__main__":
    main()
