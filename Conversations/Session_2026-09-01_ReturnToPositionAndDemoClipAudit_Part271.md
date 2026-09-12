# Part 271 — Return-to-position scrolling, and an audit of the recorded demo clips

**Date:** 2026-09-01
**Repos touched:** `ml-portfolio` only. **No backend file changed, so no HF Space
upload applies.**
**Commits:** `d3217eb`, `5d3ee25`, `dd67442`, `83221be`, `b47f06a`, `a6ef651` —
all pushed to `main`.
**Paid API calls spent:** roughly 10, against an estimate of 3. Accounted for in §9.

---

## 0. Where things stand in one paragraph

One handbook backlog item closed (return-to-position scrolling). Then three of
the eleven recorded demo clips were reviewed frame by frame, which is a thing
nobody had done since they were made: two of the three were narrating claims
the screen did not support, and one of those two was hiding a recorder bug that
the previous session's spotlight fix had not covered. Both broken clips were
fixed at the script level, re-filmed, and verified frame by frame. `automl` was
reviewed and deliberately left alone. Three smaller problems in `text-to-sql`
remain open and diagnosed, one of which is a real defect in the tool rather
than the demo.

---

## 1. The commits

| Hash | What |
|---|---|
| `d3217eb` | feat: offer a way back after a jump in the handbook |
| `5d3ee25` | fix(demo): make the multimodal RAG walkthrough do what it says |
| `dd67442` | fix(recorder): hide the spotlight when its anchor unmounts |
| `83221be` | chore(demo): re-record the multimodal RAG clip |
| `b47f06a` | fix(demo): make the text-to-SQL walkthrough actually run the query |
| `a6ef651` | chore(demo): re-record the text-to-SQL clip |

CI green on `d3217eb` (all four jobs: `secret-scan`, `build`, `file-length`,
`handbook`). The later pushes were not separately polled.

---

## 2. What the owner asked for, in order

1. "proceed with backlog - return-to-position scrolling, in handbook section"
2. "yes" — commit it
3. `/compact`, then: what is "the three oldest clips re-recorded against the
   spotlight fix"? — "explain in simple words"
4. "what to do about it?"
5. (chose) fix the script first, then film all three; and check the cost before
   any live call
6. "yes" — commit the script work
7. "is multimodal-rag done or is issue still there?"
8. "proceed" — record it
9. "yes" — record again after the recorder fix
10. "what are you suggesting?"
11. "do 1. Fix text-to-sql and re-film it"
12. "is there anything pending in text-to-sql?"
13. "the three things that are open related to text to sql, can they be fixed?"
14. "document above conversations to Conversations/"

---

## 3. Return-to-position scrolling

The last unbuilt half of Part 268 §13.2. The rail, the contents and the find bar
each move the reader hundreds of thousands of pixels in one gesture, and none of
them left a way back. The rail solves getting *up* the book; it cannot know the
reader was forty pages into chapter 34 and only wanted one table in chapter 6.

New files: `src/app/handbook/handbookJump.ts` (149) and
`src/app/handbook/HandbookReturn.tsx` (73). Wired into `HandbookRail.tsx`,
`HandbookSearch.tsx` and `page.tsx`; CSS appended to `12-handbook-search.css`.

### 3.1 One slot, not a stack

A stack sounds more complete and reads worse. After six hops nobody has a model
of where "back" goes, and what a reader wants is always the last place they were
*reading*, not the last place they were *looking*.

That distinction is the whole design, and it lives in two flags:

- **`moved`** — has the reader scrolled under their own power since the mark was
  set? While false, a further jump does not overwrite the mark. Walking search
  hits with Enter is *one* navigation; without this, each Enter would repoint
  "back" at the previous hit until the original reading position was gone.
- **`landing`** — where the jump actually put them, learned from their first
  movement afterwards rather than measured at the time (a smooth scroll is still
  in flight when `markJump()` returns, so there is nothing true to record yet).
  It exists so the offer can expire: without it, "back to chapter 31" sits there
  for the rest of the session while the reader works through 6, 7 and 8.

### 3.2 Visibility is gated on distance, not on the jump

This is what keeps it quiet. A jump landing under 1.5 viewports away never shows
a button. A reader who scrolls back on their own puts it away without dismissing
anything. Four screens of hand-scrolling from the landing point retires it.

None of that needed a dismiss button, a timeout, or any state the reader has to
manage.

### 3.3 Two details worth keeping

`headingRef` is now exported from `handbookIndex.ts` so the find bar and the
return pill cannot call the same chapter two different things.

