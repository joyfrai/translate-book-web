SITE_STYLES = """<style>
@font-face {
  font-family: "Cormorant Garamond Variable";
  src: url("assets/fonts/cormorant-garamond-cyrillic-wght-normal.woff2") format("woff2");
  font-style: normal;
  font-weight: 300 700;
  font-display: swap;
  unicode-range: U+0400-052F, U+2DE0-2DFF, U+A640-A69F;
}
@font-face {
  font-family: "Cormorant Garamond Variable";
  src: url("assets/fonts/cormorant-garamond-latin-wght-normal.woff2") format("woff2");
  font-style: normal;
  font-weight: 300 700;
  font-display: swap;
  unicode-range: U+0000-024F;
}
:root {
  color-scheme: dark;
  --font-display: "Cormorant Garamond Variable", Georgia, "Times New Roman", serif;
  --ink: #f1dfc2;
  --ink-soft: #bfae94;
  --ink-muted: #8f8574;
  --surface: #07100e;
  --surface-raised: #0c1512;
  --surface-soft: #111a16;
  --rule: #4d4030;
  --rule-soft: #28261f;
  --brass: #c58a42;
  --brass-bright: #e0ad64;
  --oxblood: #711f16;
  --danger: #e0836f;
  --success: #7ca66e;
  --warning: #d9a45b;
  --texture-leather: url("assets/textures/leather-dark.webp");
  --texture-linen: url("assets/textures/linen-light.webp");
  --texture-cloth: url("assets/textures/book-cloth.webp");
  --texture-paper: url("assets/textures/aged-paper.webp");
  --texture-dark-paper: url("assets/textures/mottled-paper-dark.webp");
}
* { box-sizing: border-box; }
html {
  min-width: 320px;
  min-height: 100%;
  overflow-x: hidden;
  background-color: var(--surface);
  background-image: var(--texture-dark-paper);
  background-size: 720px 720px;
}
body {
  min-width: 320px;
  min-height: 100%;
  margin: 0;
  overflow-x: hidden;
  color: var(--ink);
  background: transparent;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 15px;
  line-height: 1.5;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
button, input, select { font: inherit; }
button, a, input, select { -webkit-tap-highlight-color: transparent; }
a { color: inherit; }
:focus-visible { outline: 2px solid var(--brass-bright); outline-offset: 3px; }
.library-app {
  position: relative;
  isolation: isolate;
  min-height: 100dvh;
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr);
  background-color: rgba(4, 11, 9, .82);
  background-image: var(--texture-dark-paper);
  background-size: 720px 720px;
  background-blend-mode: soft-light;
}
.library-app::before {
  content: "";
  position: fixed;
  z-index: 0;
  inset: 0 0 0 230px;
  background-image: url("assets/atmosphere/library-interior-wide.webp"), var(--texture-dark-paper);
  background-position: right top, center;
  background-repeat: no-repeat, repeat;
  background-size: cover, 720px 720px;
  background-blend-mode: normal, soft-light;
  pointer-events: none;
}
.library-app::after {
  content: "";
  position: fixed;
  z-index: 0;
  inset: 0 0 0 230px;
  background: rgba(1, 6, 5, .43);
  pointer-events: none;
}
.upload-app,
.catalog-app {
  background-image: var(--texture-dark-paper);
}
.app-navigation {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 10;
  width: 230px;
  height: auto;
  display: flex;
  flex-direction: column;
  gap: 48px;
  padding: 38px 18px 28px;
  border-right: 1px solid #695338;
  background-color: #08110f;
  background-image: url("assets/atmosphere/library-sidebar-study.webp"), var(--texture-dark-paper);
  background-position: 15% bottom, center;
  background-repeat: no-repeat, repeat;
  background-size: cover, 520px 520px;
  background-blend-mode: normal, soft-light;
  box-shadow: 10px 0 30px rgba(0, 0, 0, .2), inset -1px 0 rgba(231, 176, 99, .08);
  contain: paint;
}
.app-navigation::before {
  content: "";
  position: absolute;
  z-index: 0;
  inset: 0;
  background: rgba(1, 6, 5, .28);
  pointer-events: none;
}
.app-navigation::after {
  content: "";
  position: absolute;
  z-index: 0;
  inset: 38% 0 0;
  background: rgba(1, 6, 5, .82);
  opacity: 0;
  pointer-events: none;
  transition: opacity .24s ease;
}
.app-navigation.lamp-is-off::after { opacity: .66; }
.app-navigation.lamp-flicker-off::after { animation: lamp-flicker-off .62s steps(1, end) forwards; }
.app-navigation.lamp-flicker-on::after { animation: lamp-flicker-on .62s steps(1, end) forwards; }
@keyframes lamp-flicker-off {
  0% { opacity: 0; }
  14% { opacity: .6; }
  27% { opacity: .08; }
  42% { opacity: .7; }
  55% { opacity: .14; }
  72% { opacity: .62; }
  84% { opacity: .2; }
  100% { opacity: .66; }
}
@keyframes lamp-flicker-on {
  0% { opacity: .66; }
  14% { opacity: .1; }
  27% { opacity: .62; }
  42% { opacity: .08; }
  55% { opacity: .56; }
  72% { opacity: .12; }
  84% { opacity: .48; }
  100% { opacity: 0; }
}
.lamp-toggle {
  position: absolute;
  z-index: 2;
  top: 38%;
  left: 24px;
  width: 180px;
  height: min(32vh, 220px);
  min-height: 150px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: transparent;
  cursor: pointer;
}
.lamp-toggle:focus-visible { outline: 1px solid rgba(224, 173, 100, .78); outline-offset: 4px; }
.lamp-toggle[data-pointer-focus="true"]:focus-visible { outline: none; }
.lamp-easter-egg-message {
  position: fixed;
  z-index: 20;
  top: 50%;
  left: calc(50% + 115px);
  width: min(760px, calc(100vw - 310px));
  margin: 0;
  padding: clamp(26px, 3vw, 40px) clamp(28px, 4vw, 52px) clamp(22px, 2.6vw, 34px);
  border: 1px solid rgba(224, 173, 100, .42);
  border-radius: 7px;
  background-color: rgba(5, 12, 10, .92);
  background-image: var(--texture-dark-paper);
  background-size: 420px 420px;
  background-blend-mode: soft-light;
  box-shadow: inset 0 1px rgba(255, 239, 208, .08), 0 26px 70px rgba(0, 0, 0, .66);
  color: var(--ink);
  font-family: var(--font-display);
  text-align: center;
  opacity: 0;
  visibility: hidden;
  transform: translate(-50%, -38%);
  pointer-events: auto;
}
.lamp-easter-egg-close {
  position: absolute;
  top: 11px;
  right: 11px;
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  padding: 0 0 3px;
  border: 1px solid rgba(224, 173, 100, .36);
  border-radius: 50%;
  background: rgba(10, 19, 16, .9);
  color: var(--brass-bright);
  font-family: var(--font-display);
  font-size: 30px;
  line-height: 1;
  cursor: pointer;
  transition: color .18s ease, border-color .18s ease, background-color .18s ease, transform .18s ease;
}
.lamp-easter-egg-close:hover { border-color: var(--brass-bright); background-color: #18211d; color: var(--ink); transform: rotate(4deg); }
.lamp-easter-egg-message blockquote {
  margin: 0;
  font-size: clamp(32px, 3.6vw, 54px);
  font-weight: 500;
  line-height: 1.08;
  text-shadow: 0 3px 18px rgba(0, 0, 0, .76);
}
.lamp-easter-egg-message figcaption {
  margin-top: 18px;
  color: var(--brass-bright);
  font-size: clamp(17px, 1.6vw, 22px);
  font-style: italic;
  letter-spacing: .035em;
}
.library-app.lamp-easter-egg-active::before { animation: library-awakens-background 4.2s ease-in-out both; }
.lamp-easter-egg-active .lamp-easter-egg-message { animation: lamp-easter-egg-message .72s ease-out both; }
.lamp-easter-egg-active .app-brand img { animation: lamp-easter-egg-crest 2.1s ease-in-out 2; }
.lamp-easter-egg-active .catalog-book .book-cover { animation: book-awakens 1.1s ease-in-out both; }
.lamp-easter-egg-active .catalog-book:nth-child(2) .book-cover { animation-delay: .1s; }
.lamp-easter-egg-active .catalog-book:nth-child(3) .book-cover { animation-delay: .2s; }
.lamp-easter-egg-active .catalog-book:nth-child(4) .book-cover { animation-delay: .3s; }
.lamp-easter-egg-active .catalog-book:nth-child(5) .book-cover { animation-delay: .4s; }
.lamp-easter-egg-active .catalog-book:nth-child(6) .book-cover { animation-delay: .5s; }
@keyframes library-awakens-background {
  0%, 100% { transform: scale(1); filter: brightness(1); }
  34%, 72% { transform: scale(1.035); filter: brightness(1.16); }
}
@keyframes lamp-easter-egg-message {
  0% { visibility: visible; opacity: 0; transform: translate(-50%, -32%); }
  100% { visibility: visible; opacity: 1; transform: translate(-50%, -50%); }
}
@keyframes lamp-easter-egg-crest {
  0%, 100% { filter: sepia(.12) saturate(.82) brightness(.88) drop-shadow(0 6px 12px rgba(0, 0, 0, .62)); }
  46% { filter: sepia(.3) saturate(1.45) brightness(1.45) drop-shadow(0 0 18px rgba(224, 173, 100, .92)); }
}
@keyframes book-awakens {
  0%, 100% { transform: translateY(0); }
  42% { transform: translateY(-12px); }
}
.brand-lockup { position: relative; z-index: 1; width: max-content; align-self: center; }
.app-brand {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  flex-direction: column;
  gap: 8px;
  color: var(--brass-bright);
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  line-height: 1.1;
  text-align: center;
  text-decoration: none;
  text-shadow: 0 2px 8px rgba(0, 0, 0, .7);
}
.app-brand img {
  width: 82px;
  height: 82px;
  object-fit: contain;
  filter: sepia(.12) saturate(.82) brightness(.88) drop-shadow(0 6px 12px rgba(0, 0, 0, .62));
}
.mobile-crest-toggle { display: none; }
.app-navigation nav { position: relative; z-index: 1; display: grid; gap: 10px; min-width: 0; }
.nav-link {
  min-height: 52px;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 0 16px;
  border: 1px solid transparent;
  border-radius: 8px;
  color: var(--ink-soft);
  font-size: 15px;
  text-decoration: none;
  transition: color .18s ease, background-color .18s ease, border-color .18s ease, box-shadow .18s ease;
}
.nav-link:hover { color: var(--ink); }
.nav-link.active {
  border-color: #b07b3b;
  background-color: #765126;
  background-image: var(--texture-leather);
  background-size: 380px 380px;
  background-blend-mode: soft-light;
  color: #fff0d3;
  box-shadow: inset 3px 0 var(--brass-bright), inset 0 1px rgba(255, 233, 195, .16), inset 0 -10px 18px rgba(41, 21, 4, .18), 0 8px 22px rgba(0, 0, 0, .22);
}
.nav-icon, .ui-icon { display: block; flex: 0 0 auto; object-fit: contain; }
.nav-icon { width: 22px; height: 22px; }
.ui-icon { width: 20px; height: 20px; }
.nav-count {
  min-width: 20px;
  margin-left: auto;
  padding: 1px 5px;
  border: 1px solid rgba(255, 225, 172, .24);
  border-radius: 999px;
  color: #ffe3ad;
  font-size: 10px;
  text-align: center;
}
.app-content {
  position: relative;
  z-index: 1;
  grid-column: 2;
  width: min(100%, 1360px);
  margin: 0 auto;
  padding: 46px clamp(28px, 4vw, 68px) 76px;
}
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 32px;
  margin-bottom: 38px;
}
h1, h2, h3, p { margin-top: 0; }
h1, h2, h3 { font-family: var(--font-display); font-weight: 500; }
.page-header h1 { margin-bottom: 0; font-size: clamp(44px, 5vw, 68px); line-height: .98; letter-spacing: -.035em; }
.page-header p { margin: 12px 0 0; color: var(--ink-soft); font-size: 15px; }
.section-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 20px; }
.section-heading h2 { margin: 0; font-size: clamp(28px, 3vw, 38px); line-height: 1; letter-spacing: -.025em; }
.section-heading p { margin: 7px 0 0; color: var(--ink-muted); }
.button, .quiet-link, .search-field input, select {
  border: 1px solid var(--rule);
  border-radius: 7px;
  background-color: rgba(8, 17, 15, .78);
  background-image: var(--texture-dark-paper);
  background-size: 420px 420px;
  background-blend-mode: soft-light;
  color: var(--ink);
  box-shadow: inset 0 1px rgba(255, 239, 208, .04), 0 7px 18px rgba(0, 0, 0, .15);
}
.button, .quiet-link {
  min-height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 17px;
  color: var(--brass-bright);
  font-weight: 650;
  text-decoration: none;
  cursor: pointer;
  transition: border-color .18s ease, color .18s ease, background-color .18s ease, box-shadow .18s ease, transform .18s ease;
}
.button:hover, .quiet-link:hover { border-color: var(--brass); color: var(--ink); background-color: #111b17; transform: translateY(-1px); }
.button-primary {
  border-color: #a74731;
  background-color: var(--oxblood);
  background-image: var(--texture-leather);
  color: #f8dfc2;
  box-shadow: inset 0 1px rgba(255, 226, 186, .12), inset 0 -10px 22px rgba(32, 4, 2, .22), 0 12px 28px rgba(0, 0, 0, .18);
}
.button-primary:hover { background-color: #85291d; color: #fff0d3; }
.upload-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.12fr) minmax(300px, .88fr);
  gap: 44px;
  padding: 34px 0 38px;
  border-top: 1px solid var(--rule-soft);
  border-bottom: 1px solid var(--rule-soft);
}
.field-label { display: flex; justify-content: space-between; gap: 12px; margin: 0 0 11px; color: var(--ink-soft); font-size: 13px; font-weight: 650; }
.field-hint { color: var(--ink-muted); font-weight: 500; }
.file-input { position: absolute; width: 1px; height: 1px; overflow: hidden; opacity: 0; }
.file-picker {
  min-height: 250px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 10px;
  padding: 30px;
  border: 1px dashed #82653f;
  border-radius: 8px;
  background-color: #0a1311;
  background-image: var(--texture-dark-paper);
  background-size: 460px 460px;
  background-blend-mode: soft-light;
  color: var(--ink-soft);
  box-shadow: inset 0 0 32px rgba(0, 0, 0, .32), 0 14px 30px rgba(0, 0, 0, .12);
  text-align: center;
  cursor: pointer;
  transition: border-color .18s ease, background-color .18s ease, box-shadow .18s ease;
}
.file-picker.is-disabled { cursor: wait; opacity: .58; }
.file-picker:hover, .file-picker.has-file, .file-picker.is-dragover { border-color: var(--brass); background-color: #0d1714; box-shadow: inset 0 0 28px rgba(0, 0, 0, .24), 0 16px 34px rgba(0, 0, 0, .18); }
.file-picker.is-dragover { background-color: #18251d; }
.file-picker .file-visual { width: 56px; height: 56px; filter: drop-shadow(0 5px 8px rgba(0, 0, 0, .35)); }
.file-picker strong { max-width: 100%; overflow: hidden; color: var(--ink); font-family: var(--font-display); font-size: clamp(24px, 3vw, 34px); font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.file-picker span { font-size: 13px; }
.file-feedback { min-height: 18px; margin: 8px 0 0; color: var(--ink-muted); font-size: 12px; }
.file-feedback.is-error { color: var(--danger); }
.translation-settings { display: flex; flex-direction: column; justify-content: space-between; gap: 19px; padding: 2px 0 8px; }
.language-grid { display: grid; gap: 14px; }
.select-wrap { position: relative; }
.select-wrap::after { content: ""; position: absolute; top: 50%; right: 14px; width: 7px; height: 7px; border-right: 1px solid var(--brass); border-bottom: 1px solid var(--brass); pointer-events: none; transform: translateY(-70%) rotate(45deg); }
select { width: 100%; min-height: 54px; appearance: none; padding: 0 40px 0 15px; }
select:hover { border-color: var(--brass); }
.form-actions { display: grid; gap: 14px; }
.form-actions .button { min-height: 62px; font-family: var(--font-display); font-size: 20px; }
.button:disabled, .button:disabled:hover { cursor: wait; opacity: .78; transform: none; }
.button-progress-icon { animation: status-spin 1.4s linear infinite; }
.notice { margin-bottom: 22px; padding: 13px 15px; border: 1px solid #735c37; color: var(--warning); background: rgba(61, 42, 18, .58); }
.service-explainer {
  margin-top: 34px;
  padding: 27px 30px 23px;
  border: 1px solid var(--rule-soft);
  background-color: rgba(7, 16, 14, .76);
  background-image: var(--texture-dark-paper);
  background-size: 520px 520px;
  background-blend-mode: soft-light;
  box-shadow: inset 0 1px rgba(255, 239, 208, .035), 0 16px 34px rgba(0, 0, 0, .13);
}
.service-explainer-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 24px; margin-bottom: 22px; }
.service-explainer-heading h2 { margin: 0; font-size: clamp(28px, 3vw, 36px); line-height: 1; letter-spacing: -.02em; }
.service-explainer-heading p { margin: 0; color: var(--ink-muted); font-size: 12px; }
.service-steps { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0; }
.service-step { min-width: 0; display: grid; grid-template-columns: 38px minmax(0, 1fr); gap: 13px; padding: 2px 24px; border-left: 1px solid var(--rule-soft); }
.service-step:first-child { padding-left: 0; border-left: 0; }
.service-step:last-child { padding-right: 0; }
.service-step-icon { width: 38px; height: 38px; display: grid; place-items: center; border: 1px solid var(--rule); border-radius: 50%; background: rgba(12, 21, 18, .76); }
.service-step-icon img { width: 20px; height: 20px; }
.service-step h3 { margin: 0 0 4px; color: var(--ink); font-size: 19px; line-height: 1.05; }
.service-step p { margin: 0; color: var(--ink-muted); font-size: 12px; line-height: 1.45; }
.service-note { margin: 20px 0 0; padding-top: 14px; border-top: 1px solid var(--rule-soft); color: var(--ink-soft); font-size: 11px; }
.tasks-section { margin-top: 44px; }
.refresh-link { display: inline-flex; align-items: center; gap: 6px; color: var(--brass-bright); font-size: 13px; text-decoration: none; }
.refresh-link:hover { color: var(--ink); }
.job-list { display: grid; gap: 12px; margin: 0; padding: 0; list-style: none; }
.job {
  display: grid;
  grid-template-columns: minmax(220px, .8fr) minmax(300px, 1.2fr) minmax(190px, 220px);
  align-items: center;
  gap: 24px;
  padding: 20px 22px;
  border: 1px solid var(--rule-soft);
  background-color: #091210;
  background-image: var(--texture-dark-paper);
  background-size: 560px 560px;
  background-blend-mode: soft-light;
  box-shadow: inset 0 1px rgba(255, 239, 208, .025), 0 12px 30px rgba(0, 0, 0, .14);
}
.job-main { min-width: 0; }
.job-title { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.job-title strong { min-width: 0; overflow: hidden; color: var(--ink); font-family: var(--font-display); font-size: 20px; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.status { width: 25px; height: 25px; display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto; border: 1px solid var(--rule); border-radius: 50%; background: rgba(12, 21, 18, .82); color: var(--ink-soft); }
.status img { width: 15px; height: 15px; filter: brightness(0) saturate(100%) invert(76%) sepia(42%) saturate(747%) hue-rotate(349deg) brightness(93%) contrast(88%); }
.status-queued, .status-processing, .status-done { color: var(--brass-bright); }
.status-failed { color: var(--danger); }
.status-failed img { filter: brightness(0) saturate(100%) invert(65%) sepia(26%) saturate(1147%) hue-rotate(321deg) brightness(97%) contrast(84%); }
.status-processing img { animation: status-spin 1.4s linear infinite; }
@keyframes status-spin { to { transform: rotate(360deg); } }
.job-meta { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 6px; color: var(--ink-muted); font-size: 11px; }
.job-usage { color: var(--brass-bright); }
.progress-wrap { display: grid; grid-template-columns: minmax(140px, 1fr) auto; align-items: center; gap: 10px; }
.progress-track { height: 6px; overflow: hidden; background: #29271f; }
.progress-track span { display: block; width: var(--progress); height: 100%; background-color: var(--brass); background-image: var(--texture-leather); background-size: 280px 280px; background-blend-mode: soft-light; box-shadow: 0 0 12px rgba(215, 155, 78, .22); }
.progress-label { color: var(--ink-soft); font-size: 11px; white-space: nowrap; }
.progress-note { grid-column: 1 / -1; color: var(--ink-muted); font-size: 10px; }
.job-actions { display: flex; align-items: center; }
.job-actions .button { min-height: 42px; font-size: 12px; }
.error { grid-column: 1 / -1; color: var(--danger); font-size: 12px; white-space: pre-wrap; }
.empty-state { min-height: 126px; display: flex; align-items: flex-start; justify-content: center; flex-direction: column; gap: 7px; padding: 28px; border: 1px solid var(--rule-soft); color: var(--ink-soft); }
.empty-state strong { color: var(--ink); font-family: var(--font-display); font-size: 21px; font-weight: 500; }
.catalog-header { align-items: center; }
.catalog-tools { display: flex; align-items: center; gap: 14px; width: min(100%, 610px); }
.search-field { position: relative; flex: 1; }
.search-field img { position: absolute; top: 50%; left: 17px; z-index: 1; width: 20px; height: 20px; transform: translateY(-50%); pointer-events: none; }
.search-field input { width: 100%; min-height: 54px; padding: 0 18px 0 50px; }
.search-field input::placeholder { color: var(--ink-muted); }
.catalog-tools .button { min-height: 54px; white-space: nowrap; }
.catalog-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); column-gap: clamp(30px, 4vw, 68px); row-gap: 58px; }
.catalog-book { min-width: 0; }
.book-cover {
  --cover-bg: #481a17;
  --cover-ink: #e8c786;
  --cover-rule: #ad753e;
  --cover-edge: #25100f;
  --cover-texture: var(--texture-leather);
  --cover-text-shadow: 0 1px rgba(255, 244, 219, .18), 0 2px 4px rgba(0, 0, 0, .28);
  position: relative;
  width: min(100%, 228px);
  margin-inline: auto;
  aspect-ratio: 2 / 3;
  overflow: hidden;
  padding: 13px;
  border: 1px solid color-mix(in srgb, var(--cover-edge), #f2d7a2 12%);
  border-left-width: 14px;
  border-top-color: color-mix(in srgb, var(--cover-rule), #fff0cf 24%);
  border-bottom-color: color-mix(in srgb, var(--cover-edge), #000 24%);
  border-radius: 4px 7px 7px 4px;
  background-color: var(--cover-bg);
  background-image: var(--cover-texture);
  background-size: cover;
  background-blend-mode: luminosity;
  box-shadow: inset 3px 0 rgba(255, 236, 198, .09), inset 14px 0 18px rgba(0, 0, 0, .32), inset -12px 0 24px rgba(0, 0, 0, .18), inset 0 2px rgba(255, 239, 207, .11), inset 0 -32px 36px rgba(0, 0, 0, .3), 0 27px 48px rgba(0, 0, 0, .5), 0 7px 10px rgba(0, 0, 0, .42);
  color: var(--cover-ink);
  transition: transform .2s ease, box-shadow .2s ease;
}
.catalog-book:hover .book-cover { transform: translateY(-4px); box-shadow: inset 3px 0 rgba(255, 236, 198, .11), inset 14px 0 18px rgba(0, 0, 0, .28), inset -12px 0 24px rgba(0, 0, 0, .16), inset 0 2px rgba(255, 239, 207, .13), inset 0 -30px 34px rgba(0, 0, 0, .26), 0 33px 56px rgba(0, 0, 0, .54), 0 9px 13px rgba(0, 0, 0, .42); }
.book-cover-frame { height: 100%; display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 18px; padding: 24px 14px; border: 3px double var(--cover-rule); background-color: rgba(0, 0, 0, .035); box-shadow: inset 0 0 0 1px rgba(255, 232, 187, .06), inset 0 0 26px rgba(0, 0, 0, .12), 0 0 0 1px rgba(0, 0, 0, .18); text-align: center; }
.book-cover-title { max-width: 100%; color: var(--cover-ink); font-family: var(--font-display); font-size: clamp(18px, 1.7vw, 24px); font-weight: 500; line-height: 1.17; overflow-wrap: break-word; word-break: normal; text-transform: uppercase; text-shadow: var(--cover-text-shadow); }
.book-cover-rule { width: 32px; border-top: 1px solid var(--cover-rule); }
.book-cover-author { color: var(--cover-ink); font-family: var(--font-display); font-size: 11px; letter-spacing: .07em; line-height: 1.35; overflow-wrap: anywhere; text-transform: uppercase; text-shadow: var(--cover-text-shadow); }
.cover-theme-0 { --cover-bg:#481a17; --cover-ink:#e8c786; --cover-rule:#ad753e; --cover-edge:#25100f; --cover-texture:var(--texture-leather); }
.cover-theme-1 { --cover-bg:#cbb58f; --cover-ink:#231c16; --cover-rule:#765d3e; --cover-edge:#887252; --cover-texture:var(--texture-linen); }
.cover-theme-2 { --cover-bg:#101c25; --cover-ink:#e0b873; --cover-rule:#8f6638; --cover-edge:#080e13; --cover-texture:var(--texture-cloth); }
.cover-theme-3 { --cover-bg:#173024; --cover-ink:#d9bd79; --cover-rule:#94703c; --cover-edge:#0a1710; --cover-texture:var(--texture-cloth); }
.cover-theme-4 { --cover-bg:#22201e; --cover-ink:#e2d0ae; --cover-rule:#777067; --cover-edge:#0e0d0c; --cover-texture:var(--texture-dark-paper); }
.cover-theme-5 { --cover-bg:#78352a; --cover-ink:#f0d7b2; --cover-rule:#d19d60; --cover-edge:#351713; --cover-texture:var(--texture-leather); }
.cover-theme-6 { --cover-bg:#9d998a; --cover-ink:#172632; --cover-rule:#495b67; --cover-edge:#535149; --cover-texture:var(--texture-linen); }
.cover-theme-7 { --cover-bg:#382039; --cover-ink:#e3c885; --cover-rule:#9f754b; --cover-edge:#190f1a; --cover-texture:var(--texture-cloth); }
.cover-theme-8 { --cover-bg:#ae8b61; --cover-ink:#2c1b12; --cover-rule:#6e472c; --cover-edge:#62472d; --cover-texture:var(--texture-paper); }
.cover-theme-9 { --cover-bg:#303942; --cover-ink:#dce0dc; --cover-rule:#89959c; --cover-edge:#161b20; --cover-texture:var(--texture-cloth); }
.cover-theme-10 { --cover-bg:#4b5631; --cover-ink:#efe3bb; --cover-rule:#b49a5e; --cover-edge:#252b18; --cover-texture:var(--texture-cloth); }
.cover-theme-11 { --cover-bg:#8b3f25; --cover-ink:#f2dec0; --cover-rule:#d2a66a; --cover-edge:#3d1b11; --cover-texture:var(--texture-leather); }
.cover-theme-12 { --cover-bg:#111b2c; --cover-ink:#d59a5d; --cover-rule:#805832; --cover-edge:#080d16; --cover-texture:var(--texture-dark-paper); }
.cover-theme-13 { --cover-bg:#d0c4a6; --cover-ink:#244434; --cover-rule:#5e7a62; --cover-edge:#83785e; --cover-texture:var(--texture-linen); }
.cover-theme-14 { --cover-bg:#c6b08a; --cover-ink:#231b14; --cover-rule:#745738; --cover-edge:#776344; --cover-texture:var(--texture-paper); --cover-text-shadow:0 1px rgba(255,255,255,.36); }
.cover-theme-15 { --cover-bg:#5b1821; --cover-ink:#e8cfa0; --cover-rule:#b78954; --cover-edge:#290b0f; --cover-texture:var(--texture-leather); }
.cover-theme-16 { --cover-bg:#ddd0b1; --cover-ink:#1c3551; --cover-rule:#6d7f8f; --cover-edge:#8e8063; --cover-texture:var(--texture-linen); }
.cover-theme-17 { --cover-bg:#171514; --cover-ink:#d9b77c; --cover-rule:#7c2724; --cover-edge:#080706; --cover-texture:var(--texture-leather); }
.cover-theme-18 { --cover-bg:#404825; --cover-ink:#e4c379; --cover-rule:#8d713a; --cover-edge:#202413; --cover-texture:var(--texture-cloth); }
.cover-theme-19 { --cover-bg:#1d3044; --cover-ink:#ead7b2; --cover-rule:#987957; --cover-edge:#0d1721; --cover-texture:var(--texture-dark-paper); }
.cover-theme-1, .cover-theme-6, .cover-theme-8, .cover-theme-13, .cover-theme-16 { --cover-text-shadow: 0 1px rgba(255,255,255,.34); }
.cover-theme-5 .book-cover-frame, .cover-theme-6 .book-cover-frame, .cover-theme-7 .book-cover-frame, .cover-theme-8 .book-cover-frame, .cover-theme-9 .book-cover-frame { border-width: 1px 4px; }
.cover-theme-10 .book-cover-frame, .cover-theme-11 .book-cover-frame, .cover-theme-12 .book-cover-frame, .cover-theme-13 .book-cover-frame, .cover-theme-14 .book-cover-frame { justify-content: space-between; border-width: 4px 1px; }
.cover-theme-15 .book-cover-frame, .cover-theme-16 .book-cover-frame, .cover-theme-17 .book-cover-frame, .cover-theme-18 .book-cover-frame, .cover-theme-19 .book-cover-frame { border-style: solid; box-shadow: inset 0 0 0 5px var(--cover-bg), inset 0 0 0 6px var(--cover-rule); }
.catalog-book-info { min-width: 0; padding-top: 18px; text-align: center; }
.catalog-book-info h2 { margin: 0; color: var(--ink); font-size: 24px; line-height: 1.12; overflow-wrap: anywhere; }
.book-author { margin: 8px 0 0; color: var(--ink-soft); font-family: var(--font-display); font-size: 16px; line-height: 1.15; overflow-wrap: anywhere; }
.book-language { justify-content: center; display: flex; align-items: center; gap: 7px; margin: 9px 0 14px; color: var(--ink-soft); font-size: 12px; }
.book-language img { width: 18px; height: 18px; }
.book-date { margin: 5px 0 0; color: var(--ink-muted); font-size: 11px; }
.book-downloads { display: grid; grid-template-columns: 1fr; gap: 8px; }
.book-downloads .button { min-width: 0; min-height: 44px; gap: 5px; padding: 0 10px; font-size: 12px; line-height: 1; white-space: nowrap; }
.book-downloads .button img { width: 18px; height: 18px; }
.book-downloads .button-primary { background-color: #6e4a22; border-color: #8d6030; color: #f4dfb8; }
.catalog-empty { grid-column: 1 / -1; }
.site-footer { position: relative; z-index: 1; margin-top: 50px; padding-top: 18px; border-top: 1px solid var(--rule-soft); color: var(--ink-muted); font-size: 11px; overflow-wrap: anywhere; }
.site-footer a { color: var(--brass-bright); }
.is-hidden { display: none !important; }
@media (max-width: 1100px) {
  .catalog-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 980px) {
  .library-app { display: block; }
  .library-app::before, .library-app::after { position: absolute; inset: 0; }
  .app-navigation { position: sticky; inset: auto; width: auto; height: auto; flex-direction: row; align-items: center; justify-content: space-between; gap: 20px; padding: 14px 24px; border-right: 0; border-bottom: 1px solid var(--rule); background-position: center 72%, center; contain: none; }
  .lamp-toggle { display: none; }
  .lamp-easter-egg-message { display: none; }
  .app-brand { flex-direction: row; gap: 10px; text-align: left; }
  .app-brand img { width: 38px; height: 38px; }
  .app-navigation nav { display: flex; gap: 6px; }
  .nav-link { min-height: 44px; padding: 0 14px; }
  .app-content { grid-column: auto; padding-top: 36px; }
  .upload-workspace { gap: 30px; }
}
@media (max-width: 860px) {
  .job { grid-template-columns: 1fr; gap: 16px; }
  .job-actions { align-items: stretch; }
  .job-actions .button { width: 100%; }
}
@media (max-width: 760px) {
  .page-header, .catalog-header { align-items: stretch; flex-direction: column; }
  .catalog-tools { width: 100%; }
  .upload-workspace { grid-template-columns: 1fr; }
  .translation-settings { padding-top: 0; }
  .service-explainer { padding: 25px 24px 21px; }
  .service-explainer-heading { align-items: flex-start; flex-direction: column; gap: 7px; }
  .service-steps { grid-template-columns: 1fr; gap: 17px; }
  .service-step { padding: 17px 0 0; border-top: 1px solid var(--rule-soft); border-left: 0; }
  .service-step:first-child { padding-top: 0; border-top: 0; }
}
@media (max-width: 640px) {
  .app-navigation { align-items: stretch; flex-direction: column; gap: 10px; padding: 11px 14px 13px; background-color: #07100e; background-image: var(--texture-dark-paper); background-position: center; background-size: 480px 480px; box-shadow: 0 12px 28px rgba(0, 0, 0, .38), inset 0 -1px rgba(224, 173, 100, .12); }
  .app-navigation::before { background: rgba(1, 6, 5, .18); }
  .app-brand { justify-content: center; gap: 8px; font-size: 20px; }
  .app-brand img { width: 36px; height: 36px; }
  .mobile-crest-toggle {
    position: absolute;
    z-index: 2;
    top: 50%;
    left: -4px;
    width: 44px;
    height: 44px;
    display: block;
    padding: 0;
    border: 0;
    border-radius: 50%;
    background: transparent;
    cursor: pointer;
    touch-action: manipulation;
    transform: translateY(-50%);
  }
  .mobile-crest-toggle:focus-visible { outline: 1px solid var(--brass-bright); outline-offset: 3px; }
  .app-navigation nav { width: 100%; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 3px; padding: 3px; border: 1px solid var(--rule); border-radius: 8px; background: rgba(2, 8, 7, .76); box-shadow: inset 0 1px rgba(255, 239, 208, .035); }
  .nav-link { min-width: 0; min-height: 40px; justify-content: center; gap: 7px; padding: 0 8px; border-radius: 5px; }
  .nav-link > span:not(.nav-count) { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .nav-link.active { box-shadow: inset 0 1px rgba(255, 233, 195, .16), inset 0 -8px 16px rgba(41, 21, 4, .18), 0 4px 12px rgba(0, 0, 0, .22); }
  .nav-count { display: none; }
  .app-content { padding: 28px 16px 54px; }
  .page-header { margin-bottom: 26px; }
  .page-header h1 { font-size: 44px; }
  .quiet-link { width: 100%; }
  .file-picker { min-height: 190px; padding: 22px; }
  .service-explainer { margin-top: 26px; padding: 22px 18px 19px; }
  .service-step { grid-template-columns: 34px minmax(0, 1fr); gap: 11px; }
  .service-step-icon { width: 34px; height: 34px; }
  .service-step h3 { font-size: 18px; }
  .catalog-tools { align-items: stretch; flex-direction: column; }
  .catalog-tools .button { width: 100%; }
  .catalog-grid { grid-template-columns: 1fr; row-gap: 34px; }
  .catalog-book { display: grid; grid-template-columns: 118px minmax(0, 1fr); gap: 17px; align-items: start; }
  .book-cover { width: 118px; min-height: 177px; margin-inline: 0; padding: 7px; border-left-width: 7px; box-shadow: inset 2px 0 rgba(255, 236, 198, .07), inset 8px 0 12px rgba(0, 0, 0, .24), inset -7px 0 14px rgba(0, 0, 0, .12), inset 0 -18px 22px rgba(0, 0, 0, .22), 0 13px 25px rgba(0, 0, 0, .36), 0 4px 7px rgba(0, 0, 0, .32); }
  .catalog-book:hover .book-cover { transform: none; box-shadow: inset 2px 0 rgba(255, 236, 198, .07), inset 8px 0 12px rgba(0, 0, 0, .24), inset -7px 0 14px rgba(0, 0, 0, .12), inset 0 -18px 22px rgba(0, 0, 0, .22), 0 13px 25px rgba(0, 0, 0, .36), 0 4px 7px rgba(0, 0, 0, .32); }
  .book-cover-frame { gap: 9px; padding: 12px 7px; }
  .book-cover-title { font-size: 15px; }
  .book-cover-author { font-size: 8px; }
  .catalog-book-info { padding-top: 0; text-align: left; }
  .catalog-book-info h2 { font-size: 19px; }
  .book-author { font-size: 14px; }
  .book-language { justify-content: flex-start; }
  .book-downloads .button { min-height: 42px; }
  .book-downloads .button > span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .site-footer { margin-top: 34px; }
  .lamp-easter-egg-message {
    top: auto;
    right: 16px;
    bottom: calc(16px + env(safe-area-inset-bottom));
    left: 16px;
    width: auto;
    max-height: calc(100dvh - 32px);
    display: block;
    overflow: auto;
    padding: 34px 24px 25px;
    transform: translateY(24px);
  }
  .lamp-easter-egg-message blockquote { font-size: clamp(26px, 8vw, 34px); line-height: 1.1; }
  .lamp-easter-egg-message figcaption { margin-top: 14px; font-size: 17px; }
  .lamp-easter-egg-close { top: 9px; right: 9px; width: 36px; height: 36px; }
  .mobile-easter-egg-active .lamp-easter-egg-message { animation: mobile-easter-egg-message .62s ease-out both; }
  .mobile-easter-egg-active .app-brand img { animation: lamp-easter-egg-crest 1.4s ease-in-out both; }
  .mobile-easter-egg-active .catalog-book .book-cover { animation: mobile-book-awakens .82s ease-in-out both; }
  .mobile-easter-egg-active .catalog-book:nth-child(2) .book-cover { animation-delay: .08s; }
  .mobile-easter-egg-active .catalog-book:nth-child(3) .book-cover { animation-delay: .16s; }
  .mobile-easter-egg-active .catalog-book:nth-child(4) .book-cover { animation-delay: .24s; }
  .mobile-easter-egg-active .catalog-book:nth-child(5) .book-cover { animation-delay: .32s; }
  .mobile-easter-egg-active .catalog-book:nth-child(6) .book-cover { animation-delay: .4s; }
  @keyframes mobile-easter-egg-message {
    from { visibility: visible; opacity: 0; transform: translateY(24px); }
    to { visibility: visible; opacity: 1; transform: translateY(0); }
  }
  @keyframes mobile-book-awakens {
    0%, 100% { transform: translateY(0); }
    44% { transform: translateY(-6px); }
  }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; }
  .app-navigation.lamp-flicker-on::after,
  .app-navigation.lamp-flicker-off::after { animation: none !important; }
  .library-app.lamp-easter-egg-active::before,
  .lamp-easter-egg-active .app-brand img,
  .lamp-easter-egg-active .catalog-book .book-cover,
  .mobile-easter-egg-active .app-brand img,
  .mobile-easter-egg-active .catalog-book .book-cover { animation: none !important; }
  .lamp-easter-egg-active .lamp-easter-egg-message {
    animation: none !important;
    visibility: visible;
    opacity: 1;
    transform: translate(-50%, -50%);
  }
  .mobile-easter-egg-active .lamp-easter-egg-message {
    animation: none !important;
    visibility: visible;
    opacity: 1;
    transform: translateY(0);
  }
}
@media print {
  .app-navigation, .button, .search-field, .quiet-link { display: none; }
  .library-app { display: block; }
  .library-app::before, .library-app::after { display: none; }
  .app-content { width: 100%; padding: 20px; }
}
</style>"""
