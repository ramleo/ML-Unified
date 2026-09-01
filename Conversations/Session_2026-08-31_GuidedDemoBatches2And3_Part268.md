# Session 2026-08-31 (Part 268) — eight more guided demos, and four ways the recorder was quietly lying

Continues Part 267 (`Session_2026-08-31_HandbookAudioGuidedDemosAndIngestFix_Part267.md`),
which built the guided-demo system and shipped the first three clips. This one
is two more batches of demos on top of it. No chapter text changed, and no
backend file was touched.

---

## 0. Where things stand in one paragraph

The handbook now has guided demos on **11 of its 50 chapters**, up from 3.
Batch 2 added the YARA File Scanner, Password Strength & Breach Checker, TLS /
Security-Headers Scanner and Email Header Authentication Checker; batch 3 added
the Malicious Package Scanner, Extension Permission Analyzer, DNS Tunneling
Detector and Phishing Email Body Classifier. Every one of the eight was chosen
because it demonstrates honestly without spending anything — no LLM call, no
camera, no model download. The recording work exposed four separate faults in
the recorder itself, all of which could have shipped a clip whose narration did
not match its picture. Three commits, all in ml-portfolio.

---

## 1. The commits

| Commit | Repo | What |
|---|---|---|
| `1fbcd74` | ml-portfolio | batch 2 — four guided demos, and the assertion that was lying |
| `b216582` | ml-portfolio | tell the recorder to blame the backend, not the demo |
| `1820f7b` | ml-portfolio | batch 3 — four demos that cost nothing to run, and three more recorder faults |

No HF Space upload this session: nothing under `services/ml-api/**` changed.
The backend is unchanged from `6974290` in Part 267.

---

## 2. What the owner asked for, in order

1. **"can we start next batch?"** — batch 2. Four tools proposed with reasons,
   approved as recommended.
2. **"go with your recommendation"**
3. **"yes"** — commit and push batch 2.
4. Two questions about weekly usage reset. Answered honestly: no tool in the
   session can read subscription quota, `/usage` is the only surface, and it
   rounds to `1d`. Suggested watching for the flip to `23h` to pin the boundary.
5. **"what this means?"** — on the warning that the backend has to be reachable
   or the recorder will abort. Explained.
6. **"can't it happen automatically?"** and **"will that be a problem?"**
7. **"what is solution for this?"** then **"explain in simple words"** — the
   preflight design, described twice, second time without code.
8. **"yes"** — build it.
9. **"yes"** — commit and push the recorder change.
10. **"next batch?"** — batch 3. Three options offered; owner picked option 1.
11. **"proceed with 1, but do it one by one, weekly usage is 78% and i need it
    for 2 more days"**
12. **"yes"** — commit and push batch 3.
13. **"will it affect the app?"** — about the local build pointing at the Space.
14. **"do this — say the word and I'll rebuild it back"**
15. **"document the above conversations to Conversations/"**

---

## 3. Batch 2 — the four tools, and why those four

Selection criteria, stated before any work: zero LLM cost, deterministic, no
camera or microphone (Playwright has no real webcam), no heavy in-browser model
download.

| Ch | Tool | Verified real result |
|---|---|---|
| 50 | YARA File Scanner | PDF trips `High_Overall_Entropy`; a hand-written rule matches a marker at offset 252 with hex |
| 43 | Password Strength & Breach Checker | `Summer2024!` → Fair, 17 min crack, **3,614 breaches**; passphrase → Very strong |
| 48 | TLS / Security-Headers Scanner | own domain → `strong`, TLSv1.3, cert 88 days left, **all six headers present** |
| 37 | Email Header Auth Checker | GitHub sample → Likely legitimate, SPF `~all`, DMARC `p=quarantine`, DKIM key active, aligned |

Deliberately excluded: SIEM triage, prompt injection, AI code detector, document
intelligence and contract reconciliation, all of which hit a paid LLM on every
recording run. Also excluded: face liveness, ASL and pose tools.

**Every claim in the narration was verified against a live call before the
script was written**, not after:

- HIBP range API by hand → `Summer2024!` = 3,614, `Password123!` = 295,389.
- `curl -sI` on the live site → all six security headers present.
- The YARA endpoint with both samples → PDF matches exactly one rule
  (`High_Overall_Entropy`), the marker text file matches none of the built-ins.
  The custom rule returns offset 252 and the marker's hex.