Contents rows are plain anchors rendered from the Markdown — there is no
component to hang an `onClick` on. The click is caught on the capture phase
instead, before the browser acts on the fragment. The rail and find bar call
`markJump()` directly; they are ours.

### 3.4 Verified

Headed Chrome, fresh `next dev` on :3100 — deliberately not the `next start` on
:3000, which cost the previous session a wasted debugging round.

| check | result |
|---|---|
| before any jump | 0 pills |
| rail jump 240,240px → 2,830px | "Back to Chapter 31: Adversarial Robustness Lab" |
| press it | back to 240,240 exactly, pill gone |
| three Enters through search hits | label unchanged, returns to 240,540 — the reading spot, not hit 2 |
| contents-row click | marks |
| jump of 670px | 0 pills |
| far jump, then six screens of hand-scrolling | pill retires |

Two rounds were needed. The first run's short-jump case was badly constructed
and proved nothing — re-doing it properly is what surfaced that a mark never
expired, which is where `landing` came from. A clipped icon in the first
screenshot turned out to be the Next.js dev badge; `elementFromPoint` named it
before anything was changed.

---

## 4. The clip audit

Nobody had watched the recorded clips since making them. Three were reviewed
this session by extracting frames with `ffmpeg` and reading them.

**Hit rate: two of three had real defects.** That number is the main finding of
this session, and it is the argument for reviewing the remaining eight.

### 4.1 multimodal-rag — six findings

| # | finding |
|---|---|
| 1 | At ~22s the caption still reads STEP 2 (adding the PDF) while the spotlight rings the **search-filter chips row** — an unrelated element |
| 2 | Steps 5/6 spotlight targets at or below the viewport bottom; no visible ring on the ask box |
| 3 | Step 6 says "click a citation and it opens that page with the region highlighted" — and never clicks one |
| 4 | Step 3 reads out "one text chunk, two table chunks, one figure" over a panel showing `1 page · 1 figure`; the counts are off screen |
| 5 | At 1600×1000 the first ~10s is a near-blank page and the right two-thirds is black through the middle |
| 6 | `Grounded · 53%` next to a demonstrably correct answer |

Findings 3 and 4 are script problems — re-recording would not have touched
them. 5 is the recorder's viewport and affects all eleven clips. 6 is the tool
judging itself, not a demo bug.

### 4.2 text-to-sql — one finding, but it is the whole tool

Every spotlight is correct; it escaped the recorder bug entirely because none of
its steps triggers a layout shift.

But **the clip never runs a query.** The final frame shows the typed question,
the Ask button unpressed, and the entire right half empty, while the narration
says: *"Press ask and it runs. If the query errors, the agent reads the database
error and retries itself. Results come back as a sortable table with a chart
picked to suit the shape of the data, and you can ask it to explain its own
reasoning."* Four claims, none shown.

This was diagnosable from the JSON alone before watching: step 5 typed, and no
step had `act: "click"` after it.

### 4.3 automl — clean, and deliberately left alone

Steps 2 and 6 ring the stage rail correctly. Step 3's ring *is* stale — placed
on the upload dropzone, and by the time it is on screen the dropzone is gone and
the ring frames `FILE automl-churn.csv / ROWS 240 / COLUMNS 10 / Target column:
churned`. But the narration at that exact moment is "240 rows, nine features,
and a churned column as the label", so the misplaced box sits on precisely the
data being described. Wrong by mechanism, right by accident.

It promises nothing it does not show: it stops at Config and says "Press train
when you are ready, it is your run from here."

Not re-recorded. The `dd67442` fix would replace that lucky hit with a hidden
ring — a correctness win nobody can see, at the cost of a step going unlit.

---

## 5. The recorder bug that survived its own fix

Part 268's `1820f7b` taught `place()` to re-measure after anything that moves the
page. Re-recording multimodal-rag against that fix reproduced finding 1
**unchanged**, which is what pointed at the real cause:

```js
const el = document.querySelector(`[data-wt="${sel}"]`);
if (!el || !spot) return;          // ← the bug
```

`1820f7b` handled *"the element moved"*. It did nothing for *"the element is
gone"*, and from inside `place()` those are indistinguishable — `querySelector`
returns null, the function returns early, and the box stays exactly where it
was.

`data-wt="mmrag-add"` lives on the upload dropzone. The dropzone is replaced the
moment ingest finishes. Every re-measure after that was a no-op, so the ring sat
over the space the dropzone used to occupy — which the filter chips had moved
into.

Fixed in `dd67442`: no anchor now means no spotlight.

```js
if (!spot) return;
const el = document.querySelector(`[data-wt="${sel}"]`);
if (!el) { spot.style.display = "none"; return; }
```

