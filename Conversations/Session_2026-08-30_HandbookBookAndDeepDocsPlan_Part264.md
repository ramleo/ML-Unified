# Session 2026-08-30 (Part 264) — Tools-section finish, per-tool photographs, calmer accents, and the handbook rebuilt as a book

This log exists to survive a context compaction. Everything needed to pick the
handbook work up cold is here: what is built, what is committed, what is not,
every bug already hit and fixed (so they are not hit twice), the exact plan for
the deep per-tool documentation, and the decisions already taken.

---

## 0. Where things stand in one paragraph

The tools section rebuild finished and shipped. The site now has four area
pages, a photograph on every tool card, one shared card surface, calmer accent
colours, and a `/handbook` page carrying a 106-page typeset book generated from
the app's own data. **The handbook work is uncommitted.** The next job, agreed
and not started, is writing deep technical documentation for all 50 tools so the
owner can explain the app in an interview.

---

## 1. Shipped and verified live (ml-portfolio, all pushed)

| Commit | What |
|---|---|
| `06a7d65` | four area pages, bento tiles, keyboard-reachable cards |
| `72bf215` | one card surface for the whole site, PipelineShowcase split |
| `e7777b2` | a photograph on every tool card |
| `a2e7497` | lighter photo tint, back-link to the area page, unpinned search bar |
| `d9fd111` | calmer tool accents that work in both themes |
| `edf9d48` | the first handbook (superseded by the book, below) |

Live URL: `https://ml-portfolio-rho.vercel.app`

### Verified on production, not just built

- Four area routes 200, a bogus slug 404s, all 51 existing tool routes still 200.
- Home shows 1 big + 1 wide + 2 small tiles and **zero** tool cards.
- All 50 thumbnail files return 200; on the Security page 21 cards, 21 images,
  0 broken, 21 unique URLs.
- Every card type computes an identical style signature —
  `rgba(17,24,39,0.6)` fill, `0.75px rgba(255,255,255,0.07)` border, 14px
  radius, same shadow — across platform cards, pipeline stages, architecture
  stages and domain tiles.
- Accents: weakest contrast across all 29 went from **1.58:1 to 4.01:1**; every
  one now near 4.15:1 in both themes. Button labels switched to white
  (near-black measured 3.8–4.0:1, white 4.4–4.7). "Choose photo" reads 4.53:1
  label, 4.21:1 against the page in dark, 4.10:1 in light.
- Back link: Plant Growth → "Computer Vision" → the Computer Vision page. All
  50 tools verified as mapping to the right area.
- Search bar `position: static`, scrolled away 497px on a 500px scroll.

---

## 2. The handbook, as it stands — UNCOMMITTED

### Files

| File | Role |
|---|---|
| `scripts/build-handbook.py` | generates the book from the app's own data |
| `public/handbook.md` | the generated book — 4,135 lines, 236 KB |
| `src/app/handbook/page.tsx` | reads the .md at build time, renders it |
| `src/app/handbook/HandbookActions.tsx` | Download as PDF / Download Markdown |
| `public/book.css` | the paged-media stylesheet Paged.js loads |
| `src/app/styles/09-handbook.css` | screen styles for the page |
| `src/app/styles/10-print.css` | print rules; loaded last |
| `scripts/copy-pagedjs.mjs` | copies Paged.js's prebuilt bundle at build time |
| `src/types/pagedjs.d.ts` | narrow type declaration |
| `.github/workflows/ci.yml` | new `handbook` job — fails if the .md is stale |

Nav and footer both link to `/handbook`.

### What the book contains

- Title page, colophon, contents, **4 parts, 36 chapters**, appendix listing all
  50 tools plus the 3 platforms.
- **106 typeset pages**, 41 contents entries.
- Chapters exist only for the 36 tools that ship a `userGuide.ts`. Their **full
  guide text is copied into the chapter** — not referenced, not summarised.

### Where the content comes from

Three generated sources, all already the truth for something else:

- `src/data/capabilities.ts` — the facts each card shows
- `src/data/registry.json` — the three platforms
- `src/app/tools/*/userGuide.ts` — the long-form guide a tool ships in-app

### Verification done

- All 41 contents entries resolve to a real physical page, in ascending order:
  Part 1 → p5, Chapter 1 → p6, Text-to-SQL → p30, YARA → p100, Appendix → p102.
- Generated PDF: 107 pages, 889 KB.
- Print rendering confirmed by screenshot: white ground, dark text, part pages,
  chapter openings, at-a-glance tables, justified body text with hyphenation,
  folios bottom-centre.

### NOT verified

The printed folio digits were never seen directly. This machine has no way to
turn a PDF page into an image, so the check was "every contents entry maps to
the right page in the DOM", which is what `target-counter` prints — but the
final digits are unconfirmed. **Click the button once and look.**

