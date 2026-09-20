# Part 295 — Three platform worlds, then reskinning the apps to match

Continues [Part 294](Session_2026-09-19_Phase2ToFourStagesLive_Part294.md).
2026-09-20. Picked up the top deferred item from Part 294 (turn the three external
platforms into native worlds), shipped it, then — at the user's push — made the
actual HF Space **apps** look like the portfolio too. Ended on course research and
a usage stop at 95% weekly.

The through-line: **the brand is constant, the platform accent varies — and
"match the design" means the header too, not just the fonts.**

---

## 1. Three native platform worlds (ml-portfolio)

Turned the last three external-app cards into native worlds like `/qa` and `/sql`.
All three are modes of one HF Space (`?mode=ml|eda|vision`).

- **`/ml`** ML Unified (fuchsia), **`/eda`** EDA Explorer (emerald), **`/vision`**
  ML Vision (violet). Each = `theme.ts` + `guide.ts` + `layout.tsx`
  (WorldShell/WorldNav) + `page.tsx` + `sections/(Capabilities+HowScope)`, reusing
  the shared `WorldShell`/`WorldNav`/`WorldUserGuideModal` + `ToolsAIChat`. Hero has
  a signature panel (ML predict / EDA profile-histogram / Vision confidence-bars),
  User Guide modal, honest-scope cards.
- Copy verified against the backend: 4 ML models with real held-out metrics
  (Iris 96.7 / Titanic 82.5 / Diabetes 77.5 / Insurance ±668 MAE); EDA post-rebuild
  sections (3D PCA, SPLOM, MI, PDF+HTML report); Vision 4 classifier backbones,
  COCO-80, ADE20K-150.
- `WorldNav` gained an opt-in `external` flag so "Open the platform" opens the HF
  Space in a new tab. `registry.json` entries flipped to `internal:true` + `href`
  (cards now show **Enter**).
- Commits: ml-portfolio `8f2e5d7` (ml + WorldNav.external), `64e8b40` (eda+vision).
  Verified live end-to-end. Frontend-only, no backend.

---

## 2. Reskinning the three HF Space apps to the landing-world design (ML-Unified)

The user then wanted the **apps that open** (`index.html`=ml, `eda.html`,
`vision.html`, all sharing `common.css`) to look like the portfolio, not their old
sidebar chrome. It took three rounds to get right — a good lesson in not
under-scoping "make it look like X."

- **`3ed80c5` — fonts/palette/accent.** Light palette aligned to the portfolio
  (`--bg #f0f4f8`, `--bg-card #fff`); **Archivo** on the display headings (body
  stays Geist); per-mode gradient accent via `[data-mode]` (ml fuchsia / eda
  emerald / vision violet), set with a one-line inline script on
  `document.documentElement` in each html.
- **`a4b02e8` — the AIRaML nav header.** I'd wrongly scoped the nav out; the user
  showed that the header was the glaring mismatch. Replaced each app's
  `ML Unified/Home/Source/theme-dropdown` bar with the portfolio's **two-bar
  chrome**: Bar 1 = AIRaML wordmark + `Tools/Platforms/How it works/Handbook/Docs/
  About` (→ portfolio) + `Source·AGPL` (auto-injected by `source-notice.js` before
  `#themePickerWrap`, so those must stay) + theme picker; Bar 2 `.world-subnav` =
  platform name (`#nav-title-el`, filled by `common.js` `applyNavMode`) + Overview
  link → the portfolio world. New CSS: `.nav-wordmark`/`.nav-links`/`.world-subnav`.
- **`0fc97b4` — the brand fix (the real "doesn't match").** The AIRaML brand had
  been tinted by the *per-mode* accent (fuchsia/emerald/violet) with a constellation
  logo. The portfolio brand is **constant**: an "AI" square + wordmark on a fixed
  gradient `#818cf8→#38bdf8→#34d399` (light darkens to `#4f46e5→#0369a1→#047857`
  for contrast — the exact values from ml-portfolio `01-tokens.css`). Added
  `--brand-grad` (root + `[data-theme=light]`), applied to `.nav-logo-mark` (now
  text "AI") + `.nav-wordmark`; the per-mode accent stays on the world sub-nav mark,
  Overview link and app content.
- **`8cbbeb9` — dropzone bug.** The Clean & Export dropzone is a
  `<label class="upload-zone">`; `<label>` defaults to `display:inline`, so its
  dashed border fragmented into broken brackets. `display:block` → proper rectangle.

All four commits deployed to HF (upload the 4 changed `frontend/*` files, strip
`services/ml-api/` prefix) and **verified live per mode** (checked the new code was
actually served, not just stage=RUNNING, then screenshotted).

---

## 3. Course research (networking + cyber security)

The user asked for genuine, non-hallucinated courses for their stack (Vercel +
GitHub Actions + live LLM features), then narrowed to **YouTube only, no
freeCodeCamp, Hindi or English, sequenced**. Verified everything via web search.
The curated, sequenced path:

- **Networking (app layer):** EN Hussein Nasser "HTTP" then "Network Engineering"
  playlists; HI Hitesh Choudhary "Chai aur Javascript Backend"; (optional HI theory)
  Gate Smashers "Computer Networks".
- **Web security:** EN The Cyber Mentor "Ethical Hacking in 15 Hours"; HI Bitten
  Tech "Ethical Hacking & Penetration Testing – Complete Course" or WsCube "Ethical
  Hacking Full Course In Hindi"; then hands-on EN Rana Khalil "Web Security Academy"
  playlists (SQLi/XSS/Access Control) alongside PortSwigger labs; PwnFunction for
  quick concept explainers.
- Skipped CCNA/hardware channels (NetworkChuck, David Bombal) as irrelevant to a
  Vercel+API stack. Full list with links is in the session transcript, not repeated
  here.

---

## Commits

| Repo | Commits |
|---|---|
| ml-portfolio | `8f2e5d7` (ml world + WorldNav.external) · `64e8b40` (eda+vision worlds) |
| ML-Unified | `3ed80c5` (app reskin: fonts/palette/accent) · `a4b02e8` (AIRaML nav header) · `0fc97b4` (fixed brand gradient) · `8cbbeb9` (upload-zone display:block) |

---

## Still pending (next session)

- **Handbook** — teach `scripts/build-handbook.py` to keep graduated-tool chapters
  (Text-to-SQL) + add a Testwright chapter, reference the 3 new native worlds, and
  pull in the **4 newly-added Security & Trust tools missing from the current
  handbook** (`exploit-payload-detector`, `secret-scanner`, `jwt-analyzer`,
  `intrusion-detection` — a regenerate picks these up automatically since they're in
  `capabilities.ts`), then regenerate + diff before committing.
- The 5 Testwright backlog items (flakiness detection first).

---

## Lessons

- **"Make it look like X" includes the chrome.** Font/palette/accent alone read as
  "close but off"; the header was what actually made the apps feel like a different
  product. Don't scope the most visible element out.
- **Brand is constant, accent is contextual.** The AIRaML brand gradient must be
  fixed across every world; only the per-platform accent varies. Tying the brand to
  the per-mode accent was the root of "the design doesn't match."
- **A `<label>` styled as a box needs `display:block`** — inline labels fragment
  their border across line boxes.
- **Verify genuine before recommending.** The user had been burned by hallucinated
  course names; every course here was confirmed live via search first.
