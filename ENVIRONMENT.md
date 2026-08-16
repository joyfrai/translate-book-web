# Translate Book Web Environment

- Runtime: Python 3.12 virtual environment at `.venv/`.
- Service: `translate-book-web.service`.
- Bind: `0.0.0.0:3100`.
- Persistent data: `/root/projects/translate-book-web/data/`.
- Required tools: `codex`, `ebook-convert` from Calibre, and `pandoc`.
- Queue: SQLite-backed, one book worker at a time.

The Basic Auth password is loaded from the untracked `.env` file. It must not be committed.