- `/email-auth/check` with the sample headers → verdict, `sp=reject`, selector
  `pf2023` live and unrevoked, both alignment checks pass.
- zxcvbn locally → `Summer2024!` scores 2 (Fair), `velvet-otter-parade-97`
  scores 4.

This is why zero batch-2 recordings failed for a content reason.

### The sample file question

The YARA demo wanted something that would trip a built-in rule. **EICAR was
considered and rejected**: it is designed to be safe to trigger, but committing
it to a public repo risks the owner's own antivirus quarantining files in their
working tree, and a push being blocked. Instead the demo uses the already
bundled `northwind-q3.pdf` (entropy rule, which is a *better* narration beat —
it is the informational-not-a-verdict story) plus a new 385-byte
`public/samples/yara-marker.txt` containing nothing but a marker string.

---

## 4. Batch 3 — the four tools

All four are **entirely client-side**: no API call at all, and every one already
ships its own sample input, so no fixtures were added.

| Ch | Tool | Verified real result |
|---|---|---|
| 42 | Malicious Package Scanner | `lodahs` one edit from `lodash`; `postinstall` pipes remote file to shell; six source signals with line numbers incl. 4.9 bits/char entropy |
| 34 | Extension Permission Analyzer | High risk driven by the **combination**: `<all_urls>` + interception + cookies |
| 36 | DNS Tunneling Detector | 1 of 5 parents flagged at 4.6 bits/char over 60 chars; Google/GitHub/CDNs pass |
| 44 | Phishing Email Classifier | Likely phishing → Likely safe at 0%, model's own words shown both directions |

The owner asked for these **one at a time** because weekly usage was at 78% with
two days to go. Each tool was: read once, anchored, scripted, rebuilt, restarted,
recorded, verified with one extracted frame, then moved on.

### Why Part 1 was not the batch

The handbook's opening arc — 11 chapters on the ML pipeline — has only the
AutoML demo, and that is where demos matter most to a reader. It was explicitly
offered as an alternative and explicitly *not* bundled in without asking,
because:

- `src/app/tools/preprocessing/page.tsx` is **367 lines**
- `src/app/tools/feature-selection/page.tsx` is **369 lines**

Both past the 350-line modularize threshold, so adding a single `data-wt`
attribute obliges a page split first. That is a different-sized task than a demo
batch, and the owner should choose it rather than receive it. `feature-engineering`
at 345 is doable as-is. **Still pending.**

---

## 5. THE RECORDER FAULTS — four of them, all found by using it

Every one of these could produce a finished clip that describes something the
viewer is not seeing. That is the exact failure Part 267 already fixed three
instances of, which is the point: the class of bug keeps coming back in new
shapes, so the guards have to keep getting sharper.

### 5.1 The assertion that could satisfy itself

`expect` read `document.body.innerText`. **The narration caption is a child of
`body`.** So a step could satisfy its own assertion with its own words — an
assertion met by the claim it exists to check is worse than no assertion.

Caught when the YARA run reported `step 4` passing on `"matched"` while the
backend was dead: the word came from the caption saying *"which patterns
matched"*.

Fix — read every body child *except* the overlay:

```js
const seen = await page.evaluate(() =>
  Array.from(document.body.children)
    .filter((el) => el.id !== "__demo_cap" && el.id !== "__demo_spot")
    .map((el) => el.innerText)
    .join("\n")
);
```

Then **all seven existing demo scripts were audited** for `expect` strings that
appear in their own step's `say`. None did, so the three earlier clips' checks
had been genuine. The step-4 assertion was also tightened from `"matched"` to
the exact rule name `High_Overall_Entropy`.

### 5.2 The error that blamed the wrong file

The local build points at `http://localhost:8000`. Nothing runs there. The YARA
recording spent **two minutes narrating** and then said:

```
step 10 expected "MyTestRule" on screen and it is not there
```

which sends you reading the demo script, where the problem is not.

Root-caused with a direct probe rather than a guess — a throwaway Playwright
script logging `requestfailed`, which printed
`http://localhost:8000/yara-scan/builtin net::ERR_CONNECTION_REFUSED` and the
page's own `Failed to fetch`.

Fix (commit `b216582`), two listeners on anything the page requests off-site:

```js
const isBackend = (url) => !url.startsWith(BASE);   // /api/track 400s locally; not our business
page.on("requestfailed", ...);                       // dead backend
page.on("response", r => r.status() >= 500 && ...);  // Space mid-rebuild
```

Run as a **preflight** before `narrate()`, because narration is a `say` call and
an ffmpeg convert per step, all spent before the browser opens. The same
listeners stay attached during recording for calls that only happen on click,
and are checked **before** `expect`, so the cause is reported instead of the
symptom.

Measured: **1.1 seconds** instead of two minutes, with the URL, the errno and
the fix.

**Both paths were tested.** Backend down at load → preflight aborts. Backend
down mid-run → the in-run listener fires at step 1; tested by copying the script
to `scripts/_tmp-record-test.mjs` with the preflight bypassed, running it, then
deleting that file by name. The happy path was re-verified by re-recording the
TLS clip against the live Space and restoring the committed file rather than
leaving a re-encode in the diff.

### 5.3 The spotlight framed the wrong thing

`scrollIntoView({ behavior: "smooth" })` is asynchronous, and the rect was read
immediately after. On a long page the box lands over whatever used to be there.
The extension clip highlighted an unrelated `cookies` permission row while the
narration described the dangerous-combinations card.

**This was only caught by looking at an extracted frame.** Every assertion
passed; the text was all present; only the picture was wrong.

Fix: a shared `place(page, at)` helper, called after a 600 ms settle, again
after `waitFor`, and again after any action — since a click that reveals a panel
pushes everything below it out from under the box.

> **Correction, 2026-09-01 (Part 271 §5).** This fix was incomplete, and the
> incompleteness was found only by re-recording another clip and watching it.
> `place()` re-measures where an anchor *is*; it returns early when the anchor
> is **gone**, leaving the box frozen at its last position. The multimodal RAG
> clip spent fourteen seconds ringing the search-filter chips because
> `mmrag-add` lives on the upload dropzone, which unmounts the moment ingest
> finishes. "Moved" and "unmounted" are indistinguishable from inside `place()`.
> Fixed properly in `dd67442`: no anchor now hides the spotlight.

### 5.4 Assertions were case-sensitive against *rendered* text

The DNS clip failed on `"Possible DNS tunneling channel"`. The tool was working
perfectly. The label is styled `text-transform: uppercase`, so `innerText`
returns `POSSIBLE DNS TUNNELING CHANNEL`. **Nothing in the JSX tells you that.**

Confirmed by probe before changing anything — the probe printed the full result
panel, matching every number the narration claimed. Fix: compare
case-insensitively.

### 5.5 A stale server serves a stale build

`next start` holds whatever `.next` existed when it launched. Rebuilding without
restarting records the *previous* bundle — the extension demo failed to find its
brand-new anchor for exactly this reason. Not a code fix; a procedure fix. Every
subsequent tool used: rebuild → `lsof -ti :3000 | xargs kill` → restart → record.

---

## 6. One narration corrected against its own footage

The phishing clip's step 7 said the contributing words *"flip to green"*. The
extracted frame showed two of them (`retail`, `take ×3`) still red. Rewritten to
*"mostly green now... a couple still lean the other way and the model weighed
them against the rest"*, and re-recorded. Roughly 90 seconds of compute to not
ship a sentence contradicted by the screen behind it.

---

## 7. The file-length rule, applied mid-task

Adding the preflight took `scripts/record-demo.mjs` to **362 lines**, past the
350 threshold. Rather than ship it over the line and flag it afterwards, the
sound half was extracted first:

- `scripts/demo-audio.mjs` (73 lines) — `have()`, `narrate()`, `voiceTrack()`, `mux()`
- `scripts/record-demo.mjs` (now 311, later 328) — knows nothing about ffmpeg

Done inline, **not** via a subagent, per the standing rule about asking first.
`scripts/check-file-length.sh` passes: *646 tracked source files, none over 400.*

---

## 8. How each change was verified

- **One extracted frame per clip, read visually.** This is what caught the
  spotlight bug and the phishing overclaim — neither was detectable from
  assertions or logs.
- **All eight clips' `expect` assertions passed genuinely** after the caption
  fix.
