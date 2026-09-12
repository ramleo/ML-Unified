# EDA page rebuild — build spec

Agreed 2026-09-12, to be built 2026-09-13. Written to survive a context
compaction: everything needed to start is here, no session history required.

**The goal in one line:** bring `/tools/exploratory-data-analysis` up to the
legacy Explorer's capability — interactive Plotly charts, 3D PCA, box plots,
mutual information, scatter-plot matrix, and a downloadable report — and fix
the places the legacy page is weak.

Reference to build against: <https://wram1708-ml-unified.hf.space/?mode=eda>
(source: `services/ml-api/frontend/eda.html`, 1961 lines, plain HTML + Plotly).

---

## 1. Decisions already made

| Question | Decision |
|---|---|
| Parity level | Same sections as legacy, **plus** fixes where legacy is weak (§5) |
| Report format | **Both** PDF and HTML |
| Existing static SVG charts | **Replaced** by Plotly, deleted |
| Plotly delivery | **CDN**, `https://cdn.plot.ly/plotly-2.27.0.min.js`, this route only |
| Legacy `?mode=eda` page | **Keep for now**, decide after the rebuild ships |
| AI provider control | **Picker defaulting to auto**, all providers selectable |

The CSP in `ml-portfolio/next.config.*` already allows `script-src ... https:`,
so the CDN needs no config change. PagedJS is already vendored for the PDF path:
`scripts/copy-pagedjs.mjs` copies it to `public/vendor/paged.min.js` on
prebuild and predev.

---

## 2. The analysis is not changing

Both pages call the same endpoint and receive the same JSON. **No backend work
is required for the charts.** The rebuild is entirely rendering.

`POST /eda` (multipart, field `file`, CSV, 10 MB cap) returns 15 keys. The
current page renders 8 of them and ignores 6.

### Already rendered
`overview`, `columns`, `stats`, `distributions`, `correlations`, `insights`,
`quality_score`, `readiness`, `narrative`

### Returned and currently ignored — this is the gap

| Key | Shape | Legacy draws |
|---|---|---|
| `pca` | `{coords: [n×3], explained_variance: [3], labels: [7], color_col, cat_cols: [9], cat_color_map: {col: [n]}}` | Plotly `scatter3d`, Turbo colourscale, colour-by picker |
| `splom` | `{cols: [7], data: {col: [n]}, n, color_col, color_vals: [n], color_map: {col: [n]}}` | Plotly `splom`, `showupperhalf: false`, colour-by picker |
| `mi` | `{labels: [12], matrix: [12×12]}` | Plotly `heatmap`, Viridis, 0–1 |
| `stats[col].raw_vals` | up to 300 sampled values per numeric column | Plotly `box`, `boxpoints: 'outliers'` |
| `sample` | `{columns: [], rows: [5×n]}` | First-5-rows table |
| `duplicate_rows` | same shape as `sample`, or `null` | Table, only when duplicates exist |
| `low_variance_cols` | `[str]` | Flagged in readiness |

The backend already caps sizes: `raw_vals` samples at 300, `splom` samples rows
(149 of 199 in testing), `distributions` covers the first 12 numeric and 6
categorical columns. **Do not add client-side sampling on top.**

Other endpoints, unchanged: `POST /eda/clean` (multipart `file` + `config`
JSON string) and `POST /eda/suggest` (JSON body, SSE stream).

---

## 3. Files

### Backend — no changes expected
`services/ml-api/routers/eda/` — `router.py` (`/eda`, `/eda/clean`),
`_suggest.py` (`/eda/suggest`), `_stats.py`, `_readiness.py`, `_clean.py`,
`_utils.py`. Mounted in `app.py:224-225`.

### Frontend — the work
`ml-portfolio/src/app/tools/exploratory-data-analysis/`

| File | Now | Tomorrow |
|---|---|---|
| `page.tsx` | shell, nav, AI chat context | add section nav, extend chat context |
| `EdaRunner.tsx` | upload + orchestration | add the new sections |
| `EdaOverview.tsx` | stats, narrative, insights, readiness | keep, add quality gauge |
| `EdaColumns.tsx` | column table | keep, add missing-% bars |
| `EdaCharts.tsx` | static SVG bars + heatmap | **delete**, replaced by Plotly components |
| `EdaActions.tsx` | suggestions + clean/export | split; add provider picker |
| `edaTypes.ts` | types, `mi`/`pca`/`splom` are `unknown` | type them properly |

New files expected: a Plotly loader hook, one component per chart type, a
report builder, and a section nav. **No file over 400 lines; modularise
anything over 350 before adding to it.** That limit is enforced by
`scripts/check-file-length.sh` in CI and applies to `.md` too.

---

## 4. Sections to build, in page order

1. **Overview** — stat cards, plus the quality gauge the legacy page has
2. **Analyst summary** — `narrative` (exists)
3. **ML readiness** — per-column pass/warn/fail (exists)
4. **Smart insights** — severity-coded (exists)
5. **AI feature suggestions** — add provider picker, keep the served-provider label
6. **Sample** — first 5 rows, and duplicate rows when `duplicate_rows` is not null
7. **Columns** — table (exists), add missing-% bars
8. **Statistics** — outlier and skew summary, plus the full table
9. **Distributions** — Plotly histograms and bar charts
10. **Box plots** — Plotly, IQR fences, outliers as dots
11. **Mutual information** — Plotly heatmap, Viridis
12. **SPLOM** — Plotly, colour-by picker
13. **PCA 3D** — Plotly `scatter3d`, colour-by picker, explained variance shown
14. **Correlations** — Plotly heatmap, RdBu, `zmid: 0`
15. **Clean and export** — keep inline (exists)
16. **Report download** — PDF and HTML