---

## 3. Bugs already hit and fixed — do not repeat these

1. **`react-markdown` renders no tables.** Pipe tables need `remark-gfm`. Without
   it all 53 fact tables rendered as literal pipe characters. Fixed by adding
   the plugin.
2. **Paged.js's ESM build throws inside Next** — `s.call is not a function` from
   its own handler registration. Fixed by loading the prebuilt UMD bundle as a
   plain script from `/vendor/paged.min.js`, copied from `node_modules` at build
   time by `scripts/copy-pagedjs.mjs` (wired to `prebuild` and `predev`).
3. **The print rule hid the book's contents page.** `nav { display: none }` was
   meant for the site header, but the contents page is itself a `<nav>`, so two
   blank leaves printed where the contents should be. Fixed with
   `nav:not(.bk-toc)`.
4. **Site colours inherited into the typeset pages.** Paged.js clones content
   out of `.hb-body`, but `body { color: var(--text) }` still inherits, giving
   near-white text on a white page. Fixed with `body.bk-paginated` rules and
   `.pagedjs_page` rules in book.css.
5. **A guide's interpolated figure was silently deleted.** The phishing chapter
   read *"91% accuracy on a genuine -email held-out test set"* because
   `${HELD_OUT_COUNT}` resolved to an empty string. The resolver now follows
   constants into their JSON model file (91%, 2,795 emails, both traced to
   `phishingModel.json`) and **exits non-zero** rather than writing a blank.
6. **Descriptions extracted as empty for all 50 tools.** In `capabilities.ts`
   the longer values wrap onto the next line, and a pattern expecting
   `name: "` on one line silently matches nothing. Fixed with `\s*` after the
   colon. `model` worked, which is what disguised it.
7. **Guides are followed by a SUGGESTIONS export**, so an end-of-file-anchored
   regex found nothing. Guides also close two ways: `` `; `` and `` `.trim(); ``.
   Some are assembled from sibling modules by `${...}` interpolation.

---

## 4. Commands

```bash
python3 scripts/build-handbook.py        # regenerate the book; CI fails if stale
node scripts/copy-pagedjs.mjs            # runs automatically on build/dev
./scripts/check-file-length.sh           # 400-line gate
npx next build
```

---

## 5. THE NEXT JOB — deep per-tool documentation

Agreed this session, not started. The purpose is explicit: **the owner wants to
read the book and be able to explain the app in an interview.** That changes
what "documentation" means here — it has to explain the machine learning, not
just the buttons.

### Why the current book is not enough

The 36 existing guides were written to teach someone how to *use* a tool: which
button, what the output means, where it fails. They are honest and detailed
about that. They mostly do **not** explain how the model underneath works, why
that model was chosen, or what the trade-offs were — which is exactly what an
interviewer pushes on.

### Scope

**14 tools have no guide at all and need a chapter from nothing:**

`automl` · `shap` · `optuna` · `preprocessing` · `feature-engineering` ·
`feature-selection` · `ensemble` · `drift` · `pipeline-builder` ·
`pipeline-cinema` · `depth-parallax` · `face-liveness` · `pose-vj-visuals` ·
`text-to-image` · `rag-analytics`

(That list is 15 names — `rag-analytics` is the fifteenth and was missed from
the "14" count used in conversation. Check it too.)

**36 tools have a guide and need a new "how it works and why" section added.**

Either way it is 50 tools. Rough size: 40,000–60,000 words of new material.
Several sessions, not one.

### Where each tool's code lives

| Tool | Frontend lines | Backend router in ML-Unified |
|---|---|---|
| automl | 198 (+ `src/components/AutoMLSteps/`) | `automl_train_work.py` |
| shap | 651 | `shap.py` |
| optuna | 1119 (+ `src/components/OptunaSteps/`) | `automl_helpers.py` |
| preprocessing | 383 (+ `PreprocessingPanels/`, `PreprocessingModalParts/`) | `eda.py` |
| feature-engineering | 353 (+ `FEPanels/`) | `stages.py` |
| feature-selection | 377 (+ `FSPanels/`) | `stages.py` |
| ensemble | 609 | `shap.py` |
| drift | 1953 | `inference.py` |
| pipeline-builder | 405 (+ `src/components/pipeline/`) | `__init__.py` |
| pipeline-cinema | 604 (+ `src/components/pipeline-cinema/`) | none — client only |
| depth-parallax | 1371 | none — client only |
| face-liveness | 376 | `mm_liveness.py` |
| pose-vj-visuals | 440 | none — client only |
| text-to-image | 1374 | `_image_gen_budget.py` |
| rag-analytics | 363 | none |