A step whose target disappears mid-way now goes unlit for the rest of its
narration. That is the honest outcome: a ring that has stopped tracking anything
is worse than no ring, because the viewer reads it as a claim about whatever is
underneath.

**This would have bitten any future demo whose anchor unmounts, not just this
one.** It was only found by re-recording and re-watching rather than assuming
the earlier fix covered it.

---

## 6. Two failures, two root causes, no blind retries

### 6.1 403 on every browser call to the Space

The first recording attempt died at the preflight, then at step 3's assertion.
Raw curl to `https://wram1708-ml-unified.hf.space/rag/mm-ingest` returned **200
in 11.7s** with the chart correctly extracted (Leeds 79.4, Bristol 91.2, Dundee
65.8, Cardiff 86.7) — so the backend was healthy and the fault was in the
browser path.

A headed Playwright run with response logging gave the answer directly:

```
RESP 403 https://wram1708-ml-unified.hf.space/rag/mm-ingest
```

`security/origin_policy.py` hard-blocks any browser `Origin` not on its
allowlist. curl succeeded because it sends no `Origin` header at all. The
allowlist:

```
https://ml-portfolio-rho.vercel.app
http://localhost:3000
http://localhost:3300
```

I had picked port **3200** to avoid disturbing the owner's server on 3000. The
safeguard was working exactly as designed; my port choice caused the failure.
**3300 is on the list and is evidently there for this.**

*(Incidental discovery: the App Safeguard Plan in
`~/.claude/plans/plan-multimodal-rag-curious-charm.md` has been implemented at
some point — `security/origin_policy.py`, `rate_limit.py`, `body_size.py` and
`events.py` all exist and are wired into `app.py`. Earlier notes describing CORS
as `allow_origins=["*"]` are out of date for `ml-api`. `ml-sql` is still `["*"]`.)*

### 6.2 The Ask button stayed disabled

text-to-sql's first recording failed with `could not click [data-wt="ask"]:
Timeout 15000ms`. A probe showed the button reading **"Load DB"**, disabled,
with `questionValue` correctly filled — so `!schema` was the cause, not the
typing.

Response logging again:

```
RESP 404 http://localhost:3300/sql/schema?db_ref=chinook
```

The request went to the frontend itself. **text-to-sql talks to a separate
service** — `ml-sql`, with its own `NEXT_PUBLIC_ML_SQL_URL` and its own Space. I
had set only `NEXT_PUBLIC_ML_UNIFIED_URL`. Its Space is healthy and its CORS is
still `["*"]`, so no origin issue there.

**Both failures were root-caused with a raw call or a logged reproduction before
any retry.** Neither was retried on a guess.

---

## 7. What shipped in the two clips

### 7.1 multimodal-rag — 109.6s, 8 steps (`5d3ee25` + `83221be`)

| finding | before | after |
|---|---|---|
| 1 | ring on the filter chips | tracks the ingest card, then hides when it unmounts |
| 2 | no ring on the ask box | on the box, question typed |
| 3 | citation click promised only | clicked and opened: `FIGURE/High`, `dense #1`, `keyword #1`, rerank 0.99, "Why was this cited?" |
| 4 | counts off screen | ring exactly on `1 text · 2 table · 1 figure chunks` as they are spoken |
| 5 | dead space | unchanged, deliberately |
| 6 | Grounded 53% | unchanged — the tool, not the demo |

Two anchors added, since the whole page had only three (`mmrag-add`,
`mmrag-ask`, `mmrag-send`):

- `mmrag-chunks` on the ingest summary's count line
- `mmrag-cite` on the top-ranked evidence card

`mmrag-cite` is a **wrapper**, not a prop on `RagSourceCard`: that component is
shared with the other RAG tools and sits ten lines under the file-length limit,
and which card a demo clicks is a fact about this page, not about what a
citation card is. A plain div, not `display:contents` — the recorder measures
the element to place its spotlight, and a box-less element measures as zero.

The answer is right and cited: *"Dundee had the lowest on-time delivery rate at
65.8%"*, against a figure whose value appears nowhere in the document's text.
Gemini rate-limited during the run and the tool fell back to Mistral, which the
UI says out loud in the clip.

### 7.2 text-to-sql — 89.1s, 8 steps (`b47f06a` + `a6ef651`)

Step 7 now shows the button reading **"Running…"** with the pipeline advancing
`Schema → SQL → Execute → Explain`. Step 8 shows the generated SQL, `RESULTS 10
rows · 27ms`, the real table (Helena Holý 49.62, Richard Cunningham 47.62, Luis
Rojas 46.62 …), CSV/JSON/MD/Jpynb exports, AI Reasoning, column lineage,
auto-insights and a chart.

