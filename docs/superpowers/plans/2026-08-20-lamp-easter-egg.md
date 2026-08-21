# Lamp Easter Egg Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a desktop-only cinematic lamp toggle and keep the main library atmosphere fixed during scrolling without changing backend behavior.

**Architecture:** Add one accessible hotspot button to the existing sidebar markup, one shared inline initializer for both HTML pages, and CSS-only visual states/animations. Move the main atmosphere image from the scrolling app container to its existing pseudo-layer using `position: fixed`; restore an absolute layer below the desktop breakpoint.

**Tech Stack:** Python standard-library HTML rendering, CSS, small vanilla JavaScript initializer, `unittest`, in-app browser QA.

**Repository note:** This extracted source has no `.git` directory, so commit steps are recorded as unavailable rather than creating a new repository.

## Approved follow-up: automatic switch-off on page load

- [x] Add a failing presentation test requiring the shared script to invoke the existing off transition during initialization.
- [x] Run the focused test and confirm it fails because initialization currently waits for a click.
- [x] Extract the existing transition into a small `setLampState(turnOn)` function and call `setLampState(false)` once after listeners are registered.
- [x] Run the focused presentation test, full presentation suite, and full test suite.
- [x] Verify `/` and `/library` in the desktop browser: each load flickers and ends with `lamp-is-off`, while click-to-toggle still works.
- [x] Change the fixed atmosphere image from a capped intrinsic width to `cover` and verify it fills the full main viewport without a visible edge on a wide screen.
- [x] Delay automatic switch-off until 1200 ms after `window.load`, with an immediate scheduling fallback when the page is already fully loaded.
- [x] Verify the lamp remains on before the delay, flickers after 1.2 seconds, and settles off.
- [x] Rebuild the delivery archive and update QA evidence.

---

### Task 1: Lock presentation requirements with failing tests

**Files:**
- Modify: `tests/test_webapp.py:30-73`
- Test: `tests/test_webapp.py`

- [x] **Step 1: Write failing markup and style tests**

Add tests that render both pages and require the accessible hotspot, shared script, desktop-only CSS, two flicker directions, and fixed atmosphere layer:

```python
def test_lamp_toggle_is_accessible_on_both_pages(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        app = App(Path(__file__).resolve().parents[1], Path(temp_dir) / "data")
        upload = page(app)
        library = webapp_module.library_page(app)
    for payload in (upload, library):
        self.assertEqual(payload.count(b'class="lamp-toggle"'), 1)
        self.assertIn(b'aria-pressed="true"', payload)
        self.assertIn(b'aria-label="Выключить лампу"', payload)
        self.assertIn(b"lamp-flicker-off", payload)

def test_lamp_and_main_atmosphere_have_desktop_states(self) -> None:
    self.assertIn(".library-app::before", APPROVED_SITE_STYLES)
    self.assertIn("position: fixed;", APPROVED_SITE_STYLES)
    self.assertIn("library-interior-wide.webp", APPROVED_SITE_STYLES)
    self.assertIn(".lamp-toggle", APPROVED_SITE_STYLES)
    self.assertIn("@keyframes lamp-flicker-off", APPROVED_SITE_STYLES)
    self.assertIn("@keyframes lamp-flicker-on", APPROVED_SITE_STYLES)
    self.assertIn(".lamp-toggle { display: none; }", APPROVED_SITE_STYLES)
    self.assertNotIn("background-attachment: fixed", APPROVED_SITE_STYLES)
```

- [x] **Step 2: Run the focused tests and confirm red**

Run:

```bash
python3 -m unittest \
  tests.test_webapp.PresentationTests.test_lamp_toggle_is_accessible_on_both_pages \
  tests.test_webapp.PresentationTests.test_lamp_and_main_atmosphere_have_desktop_states -v
```

Expected: failures because the lamp markup, animation names, and fixed atmosphere layer do not yet exist.

### Task 2: Add the hotspot and shared lamp behavior

**Files:**
- Modify: `webapp/app.py:490-647`
- Test: `tests/test_webapp.py`

- [x] **Step 1: Add the accessible hotspot to `site_header()`**

Render the sidebar with its initial on-state and a single invisible button:

```python
return f"""<aside class="app-navigation lamp-is-on">
  <a class="app-brand" ...>...</a>
  <nav aria-label="Основная навигация">...</nav>
  <button class="lamp-toggle" type="button" aria-label="Выключить лампу" aria-pressed="true"></button>
</aside>"""
```

- [x] **Step 2: Add a shared `lamp_interaction_script()` helper**

The helper must return one inline script that:

```javascript
(() => {
  const navigation = document.querySelector(".app-navigation");
  const toggle = document.querySelector(".lamp-toggle");
  if (!navigation || !toggle || window.matchMedia("(max-width: 980px)").matches) return;

  let isOn = true;
  let isAnimating = false;
  const syncA11y = () => {
    toggle.setAttribute("aria-pressed", String(isOn));
    toggle.setAttribute("aria-label", isOn ? "Выключить лампу" : "Включить лампу");
  };
  const finish = (turnOn, animationClass) => {
    navigation.classList.remove(animationClass);
    navigation.classList.toggle("lamp-is-off", !turnOn);
    navigation.classList.toggle("lamp-is-on", turnOn);
    isOn = turnOn;
    isAnimating = false;
    syncA11y();
  };

  toggle.addEventListener("click", () => {
    if (isAnimating) return;
    const turnOn = !isOn;
    const animationClass = turnOn ? "lamp-flicker-on" : "lamp-flicker-off";
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      finish(turnOn, animationClass);
      return;
    }
    isAnimating = true;
    navigation.classList.add(animationClass);
    navigation.addEventListener("animationend", (event) => {
      if (event.animationName !== animationClass) return;
      finish(turnOn, animationClass);
    }, { once: true });
  });
})();
```

- [x] **Step 3: Include the shared initializer on both pages**

Insert `{lamp_interaction_script()}` after each page-specific script and before `</body>` in `page()` and `library_page()`.

- [x] **Step 4: Run the markup test**

Run:

```bash
python3 -m unittest tests.test_webapp.PresentationTests.test_lamp_toggle_is_accessible_on_both_pages -v
```

Expected: PASS.

### Task 3: Add CSS animation and fixed atmosphere layer

**Files:**
- Modify: `webapp/site_styles.py:76-153,406-465`
- Test: `tests/test_webapp.py`

- [x] **Step 1: Move the atmosphere to the existing fixed pseudo-layer**

Update `.library-app::before` to use `position: fixed`, `inset: 0 0 0 230px`, `library-interior-wide.webp`, the paper texture, and an opaque dark blend. Remove the atmosphere background declarations from `.upload-app, .catalog-app` while preserving the base paper texture on `.library-app`.

- [x] **Step 2: Add the lamp shade, hotspot, and keyframes**

Use `.app-navigation::after` as a non-interactive shade over the lower illustration. Add `.lamp-toggle` with absolute desktop positioning and a transparent visual style, plus `focus-visible` brass outline. Define `lamp-flicker-off` and `lamp-flicker-on` keyframes lasting roughly 560 ms and ending at dark/on opacity respectively.

- [x] **Step 3: Restore mobile behavior**

Inside `@media (max-width: 980px)`, set `.library-app::before { position: absolute; inset: 0; }`, remove the desktop atmosphere image from that layer if it compromises the mobile header, and set `.lamp-toggle { display: none; }`.

- [x] **Step 4: Respect reduced motion**

Inside the existing reduced-motion media query, disable the lamp animations explicitly:

```css
.app-navigation.lamp-flicker-on::after,
.app-navigation.lamp-flicker-off::after { animation: none !important; }
```

- [x] **Step 5: Run all presentation tests**

Run:

```bash
python3 -m unittest tests.test_webapp.PresentationTests -v
```

Expected: all presentation tests PASS.

### Task 4: Browser QA and full verification

**Files:**
- Modify: `design-qa.md`
- Rebuild: `outputs/translate-book-web-redesigned-20260820.tar.gz`

- [x] **Step 1: Restart the local preview and inspect the desktop initial state**

Open `/library` at 1487 × 1058 CSS px. Verify the lamp hotspot does not display visible chrome and the sidebar/main atmosphere match the approved design.

- [x] **Step 2: Exercise both animation directions**

Click the hotspot, wait for `animationend`, and verify `aria-pressed=false`, `lamp-is-off`, and the darkened lamp. Click again and verify `aria-pressed=true`, `lamp-is-on`, and restored illumination.

- [x] **Step 3: Verify fixed scroll layers**

Record the sidebar and atmosphere pseudo-layer positions before and after scrolling. Sidebar top must remain `0`; the globe/books crop must remain visually fixed.

- [x] **Step 4: Verify mobile behavior**

At 394 px CSS width, verify the hotspot is `display:none`, navigation remains usable, and `body.scrollWidth` equals the viewport width.

- [x] **Step 5: Run the full suite**

Run:

```bash
python3 -m unittest discover -s tests -v
```

Expected: all tests PASS with no backend behavior changes.

- [x] **Step 6: Update QA evidence and package**

Update `design-qa.md` with the lamp states, fixed-atmosphere evidence, viewport measurements, interaction checks, and exact test count. Rebuild the archive and verify it contains the updated CSS, app renderer, tests, specification, plan, and QA report.

- [x] **Step 7: Commit status**

No commit can be created because the supplied extracted source is not a Git repository. Preserve all changes in the rebuilt archive.
