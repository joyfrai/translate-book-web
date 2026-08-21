from __future__ import annotations

import io
import json
import os
import unittest
import zipfile
from unittest.mock import patch

from webapp.security import (
    UploadSecurityError,
    VirusTotalError,
    VirusTotalScanner,
    validate_payload,
)


def epub_payload() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("OEBPS/content.xhtml", "<html/>")
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.payload


class SecurityTests(unittest.TestCase):
    def test_validate_payload_rejects_zip_slip_path(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../outside.txt", "unsafe")
        with self.assertRaises(UploadSecurityError):
            validate_payload("book.epub", buffer.getvalue())

    def test_validate_payload_rejects_fake_pdf(self) -> None:
        with self.assertRaises(UploadSecurityError):
            validate_payload("book.pdf", b"not a pdf")

    def test_virustotal_scanner_uploads_and_polls_to_clean_verdict(self) -> None:
        responses = [
            FakeResponse({"data": {"type": "analysis", "id": "analysis-1"}}),
            FakeResponse({"data": {"attributes": {"status": "completed", "stats": {"malicious": 0, "suspicious": 0}}}}),
        ]
        scanner = VirusTotalScanner("secret", poll_interval=0, max_polls=2)
        with patch("webapp.security.urllib.request.urlopen", side_effect=responses) as urlopen, self.assertLogs("webapp.security", level="INFO") as captured:
            verdict = scanner.scan("book.epub", epub_payload())
        self.assertEqual(verdict.analysis_id, "analysis-1")
        self.assertEqual(urlopen.call_count, 2)
        upload_request = urlopen.call_args_list[0].args[0]
        self.assertEqual(upload_request.get_header("X-apikey"), "secret")
        self.assertIn(b"filename=\"book.epub\"", upload_request.data)
        logs = "\n".join(captured.output)
        self.assertIn("virus_scan_started", logs)
        self.assertIn("virus_scan_submitted", logs)
        self.assertIn("virus_scan_poll", logs)
        self.assertIn("virus_scan_clean", logs)
        self.assertIn("malicious=0", logs)
        self.assertIn("suspicious=0", logs)
        self.assertNotIn("secret", logs)

    def test_virustotal_scanner_rejects_detection(self) -> None:
        responses = [
            FakeResponse({"data": {"id": "analysis-1"}}),
            FakeResponse({"data": {"attributes": {"status": "completed", "stats": {"malicious": 1, "suspicious": 0}}}}),
        ]
        scanner = VirusTotalScanner("secret", poll_interval=0, max_polls=2)
        with patch("webapp.security.urllib.request.urlopen", side_effect=responses):
            with self.assertRaises(UploadSecurityError):
                scanner.scan("book.epub", epub_payload())

    def test_virustotal_scanner_rejects_incomplete_completed_verdict(self) -> None:
        responses = [
            FakeResponse({"data": {"id": "analysis-1"}}),
            FakeResponse({"data": {"attributes": {"status": "completed", "stats": {}}}}),
        ]
        scanner = VirusTotalScanner("secret", poll_interval=0, max_polls=2)
        with patch("webapp.security.urllib.request.urlopen", side_effect=responses):
            with self.assertRaises(VirusTotalError):
                scanner.scan("book.epub", epub_payload())

    def test_virustotal_scanner_accepts_shared_joy_key_name(self) -> None:
        with patch.dict(os.environ, {"JOY_VT_API_KEY": "secret"}, clear=True):
            scanner = VirusTotalScanner.from_env()
        self.assertIsNotNone(scanner)


if __name__ == "__main__":
    unittest.main()