Two anchors: `data-wt="ask"` on the button, and `sql-results` as a wrapper in
`TextToSqlRunner.tsx`.

**The results anchor is conditional on there being results.**
`QueryResultPanel` renders whether or not a query has run, so a permanent anchor
is one `waitFor` resolves against instantly — the same as not waiting at all.

It is a wrapper because `QueryResultPanel.tsx` is **403 lines**, past the
project's 400-line limit. Splitting it was not this change, so the anchor went
in `TextToSqlRunner.tsx` (201) instead. `UserGuideModal.tsx` is also 403.

All eight steps of both clips were verified frame by frame, not just the ones
that changed.

---

## 8. Three things still open in text-to-sql

Diagnosed this session, not fixed. Presented to the owner; no go-ahead given yet.

### 8.1 Step 3's assertion cannot catch what it exists to catch

`expect: "Album"` matches the sample question *"top 5 artists by total **album**
count"*, not the schema panel. This is not theoretical: **the broken run in §6.2
sailed straight past step 3 with no schema loaded at all.** The guard whose
entire job is to catch "the tool did not actually do the thing" failed to catch
exactly that.

Fix: assert on something only the schema panel can produce — `PlaylistTrack` or
`8,715`. Step 8's `"select"` is thinner than it looks and deserves the same.

A survey of all eleven demos' assertions was done while checking this:

| demo | assertions | verdict |
|---|---|---|
| dns-tunneling, malicious-package, password-audit, phishing, tls-headers, yara, extension-permissions, email-auth, multimodal-rag, automl | 24 total | result-specific strings — fine |
| text-to-sql | step 3 `"Album"`, step 8 `"select"` | the only weak ones |

No recording needed for this one.

### 8.2 The narration overstates the schema click

Step 2 says *"I will pull its schema in now"* while the schema is already listed
in the sidebar — it auto-loads on mount. The click is real but re-loads what is
already there. Fixable only by re-filming, since narration is baked audio.

### 8.3 The heatmap is a real defect in the tool

`detectViz` in `SqlChart.tsx:32`:

```ts
if (ci.length>=2 && ni.length===1) return { type:"heatmap", cx:ci[0], n:ni, c2:ci[1] };
```

Two categoricals plus one numeric ⇒ heatmap. But the query returns `FirstName |
LastName | Total Spending`, and those two categoricals are not independent
dimensions — they are two halves of one person. Every pair is unique, so the
heatmap is a 10×10 grid with ten filled cells and ninety zeros. That is exactly
what is on screen, under narration promising "a chart picked to suit the shape
of the data".

**The tool already has the information needed to reject this.** Its own
auto-insights panel, three inches above the chart, reads *"FirstName — 100%
distinct — likely a key"* and the same for LastName. The chart chooser simply
does not consult it.

Fix: a cardinality guard before the heatmap branch — a heatmap only makes sense
when both categorical columns actually repeat. If either is near-100% distinct,
they are identifiers, and it should fall through to the bar branch below.
`detectViz` is a pure function, so this is unit-testable offline with zero API
calls, and it improves the tool for every user, not just the clip.

8.2 and 8.3 could share a single recording.

---

## 9. Cost accounting

Estimated 3 paid calls. Spent roughly 10.

| what | calls |
|---|---|
| raw curl ingest, to prove the backend healthy | 2 (vision + OCR) |
| recording attempt on :3200 | 0 — 403 before any processing |
| multimodal-rag recording #1 | 3, plus a Gemini rate-limit retry before the Mistral fallback |
| multimodal-rag recording #2, after the recorder fix | 3 |
| text-to-sql attempt with no schema | 0 — never reached the LLM |
| text-to-sql recording | 1 |

**The overrun was debugging, not filming.** The estimate counted the happy path
only and budgeted nothing for the 403 chase or for a second run once the
recorder bug surfaced. A future estimate for "re-record a clip" should assume at
least one diagnostic run.

Per-run costs, traced through the code and worth keeping:

- `automl` — **0 paid calls.** `routers/training.py` has no API key reference at
  all. Pure server compute.
- `multimodal-rag` — **3.** One vision caption (`mistral-medium-latest`, falling
  back to `gemini-3.6-flash`) and one OCR page (`mistral-ocr-latest`), both from
  `_caption_page`, plus one answer on `gemini-2.5-flash` (the frontend default
  when no user key is set). Groundedness is **not** a call — `score_groundedness`
  runs on local embeddings.
