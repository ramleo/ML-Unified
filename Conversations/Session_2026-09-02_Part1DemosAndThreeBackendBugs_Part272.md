# Part 272 — Part 1 guided demos, and the three shipped backend bugs they uncovered

**Date:** 2026-09-02
**Repos touched:** `ml-portfolio` (8 commits) and `ML-Unified` (3 commits).
**Backend changed, so HF Space uploads applied** — three deploys, each verified live.
**Commits:**
`ml-portfolio` — `3132301`, `bd3e744`, `d383286`, `10fbf15`, `7319a73`, `06d4094`, `1341b89`, `f4e1137`
`ML-Unified` — `8899f58`, `8ec64dc`, `00c25de`
All pushed to `main`.
**Paid API calls spent:** **1** (one text-to-SQL recording). Everything else was
local, client-side, live DNS, or server compute with no LLM.

---

## 0. Where things stand in one paragraph

The session began by closing out the three diagnosed-but-unfixed `text-to-sql`
items from Part 271, then audited the eight demo clips nobody had ever watched
(five of eight were wrong). Three real bugs the user found by *using* the
handbook were fixed. Then Part 1 of the handbook went from 1 of 11 chapters with
a guided demo to **8 of 11**. The expensive and unplanned part: building those
demos uncovered **three bugs shipped in production**, none of which threw an
error a user would see — `/models` returning 500 for every visitor, the drift
detector measuring every built-in model against an invented baseline, and
CatBoost never once having completed a fit on the deployed Space.

---

## 1. The user's requests, in order

1. "what we need to do next?" / "navigate there"
2. "the three things that are open related to text to sql, can they be fixed?" → "proceed"
3. "which should we do 'The eight unwatched clips'?" → "yes"
4. (screenshot) "i dont see return pill bottom left"
5. (two screenshots) three handbook bugs reported from real use
6. `"The Top button" should be there irrespective of whether there is return pill or not`
7. "what is pending in handbook backlog?" → "proceed"
8. "Part 1 has 7 more chapters without a demo" → **"proceed but one at a time"**
9. Three separate "fix it" / "yes" approvals for backend bugs found mid-build
10. "stop after committing, you are using up lot of usage"

---

## 2. text-to-sql — the three open items, closed (`3132301`)

Carried from Part 271 §8. All three fixed, one paid call.

### 2.1 The chart chooser was building a grid out of two keys

The real bug, and not a demo bug. `detectViz` in `SqlChart.tsx` took "two
categorical columns plus one numeric" as a heatmap without checking whether
those categoricals *repeat*:

```ts
if (ci.length>=2 && ni.length===1) return { type:"heatmap", ... };
```

For `FirstName | LastName | Total Spending` they never repeat — they are one
person cut in half — so the top-ten-customers query rendered a 10×10 grid with
ten filled cells and ninety zeros, under narration promising a chart "picked to
suit the shape of the data".

**The tool already knew.** Its own auto-insights panel, three inches above the
chart, prints "FirstName — 100% distinct — likely a key" for both columns. The
chooser simply never consulted it.

Fixed with a cardinality guard: a heatmap now requires both categorical axes to
have a distinctness ratio ≤ 0.7. **0.7 because a genuine full grid tops out at
0.5** (two values on one axis crossed with the other).

Verified with six synthetic cases against the real exported function — zero API
calls, because `detectViz` is pure. Two of the six failed on the first run and
**both were my test cases being wrong**, not the guard: `Quarter` trips the
date-name regex and never reaches the heatmap branch, and `"1".."8"` ids read as
numeric. Corrected and re-run.

### 2.2 An assertion that matched the wrong element

`expect: "Album"` was being satisfied by a *sample question in the sidebar*
("top 5 artists by total album count"), not by the schema panel. That is exactly
how an earlier broken run with no schema loaded at all sailed through the guard
built to catch it. Now `PlaylistTrack`. Step 8's `"select"` could be met by the
SQL box alone, so it is now `"10 rows"`, which only the results header prints.

### 2.3 Narration overstating a click

Step 2 said "I will pull its schema in now" over a click that re-loads a schema
already auto-loaded on mount (`TextToSqlRunner.tsx:67`). Rewritten to say so.

---

## 3. The eight unwatched clips — five were wrong (`bd3e744`)

Reviewed frame by frame via `ffmpeg` extraction, one frame per step at 65%
through the step, read against that step's `say` text.

