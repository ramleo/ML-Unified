# Part 273 — Part 1 finished, and the first honest count of what is left

**Date:** 2026-09-03
**Repos touched:** `ml-portfolio` only. **No backend file changed, so no HF Space
upload applies.**
**Commits:** `712ed91`, `c73ab2f`, `2ac517b`, `815153e`, `d9c9da2`, `06d2b18` —
all pushed to `main`.
**Paid API calls spent:** **0.** Everything was local, server compute on the
Space, or the live Vercel site.

---

## 0. Where things stand in one paragraph

The three remaining Part 1 chapters were built, so **Part 1 is now 11 of 11**.
Doing so surfaced two shipped bugs and one dead-end UI state, opened a second
recording path (against live Vercel, for tools that cannot run locally),
explained a mystery carried over from Part 272, and — the most useful output of
the session — produced the **first actual count of demo coverage across all four
parts**. It is 21 of 50, and the shape of that number changes what should happen
next far more than any individual chapter did.

---

## 1. The commits

| Hash | What |
|---|---|
| `712ed91` | Pipeline Cinema demo (ch 9), three page fixes, recorder double-place |
| `c73ab2f` | SVG transport icons instead of ▶ ⏸ ⏹ glyphs; clip re-recorded |
| `2ac517b` | Dropped the unused `STORY_MAP` |
| `815153e` | Split `AnalyticsDashboard.tsx` 385 → 311; 13 anchors |
| `d9c9da2` | Real-Time Analytics demo (ch 10) |
| `06d2b18` | SHAP demo (ch 11); `cv_results` name bug |

---

## 2. The owner's requests, in order

1. "go through parts 271 and 272 and tell me where we stopped"
2. "yes, just do ch 9"
3. "1. commit and push  2. use SVG for Pause/Stop buttons  3. what are you
   suggesting about STORY_MAP?"
4. "Delete the map" → "yes" (commit)
5. "just do ch 10" → chose **record against live Vercel** → "yes" (commit)
6. "what you suggest?" → "yes" (do ch 11) → "yes" (commit)
7. "is the Pause/Stop glyph thing fixed?" → "how can I verify?"
8. "document the above conversation to Conversations/"

---

## 3. The coverage count — the session's most useful output

Nobody had ever counted. Derived by matching every `bk-toc-chapter` in
`public/handbook.md` against the `chapter` field of every file in
`src/data/demos/`:

| Part | Coverage | What is missing |
|---|---|---|
| **Part 1** | **11 / 11** | — |
| Part 2 | 2 / 4 | Contract/Invoice Reconciliation, Document Intelligence |
| Part 3 | **0 / 14** | the entire CV part |
| Part 4 | 8 / 21 | 13 security tools |
| **Total** | **21 / 50** | |

**Why this matters more than the three chapters built today.** Chapter 9 took
four recording passes; chapter 10 needed a file split and a production deploy
before a single frame could be filmed. At that cost, twenty-nine more chapters
is not a plan — it is the entire remaining usage budget spent on video.

The recommendation put to the owner, and not yet decided: **a guided demo earns
its place where the tool is hard to understand from a screenshot, or where a
visitor is likely to land first.** That is perhaps eight to ten more, not
twenty-nine. Part 3 is the clearest case for skipping most: several of those
fourteen need a webcam or a very specific upload, which a recorded clip cannot
show honestly anyway.

---

## 4. Chapter 9 — Pipeline Cinema (`712ed91`)

11 steps, 135s. The page had **zero anchors**; nine were added.

### 4.1 The script takes the path the chapter says people miss

Pipeline Cinema plays without a file as a scripted cartoon. With a file it
"stops being a cartoon and becomes a narrated run of your own data" — four real
calls to the Pipeline Builder's endpoints, narration generated from the
responses. The clip uploads `automl-churn.csv` and takes the second path.

Everything on screen came back from the Space: preprocessing reported
`240 rows × 10 columns`, and AutoML finished LightGBM 0.821 / RandomForest 0.821
/ CatBoost 0.816 / XGBoost 0.816. **CatBoost being present is `00c25de` from
Part 272 working in production.**

### 4.2 Mid-run narration is deliberately stage-agnostic

The run takes ~45 seconds, and the demo player has no way to sync a step
boundary to a scene boundary. Three steps narrate *over* the run, and every
claim in them is true at any moment of it — the two-clocks construction, pause
and stop, degrading rather than breaking.

**The first take proved why.** A step describing the between-stage column lists
played over the AutoML leaderboard. Replaced with a claim about the Pipeline
Builder endpoints, which is true whenever it lands.

### 4.3 Three page fixes, all found by building the demo