Plus a sticky in-page section nav, as the legacy page has.

---

## 5. Where the legacy page is weak — fix these

Agreed scope. Veto any of these tomorrow if you disagree.

1. **`null` shown as text.** The legacy statistics table prints a literal
   "null" for an undefined kurtosis. Render an em dash. A statistic that does
   not exist and a statistic that is zero are different facts.
2. **No empty states.** A dataset with one numeric column produces an empty
   correlation panel with no explanation. Say why it is empty.
3. **Uncomputable correlations look like zero.** The current page already draws
   these hollow with a dashed outline; carry that into the Plotly version
   rather than letting Plotly render a null cell as mid-scale.
4. **Labels clip and overflow on narrow screens.** Every wide chart needs its
   own `overflow-x: auto` container, and **every grid item needs
   `minWidth: 0`** — see §8.
5. **No error surfacing.** Legacy shows a generic failure. Surface the server's
   own message; a bare "analysis failed" is how the backend's 500 went
   unnoticed for months.
6. **Emoji as section icons.** The legacy page uses 🔥 💡 📊 📦 👁 🗂. This
   project's standing rule is inline SVG, never emoji as an icon.

---

## 6. Plotly specifics

- **Load once, on this route only.** A hook that injects the CDN script tag and
  resolves when `window.Plotly` exists. Every chart component waits on it.
  Render a skeleton until then, and a plain message if the script fails —
  never a blank panel.
- **Theming.** The site has a light/dark toggle. Legacy uses
  `paper_bgcolor: 'transparent'`, `plot_bgcolor: 'transparent'` and passes a
  text colour through. Charts must **re-render on theme change**, not just on
  first paint.
- **Chart types needed:** `histogram`, `bar`, `box`, `heatmap` (×2, different
  colourscales), `splom`, `scatter3d`.
- **Responsive.** `{responsive: true}` in the config, and a container that
  scrolls rather than forcing the page wide.

---

## 7. Report download

Both formats, from one capture pass.

- **Capture.** Render each chart offscreen and rasterise to PNG, the way
  `_captureAllEDACharts()` does in the legacy page (around line 1640 of
  `eda.html`). That function is a good reference for the layout dimensions it
  uses per chart.
- **HTML.** One standalone file with the PNGs embedded as data URIs, named
  `<dataset>_eda_report.html`. Matches the legacy behaviour exactly.
- **PDF.** Via the vendored PagedJS at `public/vendor/paged.min.js`. Note the
  comment in `scripts/copy-pagedjs.mjs`: importing PagedJS through the bundler
  throws at runtime, so it must be loaded as a plain script.
- Both buttons disabled while capturing, with visible progress. Capturing
  fourteen charts is not instant.

---

## 8. Standing constraints that apply to this work

- **No file over 400 lines**, any extension. Modularise anything over 350
  before adding to it. CI enforces this.
- **`minWidth: 0` on every grid item.** A grid item defaults to
  `min-width: auto` and will not shrink below its content, so one wide table
  forces the whole page sideways and the table's own scroller never engages.
  This exact bug is currently fixed but **unbuilt** — see §10.
- **`data-wt` anchors** on anything a test or demo recording needs to click.
  These are the site's test selectors; there is no separate `data-testid` set.
- **ConstellationBackground** on every tool page. Already present.
- **An `h1`, not a styled span**, for the page title. Already correct.
- **Inline SVG for icons, never emoji.**
- **Wide containers**, `maxWidth: 1280` as the page already uses.
- Ask before `git commit` in either repository. Never `git add -A`.
- Backend commits require an HF Space upload in the same response.

---

## 9. Testing

- The Playwright route list is read from the filesystem, so the page is already
  covered by a render smoke test. Extend `e2e/` with anchors for the new
  sections.
- **Do not assert on Plotly internals.** Assert that a container exists and is
  non-empty, not on SVG paths a library version can change.
- Backend tests are unaffected: 364 in ml-api, all passing. If any backend
  change does become necessary, it needs tests in the same commit.
- Verify in a real browser before claiming done. Both bugs in the current page
  were found by using it, not by reading it.

---

## 10. Loose end to pick up first

`ml-portfolio/src/app/tools/exploratory-data-analysis/` has an **uncommitted,
unbuilt** fix: `minWidth: 0` added to the section and card styles in
`EdaOverview.tsx`, `EdaColumns.tsx`, `EdaCharts.tsx` and `EdaActions.tsx`.
It fixes horizontal page scroll at narrow widths, caused by the columns
table's 760px minimum. The build was interrupted before it was verified.

Also uncommitted in `EdaCharts.tsx`: the correlation heatmap's font fix. The
SVG had no width, so it stretched to fill its container and scaled roughly
six times, rendering 10px labels at about 60px. Fixed by pinning `width` and
`height` to the viewBox. **That file is being deleted in this rebuild**, so
carry the lesson, not the code: an SVG with a viewBox and no width fills its
container and scales its text with it.

---

## 11. Second task for tomorrow

**Merge the 31 Dependabot pull requests** — 23 in ML-Unified, 8 in
ml-portfolio. They were blocked by a gitleaks permission fault, fixed in
`3d7e6d3` (ML-Unified) and earlier in ml-portfolio. Each open pull request
needs rebasing onto main to pick the fix up.

ML-Unified pull request 24 is already rebased and fully green, so merge it
first as proof the batch is safe. Then batch the rest and stop on the first
failure rather than pushing through.
