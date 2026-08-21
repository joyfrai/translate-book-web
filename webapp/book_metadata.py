from __future__ import annotations

import json
import re
from pathlib import Path


UNKNOWN_AUTHOR = "Автор не указан"
TRANSLATED_METADATA_FILENAME = "translated_metadata.json"


def _clean(value: str, *, replace_underscores: bool = False) -> str:
    if replace_underscores:
        value = value.replace("_", " ")
    return re.sub(r"\s+", " ", value).strip(" ._-—–")


def filename_book_metadata(original_name: str) -> tuple[str, str]:
    """Return a readable title/author fallback from an uploaded filename.

    The supported convention is ``Author - Title``. Embedded book metadata
    takes precedence whenever the conversion pipeline provides it.
    """
    stem = Path(original_name).stem
    readable = _clean(stem, replace_underscores=True)
    match = re.match(r"^(?P<author>.+?)\s+[-–—]\s+(?P<title>.+)$", readable)
    if match:
        return _clean(match.group("title")), _clean(match.group("author"))
    return readable or "Без названия", UNKNOWN_AUTHOR


def translated_book_metadata(job_dir: Path, source_path: Path) -> tuple[str | None, str | None]:
    """Read optional translated title/author generated during the first chunk."""
    metadata_path = job_dir / "work" / f"{source_path.stem}_temp" / TRANSLATED_METADATA_FILENAME
    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, None
    if not isinstance(data, dict):
        return None, None
    title = _clean(data.get("title", "")) if isinstance(data.get("title"), str) else None
    author = _clean(data.get("author", "")) if isinstance(data.get("author"), str) else None
    return title or None, author or None


def pipeline_book_metadata(job_dir: Path, source_path: Path, original_name: str) -> tuple[str, str]:
    """Read title/creator written by scripts/convert.py, with filename fallback."""
    fallback_title, fallback_author = filename_book_metadata(original_name)
    config_path = job_dir / "work" / f"{source_path.stem}_temp" / "config.txt"
    metadata: dict[str, str] = {}
    try:
        for line in config_path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key in {"original_title", "creator"}:
                metadata[key] = _clean(value)
    except (OSError, UnicodeError):
        pass
    translated_title, translated_author = translated_book_metadata(job_dir, source_path)
    return (
        translated_title or metadata.get("original_title") or fallback_title,
        translated_author or metadata.get("creator") or fallback_author,
    )
