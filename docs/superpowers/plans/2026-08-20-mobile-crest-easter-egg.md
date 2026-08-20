# Mobile Crest Easter Egg Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repeatable mobile-only “books awaken” scene after seven rapid taps on the header crest, while preserving desktop lamp behavior and all backend flows.

**Architecture:** Extend the shared header with a mobile-only semantic hit target positioned over the existing crest. Reuse the existing quote markup and close button, add a self-resetting three-second tap counter in the shared interaction script, and scope all new visual behavior to the existing `max-width: 640px` media query.

**Tech Stack:** Python-rendered HTML, vanilla JavaScript, CSS media queries/keyframes, Python `unittest`, in-app browser QA.

**Repository note:** The extracted source has no `.git` directory, so worktree and commit steps are unavailable. Changes are applied directly and delivered in the rebuilt archive.

---

### Task 1: Lock the mobile interaction contract

**Files:**
- Modify: `tests/test_webapp.py`
- Test: `tests/test_webapp.py`

- [x] **Step 1: Add a failing presentation test**

Add `test_mobile_crest_taps_trigger_repeatable_easter_egg` to `PresentationTests`. Render `/` and `/library`, then require one `.mobile-crest-toggle`, the accessible label `Разбудить библиотеку`, `mobileTapCount`, the seven-tap threshold, a 3000 ms reset, `.mobile-easter-egg-active`, and the existing close-only behavior.

```python
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
        self.assertIn(b'mobileEasterEggActive', payload)
    self.assertIn(".mobile-easter-egg-active", APPROVED_SITE_STYLES)
    self.assertIn("@keyframes mobile-book-awakens", APPROVED_SITE_STYLES)
    self.assertIn("@keyframes mobile-easter-egg-message", APPROVED_SITE_STYLES)
```

- [x] **Step 2: Run the focused test and verify red**

Run:

```bash
python3 -m unittest tests.test_webapp.PresentationTests.test_mobile_crest_taps_trigger_repeatable_easter_egg -v
```

Expected: FAIL because the mobile crest control, counter, class, and mobile animations do not exist.

### Task 2: Add the semantic crest trigger and tap counter

**Files:**
- Modify: `webapp/app.py`
- Test: `tests/test_webapp.py`

- [x] **Step 1: Add the mobile-only hit target**

Wrap the existing brand link in `.brand-lockup` and add one sibling button. Keep the existing crest image inside the link so the source asset and desktop layout are unchanged.

```html
<div class="brand-lockup">
  <a class="app-brand" href="/" aria-label="Translate Book — загрузить книгу">…</a>
  <button class="mobile-crest-toggle" type="button" aria-label="Разбудить библиотеку"></button>
</div>
```

- [x] **Step 2: Share quote dismissal across desktop and mobile**

Move the close-button binding before the desktop breakpoint return. `dismissEasterEgg()` must remove both `.lamp-easter-egg-active` and `.mobile-easter-egg-active`, then set `aria-hidden="true"`.

```javascript
const mobileEasterEggActive = "mobile-easter-egg-active";
const dismissEasterEgg = () => {
  app.classList.remove("lamp-easter-egg-active", mobileEasterEggActive);
  easterEggMessage.setAttribute("aria-hidden", "true");
};
closeEasterEgg.addEventListener("click", dismissEasterEgg);
```

- [x] **Step 3: Add the three-second seven-tap window**

Register the crest handler once and check `matchMedia("(max-width: 640px)")` at tap time, so a responsive width change does not leave a visible but inert control. Reset after three seconds and reset immediately after a successful trigger; the existing 980 px guard still keeps desktop lamp initialization out of mobile layouts.

```javascript
let mobileTapCount = 0;
let mobileTapTimer;
const resetMobileTaps = () => {
  mobileTapCount = 0;
  window.clearTimeout(mobileTapTimer);
};
mobileCrestToggle.addEventListener("click", () => {
  if (!window.matchMedia("(max-width: 640px)").matches) return;
  if (app.classList.contains(mobileEasterEggActive)) return;
  if (mobileTapCount === 0) {
    mobileTapTimer = window.setTimeout(resetMobileTaps, 3000);
  }
  mobileTapCount += 1;
  if (mobileTapCount >= 7) {
    resetMobileTaps();
    app.classList.add(mobileEasterEggActive);
    easterEggMessage.setAttribute("aria-hidden", "false");
    closeEasterEgg.focus({ preventScroll: true });
  }
});
```

- [x] **Step 4: Run the focused test and verify green**

Run the Task 1 command and expect PASS.

### Task 3: Style the mobile scene without disturbing layout

**Files:**
- Modify: `webapp/site_styles.py`
- Test: `tests/test_webapp.py`

- [x] **Step 1: Position the 44 px crest control**

Add `.brand-lockup { position: relative; }` globally and hide `.mobile-crest-toggle` by default. Inside `@media (max-width: 640px)`, center the lockup and place a transparent 44 × 44 px button over the existing 36 px crest. Preserve keyboard focus with a brass outline.

- [x] **Step 2: Convert the quote into a mobile bottom sheet**

Override the earlier tablet `display: none` inside the 640 px media query. Use fixed left/right/bottom insets, safe-area padding, the existing textured surface, and a mobile entrance animation that ends visible.

```css
.mobile-easter-egg-active .lamp-easter-egg-message {
  animation: mobile-easter-egg-message .62s ease-out both;
}
@keyframes mobile-easter-egg-message {
  from { visibility: visible; opacity: 0; transform: translateY(24px); }
  to { visibility: visible; opacity: 1; transform: translateY(0); }
}
```

- [x] **Step 3: Animate the existing crest and covers**

Reuse `lamp-easter-egg-crest` for the crest and add `mobile-book-awakens` with a 6 px lift. Stagger the first six `.catalog-book` elements by 80 ms. Do not add catalog-specific markup to the upload page.

```css
@keyframes mobile-book-awakens {
  0%, 100% { transform: translateY(0); }
  44% { transform: translateY(-6px); }
}
```

- [x] **Step 4: Add reduced-motion fallback**

Disable crest, cover, and sheet spatial animations for `.mobile-easter-egg-active`; keep the quote visible at its final position.

- [x] **Step 5: Run all presentation tests**

Run:

```bash
python3 -m unittest tests.test_webapp.PresentationTests -v
```

Expected: all presentation tests PASS.

### Task 4: Browser QA, full regression, and delivery

**Files:**
- Modify: `design-qa.md`
- Rebuild: `outputs/translate-book-web-redesigned-20260820.tar.gz`

- [x] **Step 1: Verify the trigger at 390 px**

Confirm that six rapid taps do nothing and the seventh opens the quote. Inspect the 44 px hit target, crest pulse, 6 px cover wave, bottom-sheet bounds, and absence of horizontal overflow.

- [x] **Step 2: Verify close-only and repeatability**

Confirm that tapping outside leaves the quote open, the labelled cross closes it, and another seven rapid taps reopen it without a reload.

- [x] **Step 3: Verify route and breakpoint isolation**

Confirm the brand text still navigates to `/`, the crest does not change the URL, the upload page triggers the shared quote, widths above 640 px hide the mobile control, and the desktop lamp still triggers every 16 clicks.

- [x] **Step 4: Run the full suite**

Run:

```bash
python3 -m unittest discover -s tests -v
```

Expected: all tests PASS with zero failures.

- [x] **Step 5: Update QA notes and rebuild the archive**

Record browser evidence in `design-qa.md`, rebuild the archive without `__pycache__` or `.pyc`, and verify the packaged `app.py` contains `mobileTapCount >= 7` and `Разбудить библиотеку`.
