# Open issues

Everything currently known to be broken, missing or undecided, as of
**2026-09-13**. Written after a day whose work opened more than it closed, and
kept separate from `Conversations/pending.md`, which is a historical log rather
than a live list.

Each item says how it was found and what evidence exists, because several
things below were shipped as done and were not.

Status: ☐ open · ☑ done · ◐ needs a decision, not a fix

---

## A. Exploratory data analysis page

Rebuilt today in ml-portfolio commit `a22308b`. Verified against the two
datasets I tested with, which is exactly why the gaps below survived: neither
test exercised them, and the parity check was against my own spec rather than
against the legacy page.

| # | S | Item | Detail |
|---|---|---|---|
| A1 | ☑ | **No card thumbnail** | Done 2026-09-13 — layered sandstone, Pexels 20015727, in ml-portfolio `2ae31d2`. Chosen by hand after the picker's contrast score twice ranked an unusable photo first; see that commit for the two selector weaknesses worth fixing later. |
| A2 | ☑ | **Statistics section missing entirely** | Done 2026-09-13 — `EdaStatistics.tsx`. Outliers (IQR) ranked bars, signed Skewness bars around a centre line, and the 9-column detail table. Nav entry added. |
| A3 | ☑ | **Columns missing-% is a table, not a chart** | Done 2026-09-13 — `EdaColumns.tsx` rewritten as the labelled bar list: num/cat badge, name, bar, percentage, with dtype, missing count and cardinality beneath. The old table's numbers now live in the statistics panel. |
| A4 | ☑ | **Report is light even in dark theme** | Done 2026-09-13 in ml-portfolio `575bd7f`, then fixed properly in `4904319`. The first attempt printed near-black text on the dark panels: print-color-adjust was declared in the sheet PagedJS rewrites and never reached the page. Found only after rendering a real PDF — the on-screen paginated preview measured correct, because the damage happens in Chrome's print rasteriser, not the cascade. |
| A5 | ☐ | **Section nav has no Statistics entry** | Follows from A2. `EdaSectionNav.tsx` lists 14 anchors; legacy lists Statistics between Columns and Distributions. |
| A6 | ☑ | **Legacy-vs-rebuild parity audit** | Done 2026-09-13 against `services/ml-api/frontend/eda.html`, panel by panel. Result in the table below. Found A7–A10 on top of A1–A5. |
| A7 | ☑ | **ML readiness reasons are hidden in a tooltip** | Done 2026-09-13 — `EdaReadiness.tsx`. Card grid, reason as body text, Ready/Review/Fix label, inline SVG verdict icons. e2e asserts the reason is rendered content, not a tooltip. |
| A8 | ☑ | **Low-variance badge missing from distribution cards** | Done 2026-09-13 — badge on the distribution card of each low-variance column. |
| A9 | ☑ | **Analyst summary is not its own section** | Done 2026-09-13 — narrative is its own `#summary` section with a nav tab. A new e2e test walks every nav tab and fails if one points at a section that does not exist. |
| A10 | ☑ | **Panel headers lost their context lines** | Done 2026-09-13 — `meta` slot on `EdaSection`; filename on Overview, counts on Columns, Sample, Distributions, Spread, Mutual info, SPLOM, PCA and Correlations. |

### A6 audit result — legacy `?mode=eda` vs the rebuild

Legacy renders 15 panels and 12 nav tabs. Read from `eda.html` lines 840–1180.

