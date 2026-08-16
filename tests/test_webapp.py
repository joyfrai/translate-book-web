from __future__ import annotations

import base64
import http.client
import sqlite3
import tempfile
import threading
import unittest
import uuid
import zipfile
from pathlib import Path

from webapp.app import App, WebServer


class WebAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.app = App(Path(__file__).resolve().parents[1], root / "data", "joy", "secret")
        self.server = WebServer(("127.0.0.1", 0), self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def request(self, method: str, path: str, body: bytes = b"", content_type: str | None = None, auth: bool = True):
        connection = http.client.HTTPConnection("127.0.0.1", self.port)
        headers = {}
        if auth:
            token = base64.b64encode(b"joy:secret").decode()
            headers["Authorization"] = f"Basic {token}"
        if content_type:
            headers["Content-Type"] = content_type
            headers["Content-Length"] = str(len(body))
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        connection.close()
        return response, payload

    def test_basic_auth_and_empty_page(self) -> None:
        response, _ = self.request("GET", "/", auth=False)
        self.assertEqual(response.status, 401)
        response, payload = self.request("GET", "/")
        self.assertEqual(response.status, 200)
        self.assertIn("Файлов пока нет".encode(), payload)
        self.assertIn("name=\"target_language\"".encode(), payload)
        self.assertIn("<option value=\"ru\" selected>Русский</option>".encode(), payload)

    def test_upload_creates_queued_job(self) -> None:
        boundary = "----translate-book-" + uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="book"; filename="sample.epub"\r\n'
            "Content-Type: application/epub+zip\r\n\r\n"
        ).encode() + b"epub bytes" + f"\r\n--{boundary}--\r\n".encode()
        response, _ = self.request("POST", "/upload", body, f"multipart/form-data; boundary={boundary}")
        self.assertEqual(response.status, 303)
        jobs = self.app.store.list()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["status"], "queued")
        self.assertEqual(jobs[0]["target_code"], "ru")
        self.assertEqual(jobs[0]["target_language"], "Русский")
        self.assertTrue(Path(jobs[0]["source_path"]).is_file())

    def test_upload_persists_selected_language(self) -> None:
        boundary = "----translate-book-" + uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="target_language"\r\n\r\n'
            "de\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="book"; filename="sample.epub"\r\n'
            "Content-Type: application/epub+zip\r\n\r\n"
        ).encode() + b"epub bytes" + f"\r\n--{boundary}--\r\n".encode()
        response, _ = self.request("POST", "/upload", body, f"multipart/form-data; boundary={boundary}")
        self.assertEqual(response.status, 303)
        job = self.app.store.list()[0]
        self.assertEqual(job["target_code"], "de")
        self.assertEqual(job["target_language"], "Deutsch")

    def test_done_job_can_be_downloaded(self) -> None:
        job_id = uuid.uuid4().hex
        job_dir = self.app.store.jobs_dir / job_id
        job_dir.mkdir(parents=True)
        result = job_dir / "translated-book.zip"
        with zipfile.ZipFile(result, "w") as archive:
            archive.writestr("book.html", "translated")
        source = job_dir / "source.epub"
        source.write_bytes(b"source")
        self.app.store.add(job_id, "source.epub", source, 6)
        self.app.store.finish(job_id, result)
        response, payload = self.request("GET", f"/download/{job_id}")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "application/zip")
        self.assertTrue(payload.startswith(b"PK"))

    def test_processing_jobs_are_requeued_on_store_start(self) -> None:
        job_id = uuid.uuid4().hex
        job_dir = self.app.store.jobs_dir / job_id
        job_dir.mkdir(parents=True)
        source = job_dir / "source.epub"
        source.write_bytes(b"source")
        self.app.store.add(job_id, "source.epub", source, 6)
        with self.app.store.connect() as db:
            db.execute("UPDATE jobs SET status='processing' WHERE id=?", (job_id,))
        restarted = type(self.app.store)(self.app.store.data_dir)
        self.assertEqual(restarted.get(job_id)["status"], "queued")

    def test_legacy_store_gets_default_russian_language(self) -> None:
        data_dir = Path(self.temp_dir.name) / "legacy-data"
        data_dir.mkdir()
        jobs_dir = data_dir / "jobs"
        jobs_dir.mkdir()
        db_path = data_dir / "jobs.sqlite3"
        with sqlite3.connect(db_path) as db:
            db.execute(
                """
                CREATE TABLE jobs (
                    id TEXT PRIMARY KEY,
                    original_name TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    result_path TEXT,
                    size_bytes INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        from webapp.app import Store

        store = Store(data_dir)
        columns = {row["name"] for row in store.connect().execute("PRAGMA table_info(jobs)")}
        self.assertIn("target_code", columns)
        self.assertIn("target_language", columns)


if __name__ == "__main__":
    unittest.main()
