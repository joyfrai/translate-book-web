# Design QA

Дата проверки: 20 августа 2026

- Source visual truth: `/Users/apple/.codex/generated_images/01a01ab0-755f-7b23-bd9a-86f7c6c7f1e5/exec-d77f3b18-5b1e-4254-96dc-c591d464b87f.png`
- Implementation: `http://127.0.0.1:3100/library`
- Implementation screenshot: `/Users/apple/Documents/Codex/2026-08-19/product-design-plugin-product-design-openai-2/outputs/qa/library-lamp-on-final.png`
- Full-view comparison: `/Users/apple/Documents/Codex/2026-08-19/product-design-plugin-product-design-openai-2/outputs/qa/final-reference-comparison-lamp.png`
- Lamp-off evidence: `/Users/apple/Documents/Codex/2026-08-19/product-design-plugin-product-design-openai-2/outputs/qa/library-lamp-off-final.png`
- Fixed-atmosphere scroll evidence: `/Users/apple/Documents/Codex/2026-08-19/product-design-plugin-product-design-openai-2/outputs/qa/library-fixed-atmosphere-scroll.png`
- Focused upload evidence: `/Users/apple/Documents/Codex/2026-08-19/product-design-plugin-product-design-openai-2/outputs/qa/upload-scroll-status.png`
- Mobile evidence: `/Users/apple/Documents/Codex/2026-08-19/product-design-plugin-product-design-openai-2/outputs/qa/library-mobile-final.png`

## Viewport and normalization

- Desktop CSS viewport: 1487 × 1058 px; browser capture: 1487 × 886 px at the selected in-app browser density.
- Source pixels: 1487 × 1058. For the combined comparison, the source was cropped to the same 1487 × 886 visible region; no scaling was applied.
- Mobile CSS viewport: 394 × 845 px; no horizontal overflow (`body.scrollWidth = 394`).
- State: six completed translations in the catalog; six completed jobs plus one processing job on the upload page.

## Findings

- No actionable P0, P1, or P2 differences remain.
- The catalog intentionally uses a direct three-column library grid instead of the reference's featured-book block. This is the approved separation between the upload/progress page and the finished-book catalog, not accidental drift.
- The mock contains author metadata that the current backend does not provide. The implementation therefore uses only real filename-derived titles, languages, dates, and downloads; no author names were invented.

## Fidelity surfaces

- Fonts and typography: bundled Cormorant Garamond gives headings, book titles, and covers the intended editorial character; UI text remains legible at desktop and mobile sizes.
- Spacing and layout rhythm: covers, titles, dates, language pairs, and vertical download buttons share a centered desktop axis; mobile cards deliberately return to left alignment beside the cover.
- Colors and tokens: dark green-black surfaces, brass rules, gold active navigation, and oxblood primary actions match the reference direction. Statuses use neutral outlined circles with gold icons instead of green/yellow badges.
- Image quality and assets: supplied/generated library imagery is darkened behind content; cover textures, spines, inset highlights, and shadows remain crisp. Official Phosphor SVG icons are used.
- Copy and content: upload and catalog copy is concise; internal VirusTotal wording is absent; timestamps omit seconds and timezone; catalog exposes separate original/translation downloads.

## Interaction and responsive checks

