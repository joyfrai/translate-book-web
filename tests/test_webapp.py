from __future__ import annotations

import http.client
import io
import sqlite3
import tempfile
import threading
import unittest
import uuid
import zipfile
from pathlib import Path

from webapp import app as webapp_module
from webapp.app import App, Store, WebServer, page
from webapp.security import UploadSecurityError
from webapp.site_styles import SITE_STYLES as APPROVED_SITE_STYLES


class AcceptScanner:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[tuple[str, bytes]] = []

    def scan(self, filename: str, payload: bytes) -> None:
        self.calls.append((filename, payload))
        if self.error:
            raise self.error


class PresentationTests(unittest.TestCase):
    def test_display_time_omits_seconds_and_timezone(self) -> None:
        self.assertEqual(
            webapp_module.format_display_time("2026-08-19T21:16:57+00:00"),
            "2026-08-19 21:16",
        )

    def test_desktop_library_layout_stays_stable_while_scrolling(self) -> None:
        self.assertIn("position: fixed;", APPROVED_SITE_STYLES)
        self.assertIn("grid-column: 2;", APPROVED_SITE_STYLES)
        self.assertNotIn("background-attachment: fixed", APPROVED_SITE_STYLES)

    def test_catalog_covers_are_centered_and_statuses_are_neutral(self) -> None:
        self.assertIn("margin-inline: auto;", APPROVED_SITE_STYLES)
        self.assertIn(".catalog-book-info { min-width: 0; padding-top: 18px; text-align: center; }", APPROVED_SITE_STYLES)
        self.assertIn(".book-language { justify-content: center;", APPROVED_SITE_STYLES)
        self.assertIn(".status-queued, .status-processing, .status-done", APPROVED_SITE_STYLES)

    def test_upload_page_omits_internal_scanner_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = App(Path(__file__).resolve().parents[1], Path(temp_dir) / "data")
            payload = page(app)
        self.assertNotIn("Проверка VirusTotal перед обработкой".encode(), payload)

    def test_done_job_uses_an_accessible_icon_instead_of_colored_text_badge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app = App(Path(__file__).resolve().parents[1], root / "data")
            source = root / "book.epub"
            result = root / "book-ru.epub"
            source.write_bytes(b"source")
            result.write_bytes(b"translation")
            app.store.add("book", source.name, source, len(b"source"))
            app.store.finish("book", result)
            markup = webapp_module.job_markup(app, app.store.get("book"))
        self.assertIn('aria-label="Готово"', markup)
        self.assertIn("check-circle.svg", markup)
        self.assertNotIn(">Готово<", markup)

    def test_job_progress_alignment_and_status_icon_contrast_are_stable(self) -> None:
        self.assertIn("minmax(190px, 220px)", APPROVED_SITE_STYLES)
        self.assertIn(".status img { width: 15px; height: 15px; filter:", APPROVED_SITE_STYLES)

    def test_lamp_toggle_is_accessible_on_both_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = App(Path(__file__).resolve().parents[1], Path(temp_dir) / "data")
            upload = page(app)
            library = webapp_module.library_page(app)
        for payload in (upload, library):
            self.assertEqual(payload.count(b'class="lamp-toggle"'), 1)
            self.assertIn(b'aria-pressed="true"', payload)
            self.assertIn('aria-label="Выключить лампу"'.encode(), payload)
            self.assertIn(b"lamp-flicker-off", payload)
            self.assertIn(b'addEventListener("pointerdown"', payload)
            self.assertIn(b"window.setTimeout(() => setLampState(false), 1200);", payload)
            self.assertIn(b'window.addEventListener("load", scheduleAutoOff, { once: true });', payload)

    def test_lamp_and_main_atmosphere_have_desktop_states(self) -> None:
        self.assertIn(".library-app::before", APPROVED_SITE_STYLES)
        self.assertIn(".library-app::after", APPROVED_SITE_STYLES)
        self.assertIn("position: fixed;", APPROVED_SITE_STYLES)
        self.assertIn("library-interior-wide.webp", APPROVED_SITE_STYLES)
        self.assertIn("background-size: cover, 720px 720px;", APPROVED_SITE_STYLES)
        self.assertIn(".lamp-toggle", APPROVED_SITE_STYLES)
        self.assertIn("@keyframes lamp-flicker-off", APPROVED_SITE_STYLES)
        self.assertIn("@keyframes lamp-flicker-on", APPROVED_SITE_STYLES)
        self.assertIn(".lamp-toggle { display: none; }", APPROVED_SITE_STYLES)
        self.assertIn('.lamp-toggle[data-pointer-focus="true"]:focus-visible { outline: none; }', APPROVED_SITE_STYLES)
        self.assertNotIn("background-attachment: fixed", APPROVED_SITE_STYLES)

    def test_every_sixteenth_manual_lamp_toggle_triggers_easter_egg(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = App(Path(__file__).resolve().parents[1], Path(temp_dir) / "data")
            upload = page(app)
            library = webapp_module.library_page(app)
        for payload in (upload, library):
            self.assertEqual(payload.count(b'class="lamp-easter-egg-message"'), 1)
            self.assertIn("Многие упорны в отношении однажды избранного пути".encode(), payload)
            self.assertIn("Фридрих Ницше".encode(), payload)
            self.assertNotIn("Хватит тыркать".encode(), payload)
            self.assertIn(b'role="dialog" aria-labelledby="lamp-quote-text"', payload)
            self.assertIn(b'class="lamp-easter-egg-close"', payload)
            self.assertIn('aria-label="Закрыть цитату"'.encode(), payload)
            self.assertIn(b"let manualToggleCount = 0;", payload)
            self.assertIn(b"manualToggleCount += 1;", payload)
            self.assertIn(b"manualToggleCount % 16 === 0", payload)
            self.assertIn(b"triggerEasterEgg();", payload)
            self.assertIn(b'const dismissEasterEgg = () => {', payload)
            self.assertIn(b'closeEasterEgg.addEventListener("click", dismissEasterEgg);', payload)
            self.assertNotIn(b'document.addEventListener("click", dismissEasterEgg', payload)
            self.assertNotIn(b"}, 4200);", payload)
        self.assertIn(".lamp-easter-egg-active", APPROVED_SITE_STYLES)
        self.assertIn("background-color: rgba(5, 12, 10, .92);", APPROVED_SITE_STYLES)
        self.assertIn("@keyframes library-awakens-background", APPROVED_SITE_STYLES)
        self.assertIn("@keyframes lamp-easter-egg-message", APPROVED_SITE_STYLES)
        self.assertIn("@keyframes book-awakens", APPROVED_SITE_STYLES)

    def test_atmosphere_overlays_reveal_more_background_detail(self) -> None:
        self.assertIn("background: rgba(1, 6, 5, .43);", APPROVED_SITE_STYLES)
        self.assertIn("background: rgba(1, 6, 5, .28);", APPROVED_SITE_STYLES)
        self.assertIn(".app-navigation.lamp-is-off::after { opacity: .66; }", APPROVED_SITE_STYLES)

    def test_mobile_crest_taps_trigger_repeatable_easter_egg(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = App(Path(__file__).resolve().parents[1], Path(temp_dir) / "data")
            upload = page(app)
            library = webapp_module.library_page(app)
        for payload in (upload, library):
            self.assertEqual(payload.count(b'class="mobile-crest-toggle"'), 1)
            self.assertIn('aria-label="Разбудить библиотеку"'.encode(), payload)
            self.assertIn(b"let mobileTapCount = 0;", payload)
            self.assertIn(b"mobileTapCount >= 7", payload)
            self.assertIn(b"window.setTimeout(resetMobileTaps, 3000);", payload)
            self.assertIn(b'if (!window.matchMedia("(max-width: 640px)").matches) return;', payload)
            self.assertNotIn(b'if (window.matchMedia("(max-width: 640px)").matches) {', payload)
            self.assertIn(b"mobileEasterEggActive", payload)
        self.assertIn(".mobile-easter-egg-active", APPROVED_SITE_STYLES)
        self.assertIn("@keyframes mobile-book-awakens", APPROVED_SITE_STYLES)
        self.assertIn("@keyframes mobile-easter-egg-message", APPROVED_SITE_STYLES)

    def test_mobile_catalog_controls_can_shrink_without_horizontal_clipping(self) -> None:
        self.assertIn(".app-navigation nav { position: relative; z-index: 1; display: grid; gap: 10px; min-width: 0; }", APPROVED_SITE_STYLES)
        self.assertIn(".catalog-book-info { min-width: 0; padding-top: 18px; text-align: center; }", APPROVED_SITE_STYLES)
        self.assertIn(".nav-link > span:not(.nav-count) { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }", APPROVED_SITE_STYLES)
        self.assertIn(".book-downloads .button > span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }", APPROVED_SITE_STYLES)
        self.assertIn("overflow-wrap: anywhere;", APPROVED_SITE_STYLES)


class WebAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.scanner = AcceptScanner()
        self.app = App(Path(__file__).resolve().parents[1], root / "data", scanner=self.scanner)
        self.server = WebServer(("127.0.0.1", 0), self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def request(self, method: str, path: str, body: bytes = b"", content_type: str | None = None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port)
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
            headers["Content-Length"] = str(len(body))
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        connection.close()
        return response, payload

    def test_public_page_and_empty_page(self) -> None:
        response, payload = self.request("GET", "/")
        self.assertEqual(response.status, 200)
        self.assertIn("Файлов пока нет".encode(), payload)
        self.assertIn("name=\"source_language\"".encode(), payload)
        self.assertIn("<option value=\"en\" selected>English</option>".encode(), payload)
        self.assertIn("name=\"target_language\"".encode(), payload)
        self.assertIn("<option value=\"ru\" selected>Русский</option>".encode(), payload)
        self.assertIn("до 30 MB".encode(), payload)
        self.assertIn("Как работает перевод".encode(), payload)
        self.assertIn("id=\"file-feedback\"".encode(), payload)

    def test_public_page_uses_approved_library_design(self) -> None:
        response, payload = self.request("GET", "/")
        self.assertEqual(response.status, 200)
        self.assertIn(b'class="library-app upload-app"', payload)
        self.assertIn(b"/assets/atmosphere/translate-book-crest.webp", payload)
        self.assertIn(b"assets/atmosphere/library-sidebar-study.webp", payload)
        self.assertIn("Текущие загрузки".encode(), payload)
        self.assertNotIn("Последние задачи".encode(), payload)
        self.assertIn(b'name="source_language"', payload)
        self.assertIn(b'name="target_language"', payload)

    def test_static_design_asset_is_served_and_traversal_is_rejected(self) -> None:
        response, payload = self.request("GET", "/assets/atmosphere/translate-book-crest.webp")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "image/webp")
        self.assertTrue(payload)

        response, _ = self.request("GET", "/assets/../app.py")
        self.assertEqual(response.status, 404)

    def test_library_is_public_and_empty(self) -> None:
        response, payload = self.request("GET", "/library")
        self.assertEqual(response.status, 200)
        self.assertIn("Публичный каталог".encode(), payload)
        self.assertIn("Переведённых книг пока нет".encode(), payload)

    def test_upload_creates_queued_job(self) -> None:
        boundary = "----translate-book-" + uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="book"; filename="sample.epub"\r\n'
            "Content-Type: application/epub+zip\r\n\r\n"
        ).encode() + valid_epub() + f"\r\n--{boundary}--\r\n".encode()
        response, _ = self.request("POST", "/upload", body, f"multipart/form-data; boundary={boundary}")
        self.assertEqual(response.status, 303)
        jobs = self.app.store.list()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["status"], "queued")
        self.assertEqual(jobs[0]["source_code"], "en")
        self.assertEqual(jobs[0]["source_language"], "English")
        self.assertEqual(jobs[0]["target_code"], "ru")
        self.assertEqual(jobs[0]["target_language"], "Русский")
        self.assertTrue(Path(jobs[0]["source_path"]).is_file())
        self.assertEqual(self.scanner.calls[0][0], "sample.epub")

    def test_upload_persists_selected_language(self) -> None:
        boundary = "----translate-book-" + uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="source_language"\r\n\r\n'
            "fr\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="target_language"\r\n\r\n'
            "de\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="book"; filename="sample.epub"\r\n'
            "Content-Type: application/epub+zip\r\n\r\n"
        ).encode() + valid_epub() + f"\r\n--{boundary}--\r\n".encode()
        response, _ = self.request("POST", "/upload", body, f"multipart/form-data; boundary={boundary}")
        self.assertEqual(response.status, 303)
        job = self.app.store.list()[0]
        self.assertEqual(job["source_code"], "fr")
        self.assertEqual(job["source_language"], "Français")
        self.assertEqual(job["target_code"], "de")
        self.assertEqual(job["target_language"], "Deutsch")

    def test_progress_is_shown_for_translated_chunks(self) -> None:
        job_id = uuid.uuid4().hex
        job_dir = self.app.store.jobs_dir / job_id
        temp_dir = job_dir / "work" / "source_temp"
        temp_dir.mkdir(parents=True)
        (temp_dir / "chunk0001.md").write_text("one", encoding="utf-8")
        (temp_dir / "chunk0002.md").write_text("two", encoding="utf-8")
        (temp_dir / "output_chunk0001.md").write_text("translated", encoding="utf-8")
        source = job_dir / "source.epub"
        source.write_bytes(b"source")
        self.app.store.add(job_id, "source.epub", source, 6)
        job = self.app.store.get(job_id)
        self.assertEqual(self.app.store.progress(job), (1, 2))
        self.assertIn("50.0% (1/2)".encode(), page(self.app))

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

    def test_done_job_original_can_be_downloaded(self) -> None:
        job_id = uuid.uuid4().hex
        job_dir = self.app.store.jobs_dir / job_id
        job_dir.mkdir(parents=True)
        result = job_dir / "translated-book.zip"
        result.write_bytes(b"zip")
        source = job_dir / "source.epub"
        source.write_bytes(b"source")
        self.app.store.add(job_id, "source.epub", source, 6)
        self.app.store.finish(job_id, result)
        response, payload = self.request("GET", f"/download/{job_id}/original")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "application/epub+zip")
        self.assertIn("source.epub", response.getheader("Content-Disposition"))
        self.assertEqual(payload, b"source")

    def test_done_job_appears_in_public_library(self) -> None:
        job_id = uuid.uuid4().hex
        job_dir = self.app.store.jobs_dir / job_id
        job_dir.mkdir(parents=True)
        result = job_dir / "translated-book.zip"
        result.write_bytes(b"zip")
        source = job_dir / "source.epub"
        source.write_bytes(b"source")
        self.app.store.add(job_id, "source.epub", source, 6)
        self.app.store.finish(job_id, result)
        response, payload = self.request("GET", "/library")
        self.assertEqual(response.status, 200)
        self.assertIn(b"source.epub", payload)
        self.assertIn(f"/download/{job_id}/original".encode(), payload)
        self.assertIn(f"/download/{job_id}/translated".encode(), payload)
        self.assertIn("Скачать оригинал · English".encode(), payload)
        self.assertIn("Скачать перевод · Русский".encode(), payload)

    def test_done_job_uses_one_of_twenty_material_cover_themes(self) -> None:
        job_id = "0123456789abcdef0123456789abcdef"
        job_dir = self.app.store.jobs_dir / job_id
        job_dir.mkdir(parents=True)
        result = job_dir / "translated-book.zip"
        result.write_bytes(b"zip")
        source = job_dir / "A Thoughtful Book.epub"
        source.write_bytes(b"source")
        self.app.store.add(job_id, "A Thoughtful Book.epub", source, 6)
        self.app.store.finish(job_id, result)

        response, payload = self.request("GET", "/library")
        self.assertEqual(response.status, 200)
        self.assertIn(b'class="book-cover cover-theme-3"', payload)
        for index in range(20):
            self.assertIn(f".cover-theme-{index}".encode(), payload)
        self.assertIn(f"/download/{job_id}/original".encode(), payload)
        self.assertIn(f"/download/{job_id}/translated".encode(), payload)

    def test_upload_rejects_zip_bomb_metadata_before_scanner(self) -> None:
        boundary = "----translate-book-" + uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="book"; filename="bomb.epub"\r\n'
            "Content-Type: application/epub+zip\r\n\r\n"
        ).encode() + zip_bomb_metadata() + f"\r\n--{boundary}--\r\n".encode()
        response, _ = self.request("POST", "/upload", body, f"multipart/form-data; boundary={boundary}")
        self.assertEqual(response.status, 400)
        self.assertEqual(self.scanner.calls, [])
        self.assertEqual(self.app.store.list(), [])

    def test_upload_rejects_when_virustotal_finds_threat(self) -> None:
        self.app.scanner = AcceptScanner(UploadSecurityError("VirusTotal обнаружил угрозу в файле."))
        boundary = "----translate-book-" + uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="book"; filename="sample.epub"\r\n'
            "Content-Type: application/epub+zip\r\n\r\n"
        ).encode() + valid_epub() + f"\r\n--{boundary}--\r\n".encode()
        response, _ = self.request("POST", "/upload", body, f"multipart/form-data; boundary={boundary}")
        self.assertEqual(response.status, 422)
        self.assertEqual(self.app.store.list(), [])

    def test_upload_rejects_when_virustotal_is_not_configured(self) -> None:
        self.app.scanner = None
        boundary = "----translate-book-" + uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="book"; filename="sample.epub"\r\n'
            "Content-Type: application/epub+zip\r\n\r\n"
        ).encode() + valid_epub() + f"\r\n--{boundary}--\r\n".encode()
        response, _ = self.request("POST", "/upload", body, f"multipart/form-data; boundary={boundary}")
        self.assertEqual(response.status, 503)
        self.assertEqual(self.app.store.list(), [])

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
        store = Store(data_dir)
        with store.connect() as db:
            columns = {row["name"] for row in db.execute("PRAGMA table_info(jobs)")}
        self.assertIn("target_code", columns)
        self.assertIn("target_language", columns)
        self.assertIn("source_code", columns)
        self.assertIn("source_language", columns)


def valid_epub() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("OEBPS/content.xhtml", "<html/>")
    return buffer.getvalue()


def zip_bomb_metadata() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("bomb.bin", b"\0" * (2 * 1024 * 1024), compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