- `text-to-sql` — **1**, now that it actually submits. Was 0.

**No dollar figure is obtainable from this project.** `analytics.py` records
upload counts, query counts, latency and cache hits — no tokens, no spend.

---

## 10. How each claim was verified

| claim | evidence |
|---|---|
| return pill works | headed Chrome, 7 scripted checks against a fresh `next dev` on :3100 |
| the clips were wrong | `ffmpeg` frame extraction, read directly — not inferred from the JSON |
| the backend was healthy | raw curl, 200 in 11.7s with the correct chart values |
| the 403 was origin policy | Playwright response log + `origin_policy.py` read directly |
| the Ask button was disabled by `!schema` | `page.evaluate` reading `disabled` and the field value |
| ml-sql was the missing backend | 404 URL in the response log, then a 200 from the Space by curl |
| the recorder bug survived `1820f7b` | re-recorded and re-extracted; frame at 22s unchanged |
| the fixes landed | frame extraction of both new clips, all 8 steps each |
| assertions are otherwise sound | enumerated all 26 `expect` values across 11 demos |
| the heatmap is degenerate | the frame itself, plus the tool's own "100% distinct — likely a key" |

---

## 11. Lessons

**Watch the artefact, not the code that produced it.** Three clips reviewed, two
broken, and both defects were invisible from the source — one needed the video,
one needed only the JSON but nobody had read it either. Everything shipped in
Parts 267–268 was verified as *code*; no one had checked what the code produced.

**A fix verified against the case that motivated it is not verified.** `1820f7b`
demonstrably fixed the extension-permissions clip. It did nothing for the
mmrag case, because "moved" and "unmounted" look identical from inside
`place()`. Re-recording and re-watching is what caught it — reasoning about the
diff would not have.

**An assertion that can pass on the wrong text is worse than no assertion**,
because it is trusted. `expect: "Album"` let a completely broken run through
step 3, and the recorder's own comment says the whole point of `expect` is to
catch a tool that silently failed.

**A tool can already know the thing it is getting wrong.** The chart chooser
picks a degenerate heatmap while the panel above it announces both columns are
100% distinct keys. Two features computing the same fact, one of them ignoring
it.

**Estimate the debugging, not the task.** 3 calls estimated, ~10 spent, and
every extra one was diagnosis.

**My own environment choice caused a failure that looked like a product bug.**
Port 3200 vs the allowlisted 3300. Worth checking what the safeguards allow
before blaming them.

---

## 12. Not done

- **The other eight clips have never been reviewed.** Two of three reviewed had
  real defects; that rate does not justify assuming the rest are fine. Free to
  check — costs only time.
- ~~**The three text-to-sql items in §8.**~~ **CLOSED 2026-09-02, Part 272 §2** (`3132301`).
- **`automl`** — reviewed, deliberately not re-recorded (§4.3).
- **Nothing checked on live Vercel.** Parts 269, 270 and 271 were all verified
  against localhost only. The return pill, the contents demo markers, the
  read-aloud speeds and both new clips are unverified in production.
- ~~**Part 1 of the handbook** — blocked on splitting~~ **UNBLOCKED and 8 of 11
  chapters built, 2026-09-02, Part 272 §5/§8.** It was three files needing a
  split, not two: `pipeline-builder/page.tsx` was 397.
- **The hosted TTS path** has still never run against a live paid vendor.
- **`QueryResultPanel.tsx` and `UserGuideModal.tsx` are both 403 lines**, past
  the 400-line limit. Pre-existing; worked around rather than split.
- **Four pre-existing `react-hooks/set-state-in-effect` lint errors** in
  `QuestionInput.tsx` and `TextToSqlRunner.tsx`. Confirmed present before this
  session's changes by linting the stashed tree; left alone.

---

## 13. Local environment note

`.next` is currently built with `NEXT_PUBLIC_ML_UNIFIED_URL` and
`NEXT_PUBLIC_ML_SQL_URL` pointed at the two HF Spaces, because that is what
recording requires. A plain `npm run build` resets it. Any `next start` restarted
against the current `.next` will talk to the Spaces rather than a local backend.

**Recording recipe, for next time:**

```
NEXT_PUBLIC_ML_UNIFIED_URL=https://wram1708-ml-unified.hf.space \
NEXT_PUBLIC_ML_SQL_URL=https://wram1708-ml-sql.hf.space \
  npx next build && npx next start -p 3300
DEMO_BASE_URL=http://localhost:3300 node scripts/record-demo.mjs <demo>
```

Port **3300** is not optional — it is the allowlisted one (§6.1).