| Clip | Verdict |
|---|---|
| `tls-security-headers-scanner` | clean |
| `extension-permission-analyzer` | clean |
| `dns-tunneling-detector` | clip clean — **but the tool's own copy was wrong** |
| `email-auth-checker` | claimed a DMARC subdomain policy that was nowhere on screen |
| `phishing-email-classifier` | promised quoted flags; none matched, and the "contrast" was vacuous |
| `malicious-package-scanner` | "one character away" vs the screen's "edit distance 2" |
| `password-audit` | "four words… no symbol" over `velvet-otter-parade-97` |
| `yara-file-scanner` | asserted a built-in scan that never ran |

**Across all eleven clips, seven were wrong.**

### 3.1 The two failure kinds — and why one is invisible to tooling

1. **Contradicting a visible value.** The edit distance, the word count, the
   missing symbol. Caught by reading the frame.
2. **Asserting something never shown.** The subdomain policy, the quoted flags,
   the scan that never ran. **This kind cannot be caught by the recorder at
   all** — an `expect` proves something *is* on screen and can never catch a
   claim that is merely unsupported. The only defence is watching the clip.

### 3.2 Three of the fixes were code, not copy

- **`email-auth-checker`** never rendered the `subdomain_policy` the API had
  always returned (`email_auth_check.py:167` returns it; the type declared it;
  no component displayed it). The row now renders, GitHub really does publish
  `sp=reject` (confirmed with `dig`), and the step asserts on it.
- **`dns-tunneling-detector`'s clip was correct and the *tool* was wrong.** Its
  intro paragraph and a code comment both claimed length, entropy AND volume
  must all agree, while the code needs two of three with entropy mandatory —
  and the screen showed a domain flagged on exactly two. A careful viewer
  reading the tool's own description would have concluded the flag was a bug.

### 3.3 A sample deliberately NOT changed

`phishing-email-classifier`'s rule list matches nothing on either sample, and
`sampleEmails.ts` records that both are **real held-out corpus emails, not
fabricated text**. Writing an email containing `"urgent action required"` would
have made the rules fire *by staging the evidence*. The narration was fixed
instead, and now makes the near-miss the lesson: the email says *Hello* and
*Urgent* and *my dear*, the list holds exact phrases, so it stays silent — and
that narrowness is why the list sits beside the model rather than inside its
score.

---

## 4. Three handbook bugs, all found by the user using it (`d383286`)

Reported with screenshots. All three were real; two shared one cause.

**The return pill named the wrong chapter.** The label was read from the *top
edge of the window*. A chapter heading a third of the way down the screen means
that edge is still inside the previous chapter, so reading chapter 30 marked it
"Chapter 29". The probe now sits at 38% down (`READING_LINE`), where the eye is.
The mark still stores the true scroll position; only the label moved.

**The mark then never updated.** "Do not overwrite until the reader scrolls by
hand" was written for one case — Enter through eight search hits is one
navigation — but it froze the mark across entirely separate jumps too, so the
first mark of a session outlived every jump after it. That is both remaining
symptoms: 48→43 still offered chapter 29, and 43→30 hid the button entirely,
because 30 sits within a page and a half of that stale mark and the offer is
distance-gated. A jump now carries a **group**: the find bar passes
`find:<query>`, so one query's hits stay a single trip while a different search
is a new one; the rail and contents links pass nothing and always re-mark.

**A "Top" button was missing**, added above the return offer in one cluster,
shown anywhere past the first screen, and it marks a jump like anything else so
bailing out to the contents can be undone.

**Also found while testing:** Part ticks on the rail could not be clicked at
all. A Part heading and its first chapter land within a pixel or two of each
other, and the chapter tick — drawn later — swallowed every click aimed at the
Part.

> **This is the most important entry in this log.** None of these would have
> been found by more of the testing I was doing. My localhost tests jumped from
> the *top* of the book, where the reading-line offset makes no difference and
> there is no earlier mark to go stale. It took a real reading position,
> mid-book, and a second and third jump.

Verified against the reported sequences on a real build: 30→43, 43→30, 30→48,
48→43, Top from 323,891px, and a plain click on Part 4. User confirmed live.

---

## 5. Part 1 demos — the length-limit blocker, cleared

The backlog said two files needed splitting. It was three, and more emerged.

| Page | Before | After | Extracted |
|---|---|---|---|
| `preprocessing/page.tsx` | 367 | 334 | `preprocessingContext.ts` |
| `feature-selection/page.tsx` | 369 | 350 | `defaultOpts.ts` |
| `pipeline-builder/page.tsx` | 397 | 336 | `stages.tsx`, `runExpressPipeline.ts` |
| `EnsembleRunner.tsx` | 357 | 327 | `ensembleTypes.ts` |
| `feature-engineering/page.tsx` | 345 | 336 | `ActionBtn.tsx` |
| `OptunaRunner.tsx` | 350 → 351 | 320 | `optunaTypes.ts` |
| `automl_stage.py` (backend) | 410 | 336 | `_estimators.py` |