- **The run had no ending.** When the last scene finished, the story panel
  dropped straight back to its empty state, reading as though the run had been
  thrown away. It had not — every stage is still behind its pill. Added a
  completion line (inline SVG, no emoji) that says so, and anchored `cin-done`
  on it so the demo can wait for the run to finish.
- **Stale copy.** The empty state and the narrator both said *"Run Animation"*.
  The button says *"Run Cinema"*.
- **No bottom padding on `main`.** The control row sat hard against the page
  edge, so nothing could scroll it clear of anything overlaying there — the
  caption covered Pause and Stop in the exact step that describes them.

The completion banner was first placed *below* the controls, where the caption
covered it too. Moved above them, where `scrollIntoView({block:"center"})` can
actually centre it.

---

## 5. THE MISTAKE WORTH KEEPING — a defect that was a sampling artifact,
## and then turned out to be real anyway

This is the most instructive sequence of the session.

**Round 1.** The step-6 frame showed the spotlight sitting ~90px below the Run
button, ringing empty space. Diagnosed as: `place()` runs the instant `page.click`
returns, before React has re-rendered. Added a second `place()` 700ms later.

**Round 2.** Re-recorded. Still wrong. Scanned the ring position across the whole
step instead of one frame:

```
f=0.30  ring y157-879 x194-1405   <- still the previous step's ring
f=0.50  ring y568-888 x613-1216   <- mid-transition
f=0.70  ring y812-868 x907-1069   <- what I had been reading
f=0.90  ring y756-812 x813-960    <- correct
```

The spotlight has `transition: all .35s`, and the step's first `place()` does not
fire at t=0. **A frame at 70% of a short step can still show the ring in
flight.** So I concluded the defect was my sampling, reverted the recorder
change, and re-recorded.

**Round 3.** With the change reverted, the ring at **88%** was still wrong.

**Round 4.** Instrumented `place()` to print the ring and anchor rects during a
real recording rather than reasoning about it:

```
DBG a  ring 846,916  anchor 762,819   <- what one post-action place leaves
DBG b  ring 756,813  anchor 762,819   <- after +700ms and a second place
```

The fix was right, my reason for reverting it was wrong, and only direct
instrumentation separated the two. Restored, with the evidence in the comment.

**Two lessons:**

- **Sample step frames at ~88%, not 70%.** The first ~1.5s of a step can still
  be showing the previous step's spotlight mid-transition.
- **"I was wrong about the defect" does not imply "the fix was wrong."** I
  reverted a correct change because the evidence that motivated it was bad. The
  cost was two extra recordings; the thing that ended it was instrumenting the
  real run instead of arguing from a screenshot.

---

## 6. The two follow-ups (`c73ab2f`, `2ac517b`)

### 6.1 SVG transport icons

Flagged at the end of chapter 9 as pre-existing and deliberately untouched; the
owner asked for it directly. Pause, Resume and Stop carried `▶ ⏸ ⏹`. Those
render as full-colour emoji on some platforms and bare typographic marks on
others, and **neither takes the button's own colour** — the Stop mark stayed
dark on a red button.

Replaced with three inline SVG paths on `fill="currentColor"`. The chapter 9
clip was re-recorded, because step 8 spotlights those exact buttons and would
otherwise show a UI that no longer ships.

### 6.2 `STORY_MAP`

A stage-to-component lookup in `StageStory.tsx` that nothing read. It could
never have been used: the four stories take different props — `PreprocessStory`
wants the CSV preview, `FSStory` the kept/dropped column lists, `AutoMLStory`
the results — so one `<Component {...props} />` could not serve all four. The
if-chain twenty lines below is the honest shape. Deleted.

---

## 7. Chapter 10 — Real-Time Analytics (`815153e`, `d9c9da2`)

### 7.1 The blocker: it cannot run locally at all

`NEXT_PUBLIC_SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY` are present but
**empty** in `.env.local` (and in `.env.local.bak`). A local build renders only
*"Dashboard not configured"*.

**This also closes a Part 272 open item.** The "two unexplained 400 Bad Request
errors on the pipeline-builder page at load" are `/api/track` returning
`{"error":"Bad request"}` for the same missing credentials. Every page in the
app does it locally; production does not. Not a bug.

### 7.2 A second recording path: live Vercel

Put to the owner as a choice; they chose to record against
`https://ml-portfolio-rho.vercel.app`. That required pushing the anchors first
and waiting for the deploy — a longer loop than any previous chapter, but the
only way to film this tool, and it turned out to be the *better* way.

```
DEMO_BASE_URL=https://ml-portfolio-rho.vercel.app node scripts/record-demo.mjs realtime-analytics
```