- **Handbook launchers confirmed present** for every new chapter via a Playwright
  probe reading `nextElementSibling.className` on each chapter heading — all
  returned `hb-demo-open`.
- **Chapter ids grepped against `public/handbook.md`** before each script was
  written; all four batch-3 ids matched exactly once.
- `npx eslint` clean on every touched directory; `check-file-length.sh` passes.
- Live-bundle check on the deployed site confirmed production was never affected
  by the local build target.

---

## 9. The local build target — a non-issue, confirmed

Recording needs a reachable backend, so the local site was rebuilt against
`https://wram1708-ml-unified.hf.space`. Asked whether this affects the app:
**no**, for three checkable reasons — Vercel builds from source with its own env
vars, `.next` is gitignored, and `.env.local` was never edited.

At the owner's request the build was returned to `localhost:8000` at the end.
Verified afterwards: `localhost:8000` is back in the chunks. The bundle still
contains `hf.space` strings, but they are **not** the API base — 6 ×
`wram1708-ml-unified` and 2 × `wram1708-ml-sql` from
`src/app/docs/page.tsx`, `src/components/ProjectsSection.tsx` and
`src/data/registry.json`, all long-standing hardcoded display links. Checked
rather than assumed.

---

## 10. Weekly usage question — answered honestly

Asked when the weekly limit resets, and then for the exact remaining hours. No
tool in this session can read subscription quota, so no number was invented.
`~/.claude/` was searched for a cached reset timestamp; the only hit was
`cache/changelog.md`, which is documentation text. `/usage` fetches it from the
server and does not persist it. Practical answer given: watch for the display to
flip from `1d` to `23h`, which marks the 24-hour boundary exactly.

The 78% figure then shaped the rest of the session — batch 3 was done one tool
at a time with minimal re-reads, and no speculative re-recording was performed.

---

## 11. Things worth carrying forward

- **An assertion that can be satisfied by the thing it is checking is not an
  assertion.** The caption-in-`innerText` bug is the second-order version of the
  Part 267 lesson.
- **Assertions check text; only a frame checks the picture.** Two of this
  session's four faults were invisible to every passing test.
- **A negative result deserves a probe, not a guess.** Both the dead-backend and
  the uppercase-label failures were root-caused with a direct Playwright probe
  before a single line was changed. The DNS "failure" turned out to be a working
  tool and a broken test.
- **Verify the claim before writing the narration.** Every number in batch 2 was
  fetched from a live source first; zero batch-2 runs failed on content.
- **`next start` does not hot-swap a rebuild.** Restart between build and record.
- **Preflight is over-eager for client-side tools.** All four batch-3 tools make
  no backend call, yet the page's own `/health` ping means preflight still
  refuses to run against a dead backend. Harmless in practice, but it is a false
  block and worth narrowing if it becomes annoying.

---

## 12. Still open

- ~~**The three oldest clips**~~ — **HANDLED 2026-09-01 (Part 271 §4–§7).**

  > **Correction.** Two claims here were wrong. **"No API cost"** — `automl` is
  > free, but `multimodal-rag` costs 3 paid calls per recording and
  > `text-to-sql` 1. And **"highlight boxes may sit slightly off"** badly
  > understates it: reviewing the clips frame by frame found `multimodal-rag`
  > promising a citation click it never performed and reading out counts that
  > were off screen, and `text-to-sql` narrating SQL, a results table, a chart
  > and self-explanation over an unpressed button and an empty panel. Those are
  > script faults; re-recording alone would not have touched them.
  > `automl` was reviewed and deliberately left un-refilmed.
- **Part 1 of the handbook** — 11 chapters, one demo. Needs `preprocessing` (367)
  and `feature-selection` (369) split before anchoring.
- **The hosted TTS path has still never run against a live paid vendor** (carried
  over from Part 267).
- Three untracked files in ML-Unified root (`test_invoice.pdf`,
  `test_llm_invoice_items.py`, `test_pipeline.csv`) — still the owner's call.
- **Three handbook navigation requests** — search bar (**shipped 2026-09-01,
  Part 269**), return-to-position scrolling (**partly shipped**), and a video
  marker in the contents (**still open**). See §13.
- **A reported bug: 2x speed does not work properly for audio**, on both handbook
  surfaces — the recorded demo clips and the chapter read-aloud bar — and worst
  for the live-narrated voices. Not reproduced yet. See §13.4.

