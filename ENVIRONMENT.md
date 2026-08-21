# Translate Book Web Environment

- Runtime: Python 3.12 virtual environment at `.venv/`.
- Service: `translate-book-web.service`.
- Bind: `127.0.0.1:3100` (nginx public route: `https://yagix.ru/translatebook/`).
- Persistent data: `/root/projects/translate-book-web/data/`.
- Required tools: `codex`, `ebook-convert` from Calibre, and `pandoc`.
- Service user: `translatebook` (non-root).
- Runtime home: `/var/lib/translate-book-web`; Codex auth: `/var/lib/translate-book-web/.codex` via `CODEX_HOME`.
- Queue: SQLite-backed FIFO queue, one book worker at a time; additional jobs wait in `queued`.
- Per-book translation concurrency: `MAX_TRANSLATORS=2`.
- `AF_NETLINK` is allowed in the systemd unit because Codex Bubblewrap needs it for its network namespace.

The web application is public. VirusTotal credentials are loaded from the shared root-owned environment file configured in the systemd unit; they must not be committed.
