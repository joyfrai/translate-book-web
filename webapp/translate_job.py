from __future__ import annotations

import concurrent.futures
import re
import subprocess
import sys
import zipfile
from pathlib import Path


TARGET_LANGUAGE = "Russian"
TARGET_CODE = "ru"
MAX_TRANSLATORS = 8


def run_logged(command: list[str], cwd: Path, log_path: Path, timeout: int | None = None) -> None:
    with log_path.open("ab") as log:
        log.write(("\n$ " + " ".join(command) + "\n").encode())
        result = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}); see {log_path}")


def translate_chunk(repo_root: Path, temp_dir: Path, source: Path, output: Path, log_path: Path) -> None:
    prompt = f"""Translate exactly one Markdown book chunk from English to {TARGET_LANGUAGE}.
Read source file: {source}
Write the complete translation to: {output}
Rules: preserve Markdown structure, links, images, code and paragraph order; translate only readable English text; do not summarize, omit, add commentary, or touch any other files. The output file must be UTF-8 and non-empty."""
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
        prompt,
    ]
    run_logged(command, repo_root, log_path, timeout=1800)
    if not output.is_file() or not output.read_text(encoding="utf-8").strip():
        raise RuntimeError(f"empty translation output: {output.name}")


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
    with zipfile.ZipFile(result_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in available:
            archive.write(path, path.name)


def run_translation(repo_root: Path, job_dir: Path, source_path: Path) -> Path:
    scripts_dir = repo_root / "scripts"
    work_root = job_dir / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    log_path = job_dir / "pipeline.log"
    convert = [sys.executable, str(scripts_dir / "convert.py"), str(source_path), "--olang", TARGET_CODE, "--temp-root", str(work_root)]
    run_logged(convert, repo_root, log_path, timeout=1800)
    temp_dir = work_root / f"{source_path.stem}_temp"
    if not temp_dir.is_dir():
        raise RuntimeError("translate-book conversion did not create a work directory")
    chunks = _source_chunks(temp_dir)
    if not chunks:
        raise RuntimeError("translate-book conversion produced no chunks")

    def process(source: Path) -> None:
        output = source.with_name("output_" + source.name)
        if output.is_file() and output.read_text(encoding="utf-8").strip():
            return
        chunk_log = job_dir / f"{source.stem}.log"
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                translate_chunk(repo_root, temp_dir, source, output, chunk_log)
                return
            except Exception as exc:
                last_error = exc
        raise RuntimeError(str(last_error))

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_TRANSLATORS) as pool:
        errors = [future.exception() for future in concurrent.futures.as_completed([pool.submit(process, chunk) for chunk in chunks]) if future.exception()]
    if errors:
        raise RuntimeError(f"{len(errors)} chunk(s) failed; see pipeline.log and chunk logs")

    build = [sys.executable, str(scripts_dir / "merge_and_build.py"), "--temp-dir", str(temp_dir), "--lang", TARGET_CODE]
    run_logged(build, repo_root, log_path, timeout=1800)
    result_path = job_dir / "translated-book.zip"
    _build_zip(temp_dir, result_path)
    return result_path