**Cost, disclosed before doing it:** each take writes one `export` row plus a few
`page_view` / `tool_open` rows into the production analytics table — exactly what
a real visitor clicking Export produces. One take was needed.

### 7.3 The split, first

`AnalyticsDashboard.tsx` was 385 lines, past the 350 at which this project splits
before adding. Two extractions, no behaviour change:

- `analyticsTypes.ts` (49) — `Range`, `RANGE_LABELS`, and the wide `Stats` shape
  every panel reads a slice of.
- `AnalyticsToolbar.tsx` (77) — range presets, calendar, guide, export link.

385 → 311.

### 7.4 The clip demonstrates the architecture, it does not just describe it

The chapter's thesis is *"the number changed because something happened, not
because a clock ticked."* The clip proves it:

**Exporting is itself a tracked action.** Clicking Export CSV posts a row into
the very table the live feed subscribes to. Seventeen seconds later the frame
shows the `export` row at the top of the feed aged **0s**, the **CSV EXPORTS card
reading 1**, and the Events-by-Type donut carrying **`export — 4%`** — the
optimistic client-side stat update, visible. No refresh, no polling.

To make that provable rather than asserted, the **newest** feed row now carries
`data-wt={\`ra-newest-${ev.type}\`}`, so the demo waits for *this* export rather
than any earlier one. A plain `expect: "export"` would have been satisfied by the
"Export CSV" button — the exact trap from Part 272 §9.

Other real numbers in the clip: the 7-day funnel at page_view 247 → tool_open 105
(43%) → query_run 1 (1%).

---

## 8. Chapter 11 — SHAP Explainability (`06d2b18`)

11 steps, 150s. Every file already under 350, so no split needed.

### 8.1 The script refuses to blur the chapter's own distinction