---

## 13. Requested next — handbook navigation and one bug

Three asks raised at the end of this session, all about *moving around* the
handbook rather than its content, plus one reported bug. Recorded here verbatim
in intent; at the time of writing none had been designed, estimated, or in the
bug's case even reproduced.

> **Status as of 2026-09-01 (Part 270).** 13.1, 13.3 and 13.4 are all
> shipped. 13.2 is partly shipped — the mechanical difficulty is solved by a
> chapter rail, the "return to where I jumped from" half is not built.
> Per-item notes are inline below; the builds are written up in
> `Session_2026-09-01_HandbookSearchAndChapterRail_Part269.md` (13.1, 13.2)
> and `Session_2026-09-01_ContentsDemoMarkersAndSpeedBug_Part270.md`
> (13.3, 13.4).
>
> **Two claims in 13.4 below are wrong and are left in place with this
> correction rather than edited away.** Voices do *not* degrade above 1.5 on
> the machine this was measured on — the same sentence tracks `base/rate`
> within ~5% to 3x with every word-boundary event still firing. And a hosted
> provider's fixed audio file *can* be sped up: it plays through an
> `HTMLAudioElement`, which has a `playbackRate`. Part 270 §6 has the
> measurements. The first hypothesis in 13.4 — that the narrator never learns
> the video sped up — was correct and was the whole bug.

### 13.1 A search bar in the handbook — SHIPPED 2026-09-01

> Built in Part 269 across four commits: `2c10e82` (bar, contents indexing,
> substring matching, chapter rail, two positioning fixes), `f5abd25` (clear
> button), `4894b39` (undo history), `43ef795` (the Cmd-K hint). The note below
> about reusing `wordMatch.ts` was followed — it moved to `src/lib/search/` and
> gained an opt-in substring flag rather than having its behaviour changed
> underneath the RAG panel that also uses it.

The handbook is 17,406 lines across 50 chapters in a single page. There is a
table of contents and nothing else — no way to find a term without the browser's
own Ctrl-F, which on a document this size is slow and gives no sense of *where*
a hit lives.

Worth knowing before designing this: the site already has live-search matching
logic in `wordMatch.ts` (prefix + stemmer + irregular list, deliberately not a
lemmatizer — see the `search-matching-hybrid` note), so there is an existing
convention to follow rather than a new one to invent.

### 13.2 Return-to-position scrolling — SHIPPED 2026-09-01 (Part 271 §3, `d3217eb`)

> *"option to scroll up from wherever a user wants to scroll up in handbook
> section, it tedious to scroll up every time whenever i scroll down to a
> particular part of handbook."*

The complaint is concrete: having scrolled deep into a chapter, getting back up
means dragging all the way. What is wanted is a way back up from wherever you
are — at minimum a back-to-top affordance, and possibly a "return to where I
was" that survives a jump. Worth clarifying which of the two is meant before
building, since they are different features:

- **back to top** — one button, always available, trivial
- **return to previous position** — remembers where you jumped *from*, so
  following a contents link and coming back is one click

> **2026-09-01:** the first half is effectively covered by the chapter rail
> shipped in `2c10e82` — a full-height drag target on the right edge with a
> tick per chapter, which removes the need to find a 4px scrollbar thumb on a
> 387,000px page. The second half — remembering where a jump came *from* — is
> **still not built**.

### 13.3 A video marker in the contents — SHIPPED 2026-09-01

Eleven of the fifty chapters now have a guided demo, and nothing in the table of
contents says which. A reader scanning the index cannot tell that chapter 43 has
a clip and chapter 44 did not until this session.

Implementation note for whoever picks this up: the contents list is generated
markup in `public/handbook.md`, and the set of chapters with demos is already
available programmatically — `demoForChapter(id)` in `src/data/demos/index.ts`
is exactly this lookup, and `DemoLauncher.tsx` already uses it to decide where to
insert a launch button. So the marker can be derived rather than hand-maintained,
which matters because the list grows every batch.

**Per the standing no-emoji rule, the marker must be an inline SVG, not a
character like ▶ or a video emoji.**

### 13.4 BUG — 2x speed does not work properly for audio — FIXED 2026-09-01