| Legacy panel | Rebuild | Verdict |
|---|---|---|
| Overview — 5 chips, quality ring, filename, export button | `#overview` — 5 cards, gauge | Parity, minus the filename (A10) |
| Analyst Summary — own card, own nav tab | folded into `#overview` | **A9** |
| ML Readiness — card grid, reason visible, Ready/Review/Fix | `#readiness` — chips, reason in `title` | **A7 regression** |
| Smart Insights | `#insights` | Parity; rebuild better, no emoji |
| AI Feature Suggestions — 4 providers | `#suggestions` — 5 incl. auto, names who answered | Rebuild better |
| Sample Data — first 5 rows | `#sample` | Parity |
| *(legacy has none)* | `#duplicates` | Rebuild adds this |
| Columns — labelled bar per column, num/cat badge, dtype, missing count, unique count | `#columns` — wide table, 52px bar | **A3 regression** |
| **Statistics — Outliers (IQR) ranked bars, Skewness diverging bars, 9-column detail table** | *(absent)* | **A2 missing** |
| Distributions — per-card "⚠ low variance" badge | `#distributions` | **A8** |
| Box Plots — one shared axis | `#box-plots` — faceted, own axis each | Rebuild better |
| Mutual Information | `#mutual-information` | Parity |
| PCA 3D | `#pca` | Parity |
| SPLOM | `#splom` | Parity |
| Correlation Heatmap | `#correlations` — marks uncomputable cells n/a | Rebuild better |
| HTML export | `#report` — PDF and HTML | Rebuild better, but **A4** |
| *(legacy has none)* | `#clean` | Rebuild adds this |

Nothing else in the legacy page is unaccounted for. Six panels are at parity,
five are better in the rebuild, two are additions, and five defects are logged
above.

### A note on how section A was verified

Two defects in this section shipped as "verified" and were caught by the user
instead: the missing Statistics panel (A2), and a dark PDF whose text was
illegible (A4). Both share a cause worth stating rather than filing away.

Each was checked against a proxy for the deliverable. A2 was checked against
the build spec I had written, not against the page it was reproducing. A4 was
checked against the on-screen paginated preview, not against a printed PDF —
and `getComputedStyle` reported the correct colours there, because Chrome's
print rasteriser does the damage downstream of the cascade.

The rule that follows: check the artefact the reader receives. Render the PDF,
open the downloaded file, compare against the page being replaced. Every one
of these took minutes once actually done.

---

## B. Dependency upgrades

26 of 28 Dependabot pull requests merged today across both repositories, main
green after every batch. Two remain, both for stated reasons.

| # | S | Item | Detail |
|---|---|---|---|
| B1 | ☑ | **ML-Unified #6 — opencv-python-headless 5.0** | Done 2026-09-13 — `554b531` lifted ml-api to numpy 2.4.6, then #6 merged as `d7748c9`. The blocker was only the pin: opencv 5.0.0.93 declares numpy>=2. Nothing in the codebase used an API opencv 5 removed — all 73 cv2 symbols checked against 5.0.0, and the one apparent miss was prose in a docstring. All 12 pickles load and predict correctly under numpy 2. Full suite green on the PR and on main. |
| B2 | ☐ | **ml-portfolio #5 — next 16.3.4** | Every CI check passes. Only the Vercel preview deployment fails, twice. `npm install && npm run build` on that exact branch succeeds locally and other previews plus production deploy fine, so it is specific to this PR but platform-side. No Vercel log access from here, so the cause is **not** established. |

---

## C. Deploy drift

| # | S | Item | Detail |
|---|---|---|---|
| C1 | ☑ | **Space and repo disagree on three major versions** | Done 2026-09-13 — Space rebuilt on numpy 2.4.6, pandas 3.0.5, opencv 5.0.0.93, spacy 3.8.16, thinc 8.3.13, fastapi 0.141.1, confirmed from the build log rather than inferred. First attempt failed and took the backend down for a few minutes: spacy 3.7.5's thinc is compiled against the numpy 1 ABI. Rolled back, fixed in `1d7ebbe`, redeployed. Verified live: predictions byte-identical to before, EDA works including the five-row case, RAG healthy. facenet-pytorch's numpy<2 bound is knowingly violated and was checked by running it — see the Dockerfile. |

### What C1 cost, and what it bought

The first deploy failed and the backend was down for roughly four minutes.
The cause was a dependency that installs cleanly and only fails on import, so
nothing before the deploy could see it — CI had been green for hours while
main was un-deployable.

That is the exact gap C1 existed to close, and it closed it in the worst way
round. Two things came out of it worth keeping:

* `services/ml-api/tests/test_native_abi.py` imports every dependency with a
  compiled extension, because an import is the only thing that exercises a
  binary interface. It would have caught this before the deploy.