The chapter opens by arguing that **global feature importance cannot answer "why
this row"**. But this page's Try-It panel produces exactly that — global
importance from a trained model. The page is honest about it ("SHAP-style
Importance"), and the clip has to be too.

So step 1 names both halves, and step 11 says outright what the panel does *not*
do: *"It tells you support tickets matter across two hundred and forty customers.
It cannot tell you that this one customer was pushed over the line by their
ticket count while their long tenure was pulling the other way."*

Narrating "see why the model made this prediction" over a global bar chart would
have been precisely the defect Parts 271 and 272 kept finding.

### 8.2 The assertion earned its keep, loudly

Ground truth was probed with curl **before** writing narration — the discipline
from Part 272. But the probe used **Random Forest**, while the panel defaults to
`MODELS[1]`, **XGBoost**. The first recording aborted:

```
Error: step 10 expected "0.8456" on screen and it is not there
       — the recording would narrate something that did not happen
```

Four numbers across steps 5, 7, 8 and 10 were wrong and the guard stopped all of
them. Corrected to the real run: **XGBoost, CV 0.8456**, `support_tickets` 27.0%,
`contract_type` 16.3%, `tenure_months` 16.2%, `has_fiber` 11.2%.

**A false alarm inside the fix:** I briefly believed the Model dropdown was
showing "Random Forest" while sending something else — a silent-selection bug.
Reading `useShapRunner.ts` showed `useState(MODELS[1])`. Deliberate. No bug.
Checked before reporting.

The result is also a good story: support tickets beats contract type, tenure and
price as the churn driver in that dataset. Not price — how often they had to ask
for help.

### 8.3 One shipped bug fixed

`/train` returns each CV entry as `{algorithm, score, fold_scores}`. The SHAP page
reads `c.name`. So the AI assistant on that page was handed:

```
All model CV scores: undefined=0.8456
```

Invisible in the UI — only in what the assistant is told. `EnsembleRunner`
already normalises the same field the same way; applied that pattern.

**`optuna/page.tsx:118` has the identical bug and was deliberately left alone**
as out of scope. One line, same shape.

### 8.4 Anchor the block, not the region

Step 10's first pass ringed the entire results panel while narrating about one
badge. Added `data-wt="shap-cv"` to the CV Score badge and re-pointed the step —
Part 272 §9's second rule.

---

## 9. How the SVG fix was verified when asked

The owner asked "how can I verify?" — worth recording the answer as a pattern.

Rather than describing the fix, the deployed page was driven directly: load
production, click Run, read the buttons' DOM.

```
Pause  ->  SVG path: M7 4h4v16H7zM13 4h4v16h-4z
Stop   ->  SVG path: M5 5h14v14H5z
```

Plus a screenshot of the live control row. **The visual tell given to the owner
was the useful part:** the Stop square is *red*, matching its label. An emoji
glyph renders in its own fixed colour and cannot inherit — so colour is the
proof, not shape.

---

## 10. Verification method, consolidated

| claim | evidence |
|---|---|
| every clip's steps are correct | one frame per step at **88%**, read against that step's `say` |
| spotlights land on their anchor | ring bbox measured in pixels by colour-matching `#7da5ff`, not eyeballed |
| the recorder fix was needed | `place()` instrumented during a real recording; before/after rects printed |
| the live event really arrives | `waitFor` on an anchor that exists only when the newest row is an export |
| SHAP's numbers are right | `/train` probed with curl first; `expect` aborted the take when they were not |
| the SVG fix is live | production DOM queried for `<path d=…>`, plus a screenshot |
| coverage is 21/50 | handbook TOC parsed and matched against `src/data/demos/*.json` |

---

## 11. Lessons

**Count before committing to a plan.** Three chapters were built one at a time
on the assumption that "finish the handbook" was the goal. The count that should
have come first says 29 remain — which makes "which chapter next" the wrong
question entirely.

**Sample step frames at 88%.** A 70% frame can still show the previous step's
spotlight mid-transition. This produced a phantom defect, a wasted revert, and
two extra recordings.

**Being wrong about a defect does not make the fix wrong.** The recorder's
double-place was correct; my evidence for it was not. Reverting on the strength
of a bad reason cost more than the original mistake.

**Instrument the real run.** Two rounds of screenshot-reading argued in circles.
One round of printing the actual rects settled it in a single recording.

**Probe the same configuration the tool will actually use.** The SHAP ground
truth was measured properly and still wrong, because the probe used a different
model than the page's default. `expect` caught what the probe missed.

**A missing credential can look like an application bug for a long time.** The
Part 272 400s sat unexplained for a session because nobody asked what `/api/track`
needed. They were never a bug.

---

## 12. Still open

- ~~**`optuna/page.tsx:118`** — the same `c.name` → `undefined` bug fixed in SHAP.~~
  **DONE 2026-09-04, `a3a8b8e`.** Took two lines, not one — the inline state type
  declared `name: string`, so the fallback would not compile until it was widened.
- ~~**Nothing from Parts 269–272 verified on live Vercel.**~~ **WITHDRAWN
  2026-09-04, Part 274 §3.** Never an owner request — mine, carried four
  sessions without evidence anything was broken. The owner uses the site daily.
  The one item in that area with real evidence, the empty local Supabase keys,
  was already diagnosed in §7.1.
- **The demo target is still undecided** — but three more were built
  2026-09-04 (ch 12, 13, 41), taking coverage to **24 of 50** with Parts 1 and 2
  both complete. See Part 274 §8 and §12 for the remaining shortlist.
- **`pipeline-cinema/page.tsx` is 371 lines.** It was 348 when touched, so it was
  legitimately under the threshold — but the next feature there needs a split
  first. Clean cut: the transport control row plus the three icon components
  into `PipelineCinemaControls.tsx`, taking the page back to ~260.
  *(Two comparable splits were done this way on 2026-09-04 — Part 274 §6.1.)*
- **`QueryResultPanel.tsx` (403) and `UserGuideModal.tsx` (403)** — still over
  the 400-line limit. Pre-existing.
- **The hosted TTS path** has still never run against a live paid vendor.
- **No site-wide emoji-as-icon audit.** Only the three Pipeline Cinema transport
  buttons were fixed. A grep would show what else is out there; not run.
- Three untracked `test_*` files in the ML-Unified root — still the owner's call.

---

## 13. Recording recipes

**Local (default) — for anything that runs against the ML-Unified Space:**

```
NEXT_PUBLIC_ML_UNIFIED_URL=https://wram1708-ml-unified.hf.space \
NEXT_PUBLIC_ML_SQL_URL=https://wram1708-ml-sql.hf.space \
  npx next build && npx next start -p 3300
DEMO_BASE_URL=http://localhost:3300 node scripts/record-demo.mjs <demo>
```

Port **3300** is required — `security/origin_policy.py` rejects any other Origin.

**Live Vercel — for anything needing production credentials or production data:**

```
DEMO_BASE_URL=https://ml-portfolio-rho.vercel.app node scripts/record-demo.mjs <demo>
```

Anchors must be **deployed first**. Takes write real rows to real tables; say so
before running it.

**Frame review:** one frame per step at **88%** (not 70% — §5), read against that
step's `say`.

```
ffmpeg -ss <t> -i clip.webm -frames:v 1 out.png
```

Ring geometry can be measured rather than eyeballed by colour-matching the
spotlight border `#7da5ff` in the frame.
