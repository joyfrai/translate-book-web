from __future__ import annotations

import concurrent.futures
import json
import logging
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from .book_metadata import TRANSLATED_METADATA_FILENAME, pipeline_book_metadata, translated_book_metadata


SUPPORTED_LANGUAGES = {
    "ru": "Русский",
    "en": "English",
    "zh": "中文",
    "ja": "日本語",
    "ko": "한국어",
    "fr": "Français",
    "de": "Deutsch",
    "es": "Español",
}
SOURCE_LANGUAGES = {"auto": "Автоопределение", **SUPPORTED_LANGUAGES}
DEFAULT_SOURCE_CODE = "en"
DEFAULT_SOURCE_LANGUAGE = SUPPORTED_LANGUAGES[DEFAULT_SOURCE_CODE]
DEFAULT_TARGET_CODE = "ru"
DEFAULT_TARGET_LANGUAGE = SUPPORTED_LANGUAGES[DEFAULT_TARGET_CODE]
MAX_TRANSLATORS = 2
CODEX_REQUEST_RE = re.compile(r"(?m)^\$ codex exec(?:\s|$)")
LOGGER = logging.getLogger(__name__)


def _log_name(path: Path) -> str:
    return path.name.replace("\n", "\\n").replace("\r", "\\r")


def collect_translation_usage(job_dir: Path) -> tuple[int, int]:
    """Read measured Codex request/token usage from JSONL chunk logs."""
    requests = 0
    tokens = 0
    for log_path in job_dir.glob("chunk*.log"):
        text = log_path.read_text(encoding="utf-8", errors="ignore")
        requests += len(CODEX_REQUEST_RE.findall(text))
        turn_usage = []
        response_usage = []
        for line in text.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            usage = event.get("usage")
            if not isinstance(usage, dict):
                response = event.get("response")
                usage = response.get("usage") if isinstance(response, dict) else None
            if not isinstance(usage, dict):
                continue
            if event.get("type") == "turn.completed":
                turn_usage.append(usage)
            elif event.get("type") == "response.completed":
                response_usage.append(usage)
        for usage in turn_usage or response_usage:
            total = usage.get("total_tokens")
            if isinstance(total, int):
                tokens += total
                continue
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                tokens += input_tokens + output_tokens
    return requests, tokens


def run_logged(command: list[str], cwd: Path, log_path: Path, timeout: int | None = None, *, stage: str = "command") -> None:
    command_name = Path(command[0]).name if command else "unknown"
    started_at = time.monotonic()
    LOGGER.info("pipeline_command_started stage=%s command=%s log=%s timeout_seconds=%s", stage, command_name, _log_name(log_path), timeout)
    with log_path.open("ab") as log:
        log.write(("\n$ " + " ".join(command) + "\n").encode())
        try:
            result = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired:
            LOGGER.exception("pipeline_command_timed_out stage=%s command=%s duration_seconds=%.1f", stage, command_name, time.monotonic() - started_at)
            raise
        except Exception:
            LOGGER.exception("pipeline_command_failed_to_start stage=%s command=%s duration_seconds=%.1f", stage, command_name, time.monotonic() - started_at)
            raise
    if result.returncode:
        LOGGER.error("pipeline_command_failed stage=%s command=%s return_code=%d duration_seconds=%.1f log=%s", stage, command_name, result.returncode, time.monotonic() - started_at, _log_name(log_path))
        raise RuntimeError(f"command failed ({result.returncode}); see {log_path}")
    LOGGER.info("pipeline_command_succeeded stage=%s command=%s duration_seconds=%.1f log=%s", stage, command_name, time.monotonic() - started_at, _log_name(log_path))


def translate_chunk(
    repo_root: Path,
    temp_dir: Path,
    source: Path,
    output: Path,
    log_path: Path,
    source_language: str,
    target_language: str,
    metadata_path: Path | None = None,
    metadata_title: str | None = None,
    metadata_author: str | None = None,
) -> None:
    source_label = "the detected source language" if source_language == SOURCE_LANGUAGES["auto"] else source_language
    chunk_name = _log_name(source)
    LOGGER.info("translation_chunk_started chunk=%s source_language=%s target_language=%s", chunk_name, source_language, target_language)
    metadata_instruction = ""
    if metadata_path is not None and metadata_title is not None and metadata_author is not None:
        metadata_instruction = f"\nAlso write UTF-8 JSON to {metadata_path} with exactly these keys: title and author. Translate the book title \"{metadata_title}\" into {target_language}; translate or naturally transliterate the author \"{metadata_author}\" into {target_language}. Do not add any other keys."
    prompt = f"""Translate exactly one Markdown book chunk from {source_label} to {target_language}.
Read source file: {source}
Write the complete translation to: {output}
Rules: preserve Markdown structure, links, images, code and paragraph order; translate only readable English text; do not summarize, omit, add commentary, or touch any other files except the designated metadata JSON file below. The output file must be UTF-8 and non-empty.{metadata_instruction}"""
    command = [
        "codex",
        "exec",
        "--add-dir",
        str(temp_dir),
        "--approve-for-me",
        "--skip-git-repo-check",
        "--ephemeral",
        "--color",
        "never",
        "--json",
        prompt,
    ]
    run_logged(command, repo_root, log_path, timeout=1800, stage="translate_chunk")
    if not output.is_file() or not output.read_text(encoding="utf-8").strip():
        LOGGER.error("translation_chunk_empty_output chunk=%s output=%s", chunk_name, _log_name(output))
        raise RuntimeError(f"empty translation output: {output.name}")
    LOGGER.info("translation_chunk_succeeded chunk=%s output=%s output_bytes=%d", chunk_name, _log_name(output), output.stat().st_size)