Also relevant: `src/lib/` holds the real algorithm implementations for several
of these — `feAlgorithms.ts`, `feLDA.ts`, `feTransforms.ts`, `fsAlgorithms.ts`,
`fsCore.ts`, `fsEmbedded.ts`, `fsFA.ts`, `fsFilters.ts`, `fsLDA.ts`, `fsMain.ts`,
`fsReduction.ts`, `preprocessing.ts`, `preprocessingAlgorithms.ts`,
`hardwareEstimator.ts`, `automlUtils.ts`. Read these, not just the UI.

### The chapter template agreed

1. **What problem it solves** — plain terms
2. **How it works, step by step** — what happens between input and answer
3. **The model or algorithm** — what it is and how it actually computes its
   result. For SHAP that means explaining Shapley values properly; for AutoML,
   what 5-fold cross-validation does and how the winner is chosen.
4. **Why these choices** — why four models not one, why CatBoost is in the list,
   what the trade-off was
5. **How to read the output** — what the numbers mean, what good and bad look
   like
6. **Limits** — where it breaks, what it cannot tell you
7. **Likely interview questions** — what someone would push on, with answers

Point 7 is the one that serves the stated purpose.

### Decisions already taken

- **The deep text goes in the book only.** The in-app help panels stay short and
  task-focused. Confirmed by the owner this session.
- Therefore the new material must **not** be written into `userGuide.ts`. It
  needs its own home — suggested `docs/chapters/<tool-id>.md` in ml-portfolio,
  picked up by `build-handbook.py` and placed after the tool's existing guide.
- **Batch of five first:** `automl`, `shap`, `optuna`, `preprocessing`,
  `feature-engineering` — the ones an interviewer digs into. Owner reads those
  five, corrects the format once, then the remaining 45 follow in batches.

### Two warnings that were stated and accepted

1. **Only what the code shows can be written.** Where the code makes a choice
   but does not say why, describe what the choice does and what it costs, and
   **mark it as a reading rather than as the author's intent.** The owner
   correcting those marks is the most valuable review pass available.
2. **Hand-written chapters cannot be auto-checked.** The book today cannot drift
   from the app because it is generated from it. Written explanation can drift —
   swap a model next year and the chapter will not know. Keep the generated
   facts separate from the written explanation so the facts stay guarded by the
   CI job.

---

## 6. Standing constraints (carry forward)

- **Ask before every `git commit`** in both repos. No auto-commit, even for
  CLAUDE.md's "mandatory" backend deploys.
- **Never spawn a subagent without asking.** Memory file
  `feedback_use_subagents.md` was corrected this session; it previously said the
  opposite.
- **Only delete files created in the current session, named explicitly.** Never
  a wildcard `rm`.
- **No file over 400 lines**, every extension. The CI gate enforces it for
  `*.py *.ts *.tsx *.js *.jsx *.mjs *.css *.html`; `.md` is not gated.
- HF Space upload is mandatory after any commit touching `services/ml-api/**`.
  No commit this session touched it.
- **Use simple words.** Corrected twice this session — "rotate the key" and
  "rasterise" were both jargon. Say what to do, not what it is called.
- Pexels API key was pasted in chat. It is used only via `PEXELS_API_KEY` from
  the environment or `.env.local`, never written into a committed file. The
  owner was told to replace it in their Pexels account when convenient.

---

## 7. Method notes from today

1. **This machine's browser lies.** Three separate times: it reported a 780px
   window for a 390px viewport, it stopped recomputing styles when a theme class
   changed (an injected `!important` rule could not move a colour), and an
   element screenshot silently wrote no file. Verify on production with the
   site's own controls — clicking the real theme toggle worked where the class
   change did not.
2. **Measure the thing the user sees, composited.** Border contrast was reported
   at 5–10:1 when it was really 1.3–3:1, because the colour carried 46% alpha
   and the measurement painted it on a blank canvas instead of over the page.
3. **Calibrate a threshold against known-good examples.** A quality bar of 25
   rejected all 50 photographs; the images already approved measured 7.6–22.2.
   The bar was borrowed from a byte-plot, an extreme noise texture.
4. **Share the class, do not copy the declarations.** Four sections each
   described "what a card looks like" separately and drifted; one carried a
   `backdrop-filter` the original never had, which made an identical fill render
   several shades lighter.
5. **Check whether a guard actually fires.** The handbook drift check passed on
   a deliberately broken file — because the file was untracked, so `git diff`
   had nothing to compare. It only became a real guard after the first commit.
6. **Search one source badly, and you will conclude the thing does not exist.**
   Four bad queries against Wikimedia produced "there are no suitable free
   images". Openverse and then Pexels both disproved it within minutes.