* Rolling back is cheap and should be the reflex. Re-uploading the previous
  requirements restored service in about four minutes, and having saved those
  files *before* uploading is what made that a decision rather than a scramble.

Still not covered: no Docker on the development machine, so the Space's image
cannot be built locally. The next requirements change of this size should go
to a duplicate Space first.

---

## D. Repository hygiene — gates going public

The user intends to make these repositories public. Full-history gitleaks over
both is clean: 1004 commits in ML-Unified, 1057 in ml-portfolio, no findings,
and the indexed chroma text carries no secret-shaped strings either.

| # | S | Item | Detail |
|---|---|---|---|
| D1 | ◐ | **No LICENSE, and AGPL-3.0 weights committed** | `yolov8s-oiv7.onnx` (44 MB) and `yolov8n-ppe.onnx` (12 MB) are Ultralytics YOLOv8, which claims AGPL-3.0 even when exported — researched previously and accepted as a private-repo risk. Neither repository has a `LICENSE` file, so "public" currently means all rights reserved. AGPL's network clause targets exactly a hosted service. **This is the blocker for going public.** |
| D2 | ☐ | **`signature-detector.onnx` provenance untraced** | 36 MB, detector-shaped, licence unknown. Check before publishing. |
| D3 | ☐ | **Gitignored runtime junk is tracked on main** | `services/ml-api/data/chroma_db/chroma.sqlite3` (46.8 MB), its index binaries (~3.5 MB), `catboost_info/`, `models/ci-test-*.pkl`, `schemas/ci-test-*.json`, and three root `test_*` files. All match `.gitignore:26-28` and are tracked anyway. `git rm --cached` is a safe one-commit fix; purging history is a force-push and a separate decision. |
| D4 | ☐ | **Unexplained: how the junk got committed** | Every one of those files entered main via `ff5f4c2`, the squash merge of Dependabot PR #22 (httpx). A dependency bump cannot add gitignored binaries, so something upstream of it did, and until that is understood it recurs. |
| D5 | ☐ | **CI gitleaks scans PR diffs only** | `.github/workflows/ci.yml` runs gitleaks over a pull request's own commits. History has never been scanned by CI — today's clean result came from a local run. Add a full-history job so "clean" stays provable rather than a one-off. |
| D6 | ◐ | **History rewrite: worth it only bundled with D1** | Repo is 135 MB, but ~128 MB is intentional model weights. Removing chroma alone saves 26% for a force-push on shared main — not worth it standalone. If D1 removes the YOLO weights, one pass drops ~103 MB and lands near 30 MB. Decide D1 first. |

---

## E. Carried over — hardening plan and file limits

Open before today and untouched by it.

| # | S | Item | Detail |
|---|---|---|---|
| E1 | ☐ | Vercel WAF edge rate limiting | Hardening plan Gap 1 |
| E2 | ☐ | OWASP LLM Top 10 2026 audit | Hardening plan Gap 2 |
| E3 | ☐ | Provider-failure alerting outside the document path | Hardening plan Gap 3, remainder |
| E4 | ☐ | ml-sql's two untested provider paths | No coverage |
| E5 | ☐ | `mm_pdf.py` (373) and `_generate.py` (366) | Both approaching the 400-line gate; split before adding to either |
| E6 | ☐ | Handbook clips at 25 of 50 | Half the tools missing from the published handbook |
| E7 | ☐ | Stale file-length baseline entry | `check-file-length.sh` reports `automl_stage.py: now 336 lines — remove its baseline entry` |

---

## Suggested order

1. ~~A6 first.~~ Done — and it was worth doing: it found A7–A10, including
   a readiness regression that no spec checklist would have caught.
2. ~~A2, A3, A7, A8, A9, A10 as one batch.~~ Done 2026-09-13. Verified live
   against two datasets plus 66 passing e2e tests, four of them new.
3. ~~A1, A4~~ done. **Section A is closed.** Every item found by the parity
   audit and by the user's screenshots is fixed and verified live.
4. **D1** whenever the public plan firms up — it gates D3, D6 and the flip
   itself, and everything else in D is cheap once it is decided.
5. ~~B1, C1~~ done. Sections B and C are closed apart from B2.
6. B2 and section E are independent and can wait.
