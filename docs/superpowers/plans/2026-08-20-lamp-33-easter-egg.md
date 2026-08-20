# Lamp 16 Easter Egg Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trigger a repeatable desktop-only library awakening scene on every 16th accepted manual lamp toggle.

**Architecture:** Extend the existing shared lamp initializer with an in-memory manual toggle counter and a single scene trigger that toggles a class on `.library-app`. Render one shared status message and animate only existing visual surfaces with CSS; keep automatic lamp shutdown outside the counter.

**Tech Stack:** Python-rendered HTML, CSS keyframes, minimal vanilla JavaScript, `unittest`, in-app browser QA.

**Repository note:** The extracted source is not a Git repository, so commit and worktree steps are unavailable. The approved changes are applied directly and delivered in the rebuilt archive.

---

### Task 1: Lock the presentation contract

**Files:**
- Modify: `tests/test_webapp.py`

- [x] **Step 1: Add a failing presentation test**

Require both pages to contain the status text and the shared script to contain `manualToggleCount`, `% 16 === 0`, and `lamp-easter-egg-active`. Require CSS to contain the active scene, message, crest, background, cover-wave, and reduced-motion selectors.

- [x] **Step 2: Run the focused test and verify red**

Run:

```bash
python3 -m unittest tests.test_webapp.PresentationTests.test_every_thirty_third_manual_lamp_toggle_triggers_easter_egg -v
```

Expected: FAIL because the message, counter, trigger, and scene styles do not exist.

### Task 2: Add shared markup and trigger logic

**Files:**
- Modify: `webapp/app.py`
- Test: `tests/test_webapp.py`

- [x] **Step 1: Render the shared status message**

Render exactly one element after the sidebar on both pages:

```html
<p class="lamp-easter-egg-message" role="status" aria-live="polite">Хватит тыркать эту лампу</p>
```

- [x] **Step 2: Count accepted manual clicks**

Add `let manualToggleCount = 0;`. In the click handler, return while animating, then increment once, trigger the scene when `manualToggleCount % 16 === 0`, and call the existing `setLampState(!isOn)`. Do not increment inside `scheduleAutoOff`.

- [x] **Step 3: Make the scene repeatable**

`triggerEasterEgg()` adds `.lamp-easter-egg-active` and leaves it active until the dedicated close button invokes `dismissEasterEgg()`. Because the counter uses modulo, the same function runs at 16, 32, 48, and later multiples.

- [x] **Step 4: Run the focused test and verify green**

Run the command from Task 1 and expect PASS.

### Task 3: Style the approved scene

**Files:**
- Modify: `webapp/site_styles.py`
- Test: `tests/test_webapp.py`

- [x] **Step 1: Style the message**

Use a fixed, pointer-transparent, centered typographic status in the main area. Keep it hidden by default and animate opacity/vertical position only when `.lamp-easter-egg-active` is present.

- [x] **Step 2: Animate existing assets**

Animate `.library-app::before` with a small scale, `.app-brand img` with a brass-toned brightness/drop-shadow pulse, and `.book-cover` with a short staggered lift using existing catalog child order.

- [x] **Step 3: Preserve responsive and reduced-motion behavior**

Hide the message below 981 px. In reduced-motion mode, disable the background, crest, and cover animations while showing the message with a calm opacity transition.

- [x] **Step 4: Run presentation tests**

```bash
python3 -m unittest tests.test_webapp.PresentationTests -v
```

Expected: all presentation tests PASS.

### Task 4: Browser QA and delivery

**Files:**
- Modify: `design-qa.md`
- Rebuild: `outputs/translate-book-web-redesigned-20260820.tar.gz`

- [x] **Step 1: Verify the first trigger**

On `/library` at desktop width, exercise 16 accepted clicks through the real lamp control, sampling the 16th transition to verify the active class, quote card, crest/background animation, outside-click persistence, and close-button cleanup.

- [x] **Step 2: Verify repeatability**

Exercise the next 16 accepted clicks without reloading and confirm the scene triggers again at 32.

- [x] **Step 3: Verify upload and mobile behavior**

### Task 5: Persistent quote card and lighter atmosphere

**Files:**
- Modify: `webapp/app.py`
- Modify: `webapp/site_styles.py`
- Modify: `tests/test_webapp.py`

- [x] **Step 1: Lock the revised quote, dismissal, backing, and overlay values in failing tests**
- [x] **Step 2: Replace the temporary message with the attributed Nietzsche quote card**
- [x] **Step 3: Keep the card until its own close button is pressed**
- [x] **Step 4: Reveal more of the lamp and globe backgrounds without reducing content contrast**
- [x] **Step 5: Run automated and desktop/mobile browser verification**

Confirm the shared message/scene works on `/`, and at 394 px the lamp trigger and easter-egg message remain unavailable with no horizontal overflow.

- [x] **Step 4: Run the full suite**

```bash
python3 -m unittest discover -s tests -v
```

Expected: 256 tests plus the new presentation test PASS.

- [x] **Step 5: Update QA and package**

Record the trigger evidence, reduced-motion contract, test count, and `final result: passed`; rebuild the archive and verify it contains the updated renderer, styles, tests, spec, plan, and QA report.