- Search filters the visible catalog.
- Source and target language selectors remain enabled on mobile and desktop.
- Status icons expose accessible labels; processing uses a rotating indicator and completed jobs use a check.
- All desktop progress bars have identical left/right coordinates whether or not a download button is present.
- Desktop sidebar remains fixed from `navTop = 0` to `navBottom = viewportHeight` after scrolling; its divider no longer ends with page content.
- The lamp hotspot is visually invisible for pointer input, exposes `aria-pressed` and a changing action label, remains on for 1.2 seconds after `window.load`, then automatically flickers and settles off; subsequent clicks still flicker in both directions.
- Every 16th accepted manual lamp click activates the easter-egg scene. Browser evidence confirms activation at click 16 and again at click 32 without reloading. Automatic switch-off does not increment the counter.
- The persistent card quotes Nietzsche, uses the existing editorial typeface, has a textured `rgba(5, 12, 10, .92)` backing, and exposes an accessible dialog label. A click outside leaves it visible; only the labelled close button removes it.
- Lamp-off settles at shade opacity `.66`; lamp-on settles at `0`. The sidebar base overlay is now `.28`, making the lamp noticeably brighter while retaining navigation contrast.
- The main fixed atmosphere overlay is now `.43`, revealing more of the globe and book stack without overtaking catalog content.
- On mobile widths up to 640 px, the existing crest has a semantic 44 × 44 px hit target. Six rapid taps leave the interface unchanged; the seventh within three seconds opens the persistent Nietzsche bottom sheet, pulses the crest, and lifts catalog covers by 6 px in a staggered wave.
- The mobile tap window resets after three seconds, the scene repeats after another seven taps without reload, taps outside do not dismiss it, and the existing labelled cross remains the only close action. Browser checks covered both `/library` and `/`; the brand text still navigates to `/` while crest taps preserve the current URL.
- At 390 × 845 CSS px the mobile quote keeps approximately 16 px side and bottom insets, the document has zero horizontal overflow, and focus moves to «Закрыть цитату». Above 640 px the mobile hit target is hidden; at 1487 px the fixed desktop sidebar and 16-click lamp trigger remain intact.
- The crest handler rechecks the current 640 px media query on every tap. Browser verification loaded the page at 1487 px, changed to 390 px without reload, and successfully triggered the mobile scene after seven taps, avoiding an inert control after responsive width changes.
- The main globe/books atmosphere uses fixed pseudo-layers rather than `background-attachment: fixed`; both layers remain fixed while content scrolls and revert to absolute positioning below 980 px. The image uses `cover` across the full area from the 230 px sidebar edge to the right viewport edge, removing the visible capped-image boundary on wide screens.
- Mobile catalog and upload page have no horizontal overflow.
- No focused crop beyond the upload status evidence was needed: title, metadata, icons, and controls are readable in the 1487 px full-width captures.

## Comparison history

1. Earlier P2: covers were centered but their title/date/language metadata remained left-aligned. Fixed by centering the desktop metadata stack while preserving left alignment in horizontal mobile cards. Post-fix evidence: `library-centered-desktop.png` and `library-mobile-final.png`.
2. Earlier P2: rows without a download button shifted the progress bar. Fixed with a stable reserved action column and a one-column responsive fallback. Post-fix DOM evidence shows every desktop progress region at the same coordinates (`left 666`, `right 1161`).
3. Earlier P2: external status SVGs rendered black against the dark card. Fixed with brass/red icon filters while retaining official icon assets. Post-fix evidence: `upload-scroll-status.png`.
4. Earlier P2: sidebar divider moved/ended during scroll and `background-attachment` caused visual jank. Fixed with a viewport-fixed, paint-contained desktop sidebar and dedicated fixed pseudo-layers for the main atmosphere. Post-fix evidence: `navTop 0`, `navBottom 1058`, both atmosphere layers `position: fixed` at `scrollY 436`.
5. Lamp iteration P2: the invisible hotspot briefly showed a large focus ring after pointer activation. Fixed by distinguishing pointer focus while preserving the keyboard-only `focus-visible` outline. Post-fix pointer evidence reports `outline: none`.
6. Follow-up P2: the atmosphere image was capped at `1180px`, exposing a rectangular image edge on wide screens. Fixed by sizing the fixed layer with `cover`; browser evidence reports an app width equal to the viewport width and no horizontal overflow.
7. Easter-egg iteration: the approved desktop scene reuses only existing assets. At the 16th and 32nd manual triggers the background zoom, crest pulse, cover wave, and attributed quote card all became active. The card persisted through an outside click and closed only through its own button.
8. Mobile easter-egg iteration: seven rapid taps on the existing crest trigger a bottom-sheet adaptation of the same quote. Browser evidence confirms the 6/7 threshold, three-second reset, repeatability, close-only behavior, upload-page fallback without covers, 44 px target, and desktop isolation.

## Verification

- `python3 -m unittest discover -s tests -v` — 259 tests passed.
- Browser timing evidence: at 900 ms the lamp is on; at 1350 ms `lamp-flicker-off` is active; at 1950 ms the lamp is off with `aria-pressed=false`. Checks also covered both manual lamp states, fixed full-width atmosphere sizing, desktop upload/progress, and 394 px mobile layouts. Browser console: no errors.

final result: passed