`OptunaRunner` is worth noting: it sat at **exactly 350** once anchors went in —
one edit from breaching — so it got headroom rather than being shaved back to
the line.

---

## 6. Two recorder capabilities that did not exist

Both found by watching frames, both fixed in **both players** (`record-demo.mjs`
*and* `HandbookDemo.tsx`) so the clip and the live walkthrough cannot diverge.

### 6.1 There was no `select` action

A dropdown cannot be driven by clicking it — a click opens the native menu and
picks nothing. The first feature-selection take narrated "I am predicting vo2
max" over a target reading **"(none — rank by variance)"**.

### 6.2 `waitFor` wants the anchor *visible*, not merely present

`ExpressRunner` unmounts the moment a run finishes, so a `pb-done` anchor on its
wrapper was an empty zero-size div: attached, but never visible. `waitForSelector`
defaults to visible, so it waited the full 180 s and the next step narrated "four
stages done" regardless.

The recorder's failure log now distinguishes **"never appeared"** from **"in the
DOM but never visible — the anchor is probably an empty wrapper"**. That
ambiguity cost a full record-and-review cycle.

### 6.3 Components that swallow `data-wt` silently

Four found. A component with no rest-prop spread drops an inline `data-wt` with
no error, and the spotlight then has nothing to find. Each now declares it
explicitly: **`RepulsionCard`**, **`NumericTransformsPanel`**, **`ActionBtn`**,
and `MetricCell`-adjacent panels via wrappers.

**Check any custom component before anchoring it.**

### 6.4 `display: contents` is not an anchor

Nearly shipped one on the feature-engineering transforms panel. This project
already learned it: a box-less element measures as zero, so spotlights and
Playwright clicks fail on it. Caught before building.

---

## 7. THREE SHIPPED BACKEND BUGS

None of these threw an error a user would see. Two produced confident wrong
output; one silently returned less than was asked for.

### 7.1 `/models` returned 500 for every visitor (`8899f58`)

`list_models` indexed `m["schema"]["title"]` and friends directly across every
entry in `MODELS`, and the Pipeline Builder's AutoML stage registered its trained
models as a bare pipeline — **no `"schema"`, no `"classes"`**. One such entry
raised `KeyError` and the endpoint 500ed *entirely*, which took the Data Drift
tool down with it, since that tool lists models to choose what to compare against.

Latent, not new: any visitor pressing Auto-Run in Express mode created one. Found
after five recording runs left five in the registry. It self-heals on a Space
restart (`MODELS` is in-memory) and comes straight back.

Fixed at both ends: registration goes through a new `_registry.py` producing the
same shape the AutoML trainer does, **and** `list_models` reads defensively so a
malformed entry costs that entry's title, not the endpoint.

The rename is the part that does more than stop a crash: drift's baseline
extractor looks for a step called `"prep"` with a `"num"` transformer whose
scaler is `"scaler"`; these pipelines named them `"pre"` and `"scl"`. Even with
the 500 fixed, a Pipeline Builder model would have yielded an **empty baseline**
and silently compared against nothing.

### 7.2 Drift measured every built-in model against an invented baseline (`8ec64dc`)

**The most serious of the three.** `_baseline.py` looked up its preprocessor as
`named_steps.get("prep")` — and **no model in the project calls it that.** The
built-ins name it `"preprocessor"`. So the lookup returned `None`, the baseline
came back empty, and `_compute.py:68` silently substituted the midpoint of each
column's declared range for the training mean:

```python
ref_mean = (fmin + fmax) / 2
ref_std  = max((fmax - fmin) / 6, 1e-9)
```

That guess was reported as `ref_mean`, and the z-score, PSI, KS test and
histogram were all derived from it. **Nothing in the response said any of it was
made up.**

Scale of the error on the diabetes model:

| field | real `scaler.mean_` | what drift used |
|---|---|---|
| Pregnancies | 3.82 | 8.5 |
| Insulin | 78.67 | **423** |
| Age | 33.37 | 51 |

The real numbers were in the fitted `StandardScaler` the whole time, one lookup
away.

**How it was found, and this is the method worth keeping:** I built a batch where
I knew the right answer in advance — six columns drawn from the model's real
training distribution, two (Glucose, BMI) deliberately shifted — and the tool
disagreed with me. **My first instinct was that my own Pima means must be
wrong.** That is the comfortable assumption, and it would have led to quietly
tuning the sample until the demo looked convincing. Checking instead took one
command: load the pickle, read `scaler.mean_`.