def _chunk_number(path: Path) -> int:
    match = re.search(r"(\d+)$", path.stem)
    return int(match.group(1)) if match else 0


def _source_chunks(temp_dir: Path) -> list[Path]:
    return sorted((path for path in temp_dir.glob("chunk*.md") if not path.name.startswith("output_")), key=_chunk_number)


def _build_zip(temp_dir: Path, result_path: Path) -> None:
    names = ["book.epub", "book.pdf", "book.docx", "book.html", "book_doc.html", "output.md"]
    available = [temp_dir / name for name in names if (temp_dir / name).is_file()]
    if not available:
        raise RuntimeError("translate-book produced no downloadable output")
    LOGGER.info("translation_archive_started result=%s files=%s", _log_name(result_path), ",".join(_log_name(path) for path in available))
    with zipfile.ZipFile(result_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in available:
            archive.write(path, path.name)
    LOGGER.info("translation_archive_succeeded result=%s files=%d size_bytes=%d", _log_name(result_path), len(available), result_path.stat().st_size)


def run_translation(
    repo_root: Path,
    job_dir: Path,
    source_path: Path,
    target_code: str = DEFAULT_TARGET_CODE,
    target_language: str = DEFAULT_TARGET_LANGUAGE,
    source_code: str = DEFAULT_SOURCE_CODE,
    source_language: str = DEFAULT_SOURCE_LANGUAGE,
) -> Path:
    job_id = _log_name(job_dir)
    LOGGER.info("translation_started job_id=%s source=%s source_language=%s target_language=%s", job_id, _log_name(source_path), source_language, target_language)
    scripts_dir = repo_root / "scripts"
    work_root = job_dir / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    log_path = job_dir / "pipeline.log"
    convert = [
        sys.executable,
        str(scripts_dir / "convert.py"),
        str(source_path),
        "--ilang",
        source_code,
        "--olang",
        target_code,
        "--temp-root",
        str(work_root),
    ]
    run_logged(convert, repo_root, log_path, timeout=1800, stage="convert")
    temp_dir = work_root / f"{source_path.stem}_temp"
    if not temp_dir.is_dir():
        raise RuntimeError("translate-book conversion did not create a work directory")
    chunks = _source_chunks(temp_dir)
    if not chunks:
        LOGGER.error("translation_chunks_missing job_id=%s temp_dir=%s", job_id, _log_name(temp_dir))
        raise RuntimeError("translate-book conversion produced no chunks")
    LOGGER.info("translation_conversion_succeeded job_id=%s temp_dir=%s chunks=%d", job_id, _log_name(temp_dir), len(chunks))
    filename_title, filename_author = pipeline_book_metadata(job_dir, source_path, source_path.name)

    def process(source: Path) -> None:
        output = source.with_name("output_" + source.name)
        existing_title, existing_author = translated_book_metadata(job_dir, source_path)
        metadata_needed = source == chunks[0] and not (existing_title and existing_author)
        if output.is_file() and output.read_text(encoding="utf-8").strip() and not metadata_needed:
            LOGGER.info("translation_chunk_skipped_existing chunk=%s output=%s", _log_name(source), _log_name(output))
            return
        chunk_log = job_dir / f"{source.stem}.log"
        last_error: Exception | None = None
        for attempt in range(1, 3):
            try:
                LOGGER.info("translation_chunk_attempt_started job_id=%s chunk=%s attempt=%d/2", job_id, _log_name(source), attempt)
                translate_chunk(
                    repo_root,
                    temp_dir,
                    source,
                    output,
                    chunk_log,
                    source_language,
                    target_language,
                    metadata_path=temp_dir / TRANSLATED_METADATA_FILENAME if source == chunks[0] else None,
                    metadata_title=filename_title,
                    metadata_author=filename_author,
                )
                return
            except Exception as exc:
                last_error = exc
                LOGGER.warning("translation_chunk_attempt_failed job_id=%s chunk=%s attempt=%d/2 error=%s", job_id, _log_name(source), attempt, exc)
        raise RuntimeError(str(last_error))

    LOGGER.info("translation_chunks_started job_id=%s chunks=%d workers=%d", job_id, len(chunks), MAX_TRANSLATORS)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_TRANSLATORS) as pool:
        errors = [future.exception() for future in concurrent.futures.as_completed([pool.submit(process, chunk) for chunk in chunks]) if future.exception()]
    if errors:
        LOGGER.error("translation_chunks_failed job_id=%s failed_chunks=%d", job_id, len(errors))
        raise RuntimeError(f"{len(errors)} chunk(s) failed; see pipeline.log and chunk logs")
    LOGGER.info("translation_chunks_succeeded job_id=%s chunks=%d", job_id, len(chunks))

    translated_title, translated_author = translated_book_metadata(job_dir, source_path)
    build = [sys.executable, str(scripts_dir / "merge_and_build.py"), "--temp-dir", str(temp_dir), "--lang", target_code]
    if translated_title:
        build.extend(["--title", translated_title])
    if translated_author:
        build.extend(["--author", translated_author])
    run_logged(build, repo_root, log_path, timeout=1800, stage="merge_and_build")
    LOGGER.info("translation_build_succeeded job_id=%s temp_dir=%s", job_id, _log_name(temp_dir))
    result_path = job_dir / "translated-book.zip"
    _build_zip(temp_dir, result_path)
    LOGGER.info("translation_succeeded job_id=%s result=%s", job_id, _log_name(result_path))
    return result_path