> Reproduced, root-caused and fixed in Part 270 across two commits: `4ea631e`
> (the clip narrator now speaks at the clip's speed — 8 of 10 lines were being
> cut off mid-sentence at 2x, now 0) and `9dcf66b` (1.75x and 2x added to the
> read-aloud bar, which had no defect beyond not offering them). See the
> correction in the status block above before trusting the analysis below.

Reported by the owner, **not yet reproduced or root-caused**. Worst at 2x, and
specifically noted as bad *for the list of added voices* — i.e. the
voice-override picker, rather than the baked-in "As recorded" track.

**It affects both surfaces, and both of them are in the handbook section:**

- the **recorded demo clips** (`HandbookDemo.tsx` + `DemoVoice.tsx`), and
- the **read-aloud bar** for the chapter text itself (`HandbookAudio.tsx`).

That is worth stating plainly because the two are separate pieces of code that
happen to share the same defect. They both speak through
`speechSynthesis` on their own clock, independent of anything they are supposed
to be keeping time with.

Two findings from a read of the code, offered as **the most likely explanation,
not a confirmed cause** — nobody has reproduced this yet:

1. **The narrator never learns the video sped up.** `DemoVoice.tsx` schedules
   cues off `video.currentTime` (line 171), which does keep up when the clip is
   sped up — the *cues* fire at the right frames. But the speaking itself is
   `src/lib/presenter/voice.ts:68`, which hardcodes:

   ```ts
   u.rate = 0.95;
   u.pitch = 0.95;
   ```

   Nothing anywhere reads `video.playbackRate`. So at 2x the picture arrives at
   each cue in half the time while every line still takes its full wall-clock
   length to speak. Lines would run into each other, or get cut off by the next
   cue firing — which matches "not working properly" far better than silence
   would.

2. **The read-aloud bar tops out at 1.5 — there is no 2x to select.** Its speed
   selector (`HandbookAudio.tsx:373`) offers
   `[0.75, 0.85, 0.95, 1, 1.1, 1.25, 1.5]`. So on that surface the report has two
   possible readings and both need addressing: 2x is not offered at all, *and*
   the fastest settings that are offered may already sound wrong. Unlike the
   clips, this bar has no video to stay in sync with — its `u.rate` is set from
   the picker (`HandbookAudio.tsx:219`), so if 1.25 and 1.5 already misbehave the
   cause is not desync but the voice itself: many OS voices degrade badly above
   about 1.5, and the compact voices most machines ship degrade earliest. That
   would be a ceiling in the platform, not a bug in this code — but it has not
   been checked, and it must be before anyone claims either.

Note the asymmetry that makes this consistent with the report: the **"As
recorded"** track is muxed into the video file, so the browser resamples it with
the picture and 2x simply works. Every **live-narrated** voice — browser voices
and any bring-your-own-key provider — is spoken independently of the video and
therefore does not scale. That is exactly "especially for the list of added
voices".

Fixing the clip side likely means passing the video's current `playbackRate`
into the presenter and multiplying `u.rate` by it. Fixing the reading-bar side
is likely just extending the selector — assuming the voices hold up, which is
the thing to check first. Both share one caveat: `speechSynthesis` clamps rate
(roughly 0.1–10) and real OS voices degrade well before the clamp, so 2x may be
reachable for the browser path and not for a hosted provider returning a fixed
audio file, which cannot be sped up this way at all.

**Reproduce on both surfaces before changing anything.** Two separate files are
involved and they may not have the same defect.

---

## 14. Standing constraints unchanged

- **"first tell" = stop.** Text only until an explicit "proceed".
- **Never spawn a subagent without asking.** None were used this session,
  including for the file split that the CLAUDE.md rule suggests delegating.
- **Always ask before `git commit`.** Asked three times, approved three times.
- **Never `git add -A`.** Every commit staged explicit paths with `git -C`.
  Bash cwd drifted again mid-session and broke a relative-path command, which is
  exactly why.
- **Only delete files created this session, named individually.** One temporary
  file (`scripts/_tmp-record-test.mjs`) was created and deleted by name.
- **No paid API calls for self-verification without asking.** Zero this session:
  HIBP's free range API, DNS, and the project's own Space.
- **No file over 400 lines**, modularize over 350 — applied to the recorder
  mid-task rather than after.
- **HF upload after any backend commit** — not triggered; no backend file changed.
- **Always push after commit, always report the short hash.**
