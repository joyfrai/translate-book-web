from __future__ import annotations

import io
import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path


MAX_ARCHIVE_ENTRIES = 10_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 100.0
VIRUSTOTAL_API = "https://www.virustotal.com/api/v3"


class UploadSecurityError(ValueError):
    """The uploaded payload is unsafe or does not match its declared format."""


class VirusTotalError(RuntimeError):
    """VirusTotal could not produce a trustworthy verdict."""


def _zip_member_is_unsafe(name: str) -> bool:
    path = Path(name)
    return path.is_absolute() or ".." in path.parts or "\\" in name


def validate_payload(filename: str, payload: bytes) -> None:
    """Validate type and bounded archive metadata before persisting or scanning it."""
    extension = Path(filename).suffix.lower()
    if extension in {".epub", ".docx"}:
        if not zipfile.is_zipfile(io.BytesIO(payload)):
            raise UploadSecurityError("Файл не является корректным ZIP-контейнером.")
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                members = archive.infolist()
                if len(members) > MAX_ARCHIVE_ENTRIES:
                    raise UploadSecurityError("В архиве слишком много файлов.")
                total_uncompressed = 0
                total_compressed = 0
                for member in members:
                    if _zip_member_is_unsafe(member.filename):
                        raise UploadSecurityError("В архиве обнаружен небезопасный путь файла.")
                    if member.flag_bits & 0x1:
                        raise UploadSecurityError("Зашифрованные архивы не поддерживаются.")
                    if member.file_size < 0 or member.compress_size < 0:
                        raise UploadSecurityError("Архив содержит некорректные размеры файлов.")
                    total_uncompressed += member.file_size
                    total_compressed += member.compress_size
                    if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                        raise UploadSecurityError("Распакованный размер архива превышает безопасный лимит.")
                    if member.compress_size and member.file_size / member.compress_size > MAX_ARCHIVE_COMPRESSION_RATIO:
                        raise UploadSecurityError("Обнаружен подозрительно высокий коэффициент сжатия.")
                if total_compressed and total_uncompressed / total_compressed > MAX_ARCHIVE_COMPRESSION_RATIO:
                    raise UploadSecurityError("Обнаружен подозрительно высокий общий коэффициент сжатия.")
        except zipfile.BadZipFile as exc:
            raise UploadSecurityError("Файл содержит повреждённый ZIP-архив.") from exc
    elif extension == ".pdf":
        if not payload.startswith(b"%PDF-"):
            raise UploadSecurityError("Файл не похож на PDF.")


@dataclass(frozen=True)
class ScanVerdict:
    analysis_id: str
    status: str
    malicious: int
    suspicious: int


class VirusTotalScanner:
    def __init__(
        self,
        api_key: str,
        *,
        api_base: str = VIRUSTOTAL_API,
        timeout: float = 30.0,
        poll_interval: float = 2.0,
        max_polls: int = 30,
    ):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_polls = max_polls

    @classmethod
    def from_env(cls) -> "VirusTotalScanner | None":
        api_key = (os.getenv("VIRUSTOTAL_API_KEY") or os.getenv("JOY_VT_API_KEY") or "").strip()
        return cls(api_key) if api_key else None

    def _request(self, url: str, *, data: bytes | None = None, content_type: str | None = None) -> dict:
        headers = {"x-apikey": self.api_key, "Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise VirusTotalError("VirusTotal недоступен или вернул некорректный ответ.") from exc

    def _multipart(self, filename: str, payload: bytes) -> tuple[bytes, str]:
        boundary = f"----translate-book-{uuid.uuid4().hex}"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{Path(filename).name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8") + payload + f"\r\n--{boundary}--\r\n".encode("ascii")
        return body, f"multipart/form-data; boundary={boundary}"

    def scan(self, filename: str, payload: bytes) -> ScanVerdict:
        body, content_type = self._multipart(filename, payload)
        response = self._request(f"{self.api_base}/files", data=body, content_type=content_type)
        analysis_id = response.get("data", {}).get("id")
        if not analysis_id:
            raise VirusTotalError("VirusTotal не вернул идентификатор анализа.")
        analysis_url = f"{self.api_base}/analyses/{urllib.parse.quote(analysis_id, safe='')}"
        last_status = "queued"
        for attempt in range(self.max_polls):
            if attempt:
                time.sleep(self.poll_interval)
            analysis = self._request(analysis_url)
            attributes = analysis.get("data", {}).get("attributes", {})
            last_status = str(attributes.get("status", ""))
            if last_status == "completed":
                stats = attributes.get("stats", {})
                if not isinstance(stats, dict) or "malicious" not in stats or "suspicious" not in stats:
                    raise VirusTotalError("VirusTotal завершил анализ без полного verdict.")
                try:
                    malicious = int(stats["malicious"])
                    suspicious = int(stats["suspicious"])
                except (TypeError, ValueError) as exc:
                    raise VirusTotalError("VirusTotal вернул некорректный verdict.") from exc
                verdict = ScanVerdict(
                    analysis_id=analysis_id,
                    status=last_status,
                    malicious=malicious,
                    suspicious=suspicious,
                )
                if verdict.malicious or verdict.suspicious:
                    raise UploadSecurityError("VirusTotal обнаружил угрозу в файле.")
                return verdict
        raise VirusTotalError(f"VirusTotal не завершил проверку вовремя (status={last_status}).")
