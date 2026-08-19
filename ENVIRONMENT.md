# Translate Book Web Environment

- Runtime: Python 3.12 virtual environment at `.venv/`.
- Service: `translate-book-web.service`.
- Bind: `0.0.0.0:3100`.
- Persistent data: `/root/projects/translate-book-web/data/`.
- Required tools: `codex`, `ebook-convert` from Calibre, and `pandoc`.
- Queue: SQLite-backed, one book worker at a time.

The web application is public. VirusTotal credentials are loaded from the shared root-owned environment file configured in the systemd unit; they must not be committed.
