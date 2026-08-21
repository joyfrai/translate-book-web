# Translate Book Library Redesign Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved library design to the current Python webapp while preserving upload, language, queue, security, and download behavior.

**Architecture:** Keep `webapp/app.py` as the server-rendered UI boundary and preserve all business handlers. Add only a restricted static-asset route, copy the approved local assets under `webapp/static`, and render stable presentational cover themes from the existing job ID.

**Tech Stack:** Python 3.12+, `http.server`, SQLite, server-rendered HTML/CSS, `unittest`.

---

### Task 1: Lock the current behavior and new visual contracts

**Files:**
- Modify: `tests/test_webapp.py`

- [ ] **Step 1: Add failing assertions**

Add tests that require the existing language selects and both download URLs, plus `cover-theme-0` through `cover-theme-19`, `app-navigation`, `book-downloads`, and `/assets/` references in rendered HTML.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python3 -m unittest tests.test_webapp.WebAppTests -v`

Expected: existing behavior tests pass while the new presentational assertions fail.

### Task 2: Add self-contained visual assets

**Files:**
- Create: `webapp/static/atmosphere/library-interior-wide.webp`
- Create: `webapp/static/atmosphere/library-sidebar-study.webp`
- Create: `webapp/static/atmosphere/translate-book-crest.webp`
- Create: `webapp/static/textures/aged-paper.webp`
- Create: `webapp/static/textures/book-cloth.webp`
- Create: `webapp/static/textures/leather-dark.webp`
- Create: `webapp/static/textures/linen-light.webp`
- Create: `webapp/static/textures/mottled-paper-dark.webp`
- Create: `webapp/static/fonts/cormorant-garamond-cyrillic-wght-normal.woff2`
- Modify: `webapp/app.py`
- Test: `tests/test_webapp.py`

- [ ] **Step 1: Copy the approved raster and font assets**

Copy only the listed files from the verified previous prototype into `webapp/static`.

- [ ] **Step 2: Serve assets safely**

Handle only `/assets/<relative path>`, resolve against `webapp/static`, reject paths outside that root, and return an allowlisted MIME type for `.webp` and `.woff2`.

- [ ] **Step 3: Test traversal rejection and successful asset delivery**

Run: `python3 -m unittest tests.test_webapp.WebAppTests -v`

Expected: static files return `200`; `../` traversal attempts return `404`; all existing tests remain green.

### Task 3: Rebuild the two server-rendered pages

**Files:**
- Modify: `webapp/app.py`
- Test: `tests/test_webapp.py`

- [ ] **Step 1: Replace the light CSS with the approved design system**

Implement the dark palette, local display font, textured backgrounds, sidebar/header navigation, upload workspace, progress rows, catalog grid, twenty cover themes, integrated spine lighting, stacked download buttons, focus states, and the `980px`, `760px`, and `640px` responsive layouts.

- [ ] **Step 2: Update shared navigation markup**

Use the crest image and accessible image-backed icons while retaining the existing `/` and `/library` links and active state.

- [ ] **Step 3: Update upload markup without changing form contracts**

Keep `action="/upload"`, `method="post"`, `enctype="multipart/form-data"`, file input constraints, both language select names/options, the submit button, and the file-selection script. Present the list as `Текущие загрузки` and keep real statuses/progress.

- [ ] **Step 4: Update library markup without changing download contracts**

Render only `list_finished()` rows, keep `/download/<id>/original` and `/download/<id>/translated`, and derive a stable `cover-theme-N` class from the job ID.

- [ ] **Step 5: Run focused and full tests**

Run: `python3 -m unittest tests.test_webapp.WebAppTests -v`

Run: `python3 -m unittest discover -s tests -v`

Expected: all tests pass.

### Task 4: Visual QA and replacement

**Files:**
- Create: `design-qa.md`
- Replace working tree: `work/source/book-translation-reader` with the verified contents of `work/incoming/translate-book-web`
- Create: `outputs/translate-book-web-redesigned-20260820.tar.gz`

- [ ] **Step 1: Start the new app with mock data**

Use an isolated temporary data directory containing processing and completed jobs so upload, progress, library covers, languages, and real download links can be inspected without production data.

- [ ] **Step 2: Capture desktop and mobile states**

Capture `/` and `/library` at desktop and mobile widths; inspect DOM, overflow, focusable controls, and browser console errors.

- [ ] **Step 3: Compare against the selected reference**

Create a side-by-side comparison with the approved reference image, fix every P0/P1/P2 issue, and write `design-qa.md` with `final result: passed`.

- [ ] **Step 4: Replace the old working copy**

Stop old preview processes, move the old tree to a temporary rollback location, move the verified new tree into the canonical source path, re-run the full test suite there, then delete the rollback directory.

- [ ] **Step 5: Package the installation archive**

Create `outputs/translate-book-web-redesigned-20260820.tar.gz` from the verified canonical source tree and keep the local preview running on port 3100.