Before/after on the same batch:

```
BEFORE  Insulin high, DiabetesPedigreeFunction high   (neither had moved)
        BMI low                                        (shifted a full sigma)
AFTER   only Glucose and BMI above "low"               (exactly the two shifted)
```

Two changes: the preprocessor is found **by type** rather than by a name nobody
agreed on, and every feature now carries `ref_source` — `"training"` or
`"schema_range"` — so a guessed baseline is visible instead of passing as a
measurement. **The second half matters as much as the first**: without it the
next naming mismatch fails exactly this quietly.

### 7.3 CatBoost had never once run on the deployed Space (`00c25de`)

```
_catboost.CatBoostError: dir_helper.cpp:20: Can't create train working dir: catboost_info
```

CatBoost writes a `catboost_info` directory into the working directory when it
fits, and the Space's app filesystem is read-only. **It works locally, which is
why this survived: the failure only exists in production.**

| Tool | What the user saw |
|---|---|
| AutoML (ch. 1) | CatBoost advertised as one of four competing algorithms; failed every run |
| Ensemble (ch. 4) | Requests 5 models, gets 4 back — **silently** |
| Pipeline Builder | `CatBoost -999.0` in the leaderboard |
| Optuna | Same path via `automl_helpers` |

`allow_writing_files=False` at **eight** construction sites (one was missed by
the first grep and caught by a second sweep). Verified by fitting from a
`chmod 555` directory, which reproduces the Space's condition.

**The second half again matters more:** a model failing CV was logged with
`print()` and dropped on the floor, so the response looked like the caller had
asked for four rather than five. `cv_results` now travels with `failed_models`
— algorithm and reason — and the Ensemble UI has a panel that names them.

Live after deploy: **5 models scored, CatBoost 0.8288, `failed_models: []`.**

---

## 8. The eight Part 1 demos built (1 of 11 → 8 of 11)

Every step of every clip was frame-checked against its narration before shipping.

| Ch | Tool | Cost | The claim it can fail on |
|---|---|---|---|
| 2 | `drift` | 0 | Two columns shifted; detector ranks those two at 51%/36% and the other six at ≤9% |
| 3 | `preprocessing` | 0 | 186 rows / 8 cols / 29 missing → 180 rows, 0 missing |
| 4 | `ensemble` | 0 | Five algorithms within 3.4%, all "Variable" |
| 5 | `feature-engineering` | 0 | 10 columns → 30; two transforms × ten numeric = 20 new |
| 6 | `feature-selection` | 0 | 7 in, 5 kept, 2 dropped, 29% |
| 7 | `optuna` | 0 | 30 trials, best at 13, +4.6%, gamma 60.6% of importance |
| 8 | `pipeline-builder` | 0 | 4 stages done, 3 ready, AutoML +83.7 F1 |
| (1) | `automl` | 0 | pre-existing, unchanged |

### 8.1 The samples are built so the tool can be wrong

- `preprocessing-messy.csv` is messy in exactly the ways its chapter describes —
  blank cells, six duplicate rows, an income reading 40,000,000.
- `feature-selection-fitness.csv` plants a constant column and a unit-converted
  duplicate at r = 1.00.
- `drift-glucose-batch.csv` shifts two of eight columns and leaves six at the
  model's real training distribution.

### 8.2 Honest points the demos now make

Several of the best moments were unplanned and are *limitations*:

- **preprocessing** — `"unknown"` is **not** in the missing-value list
  (`isMissing` recognises `""`, `nan`, `null`, `na`, `n/a`, `none`), so region
  shows five unique values, not four. The clip says so.
- **feature-selection** — pure noise **survives** both default filters with a
  mutual-information score of 0.00, because they are structural filters, not
  predictive ones.
- **feature-engineering** — the tool transformed `churned`, the label, because
  it has no notion of a target. The clip tells you to drop your label before
  training. `expect: "churned_log1p"` proves it rather than trusting arithmetic.
- **ensemble** — the five scores span 3.4% and every model reads "Variable";
  the narration says outright they perform about the same and you should choose
  on training time instead.
- **optuna** — the CV score is what the search optimised, so it is optimistic by
  construction; the held-out 0.8125 is the number to quote.

---

## 9. THE RECURRING LESSON — an assertion satisfied by the wrong element

**This happened four separate times today**, and it is the single most important
operational finding of the session.

`expect` matches the **whole page's text**, minus the caption overlay. So:

| Clip | The guard | What actually satisfied it |
|---|---|---|
| `text-to-sql` | `"Album"` | a sample question in the sidebar |
| `text-to-sql` | `"select"` | the SQL box, with results still empty |
| `drift` | `"PSI"` | the rankings chart, while the feature card was collapsed |
| `optuna` | `"gamma"` | the Best Tuned Parameters table, not the importance chart |

**Rule: anchor every `expect` on a string only the asserted panel can produce.**
`"10 rows"`, `"KS Stat"`, `"Hyperparameter Importance"`, `"churned_log1p"`.

A related trap: **pointing at a region instead of a block.** The optuna clip
spotlighted the whole results div, so the view centred on empty space with the
narrated content scrolled off. Anchor the block you are describing.

---

## 10. Recording recipe (unchanged, still non-optional)

```
NEXT_PUBLIC_ML_UNIFIED_URL=https://wram1708-ml-unified.hf.space \
NEXT_PUBLIC_ML_SQL_URL=https://wram1708-ml-sql.hf.space \
  npx next build && npx next start -p 3300
DEMO_BASE_URL=http://localhost:3300 node scripts/record-demo.mjs <demo>
```

Port **3300** is required — `security/origin_policy.py` hard-rejects any browser
Origin not on its allowlist. A plain `npm run build` resets the backend URLs to
`localhost:8000` and the recorder's preflight will then refuse to start.

**Frame review:** one frame per step at ~70% through the step, read against that
step's `say`. `ffmpeg -ss <t> -i clip.webm -frames:v 1 out.png`.

**Time any backend run with curl before scripting around it.** Every Part 1
backend call turned out fast (pipeline-builder Express ≈10 s total, optuna 30
trials ≈6 s, ensemble train 3.2 s), but that was checked, not assumed.

---

## 11. A monitor gate that was wrong

Waiting for a Space rebuild, I gated an `until` loop on `cv_results` appearing in
the response — which the **old** code also returns. The loop exited on the first
response and reported "still 4 models", which looked like the fix had failed.

Root-caused with evidence rather than retried: the Space API reported
`stage: RUNNING_BUILDING`. **Gate a deploy check on something only the new code
emits** (`failed_models`), or on `stage == RUNNING`.

---

## 12. Corrections to earlier claims in this session

- I said Chapter 1's AutoML clip needs re-recording because it narrates CatBoost
  competing. **It does not.** The clip stops before training, so nothing on
  screen ever contradicted it, and since `00c25de` the claim is simply true.
- I repeated the "`.next` is built against the Spaces" note three times after it
  had been asked and answered. The user called it out. It is noise once stated.

---

## 13. Still open

- **Part 1: 3 of 11 chapters left** — `pipeline-cinema` (ch 9),
  `realtime-analytics` (ch 10), `shap` (ch 11). No page among them is over the
  length limit, so nothing blocks them.
- **Parts 2, 3, 4 of the handbook** have never been surveyed for demo coverage.
- **The hosted TTS path** has still never run against a live paid vendor.
- **`QueryResultPanel.tsx` (403) and `UserGuideModal.tsx` (403)** are over the
  400-line limit. Pre-existing; worked around, not fixed.
- **Two unexplained `400 Bad Request`** console errors on the pipeline-builder
  page at load. Noticed during a probe, not chased.
- **Drift threshold judgement:** a 1.5-sigma shift grades "medium", not "high".
  Deliberately not changed — that is a product decision, not a defect.
- Three untracked `test_*` files in the ML-Unified root — still the owner's call.

---

## 14. Commit index

| Hash | Repo | What |
|---|---|---|
| `3132301` | ml-portfolio | text-to-sql: heatmap-from-two-keys bug + two weak assertions |
| `bd3e744` | ml-portfolio | six demo clips that narrated things the screen never showed |
| `d383286` | ml-portfolio | handbook return pill: wrong chapter, frozen mark, Top button, rail ticks |
| `10fbf15` | ml-portfolio | **checkpoint** — three page splits + preprocessing & feature-selection demos |
| `7319a73` | ml-portfolio | pipeline-builder demo |
| `06d4094` | ml-portfolio | data drift demo |
| `1341b89` | ml-portfolio | ensemble + feature-engineering demos, `failed_models` panel |
| `f4e1137` | ml-portfolio | optuna demo |
| `8899f58` | ML-Unified | `/models` 500 on schema-less entries — **deployed, verified live** |
| `8ec64dc` | ML-Unified | drift measured against invented baselines — **deployed, verified live** |
| `00c25de` | ML-Unified | CatBoost never ran in production — **deployed, verified live** |
