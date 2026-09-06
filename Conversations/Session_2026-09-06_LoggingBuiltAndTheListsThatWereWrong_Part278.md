# Session 2026-09-06 — Part 278

## Logging built, and the lists that were wrong

**19 commits.** 13 in `ml-portfolio`, 6 in `ML-Unified`. Same day as Part 277,
which covered the provider audit; this is everything after it.

`LOGGING_SPEC.md` went from "agreed, nothing built" to fully implemented.
103 instrumented call sites, retention scheduled, and the last unrecorded
walkthrough clip filmed.

The engineering went fine. The way it was reported did not, and that is the
part worth keeping.

---

## 1. What was asked, in order

The session opened on the handbook — one clip left to record — and ended with
the whole logging spec built. Every step in between was the user asking for
one thing at a time and checking the answer.

| Ask | Outcome |
|---|---|
| continue with handbook | found the clip blocked on a stale script |
| judge provider, option B | Cohere → Mistral → Gemini cascade (`fd5a499`) |
| do logging spec | vocabulary, funnel, sink, privacy (`2b2b7f8`, `8610859`) |
| batch A | 10 tools, then 11 more, then 33 more |
| do those 15 calls | the ones deliberately skipped, done on request |
| stages 2/3/6/8 | search, demos, exports, sessions (`ebe8ceb`) |
| retention job | written, run, verified active |
| the clip | recorded, audited frame by frame (`ac20690`) |

---

## 2. The judge cascade

The reconciliation clip could not be recorded because the tool's judge was
Mistral → Gemini, and Part 277 had just established Mistral has no reserved
free capacity. So every scan fell to Gemini, the only paid key.

Two options were put to the user: swap the primary (one line), or generalise
to a candidate list. They chose the list.

`JUDGE_CANDIDATES` is now Cohere → Mistral → Gemini, matching
`generation.py`'s cascade. The latch generalised from a boolean to a cursor
that only moves forward, so a dead provider costs one wasted call per scan
across both the judge and confirm chains.

**Per-provider pacing was the non-obvious part.** The old `_MIN_CALL_INTERVAL`
was a single 1.15s tuned to Mistral's 1 req/sec. Cohere's trial keys are
capped per *minute* (20/min), so a Mistral-shaped gap would have tripped it on
the fourth call and knocked the new primary straight out of the cascade — on a
limit that wasn't real.

Verified live: 8 Cohere calls, 3.1s apart, **zero Mistral, zero Gemini**. The
scan now costs nothing.

---

## 3. The logging spec, built

### 3.1 The funnel argument, applied twice

There is no shared fetch wrapper in `ml-portfolio` — 81 raw `fetch()` calls
across 58 files. §5 of the spec already makes the argument for the backend:

> Not at the twelve individual Gemini call sites, which is how half of them
> end up uninstrumented.

That reasoning holds identically on the frontend, so `trackedFetch` was built
first and call sites migrated to it. Same move on the backend: the four
`stream_*` functions in `llm.py` were renamed `_stream_*_raw` and re-exposed
under their original names wrapped in `instrument()`, so every existing caller
got recording for free.

### 3.2 The Space never holds a database key

`llm_calls` is written by a Vercel route the Space posts to with a shared
secret (`AIRAML_LOG_TOKEN`), not by giving the Space a Supabase key. The Space
was caught leaking a Gemini key in plaintext on 2026-09-05; a database key is
far worse. Gated to 404 when the secret is unset, so a deploy that forgets it
fails closed.

Verified end to end: 8 Cohere calls, each followed by
`POST /api/llm-log 200 OK`. A 200 there only happens after the insert
succeeds.

### 3.3 Stages 2, 3, 6, 8

- **Search** — debounced 800ms, which is not cosmetic: typing "segmentation"
  would emit twelve rows, eleven for prefixes nobody searched, and the early
  ones all look like zero-result searches. That corrupts the exact number the
  spec calls the most valuable row on the page.
- **Demos** — abandonment decided on *unmount*, not on pause. Pausing to read
  a caption is normal.
- **Exports** — 21 files build their own download, so instead of 21 edits:
  a capture-phase listener for rendered `<a download>`, plus a patched
  `URL.createObjectURL` for the programmatic saves on detached anchors that
  bubble nowhere.
- **Sessions** — `visibilitychange`, not `beforeunload`, which mobile
  browsers routinely never fire. `session_end` is a floor, not a measurement.

---

## 4. Three bugs of one shape

Every one of these is *the transport said fine, the thing that mattered did
not happen*.

1. **Reconciliation** returned HTTP 200 with an empty report while every judge
   call was rate-limited (found 2026-09-05).
2. **Text-to-SQL** reports failures as `{type:"error"}` inside a 200 SSE
   stream, so the transport sees success.
3. **Streaming generally** — `fetch` resolves at the response headers, so a
   25-second answer logged ~800ms and a stream that died mid-answer logged a
   clean success.

`trackedFetch` now takes `streaming: true` and wraps the body, recording when
the stream actually ends: finished → success with the real duration, broke →
error, cancelled → success with `completed: false` (mostly someone pressing
Stop; counting that as an error would inflate the error rate with people
changing their minds).

---

## 5. The lists were wrong, four times

This is the part of the session that matters, and it is not flattering.

**Fixed 1 of 5, said "fixed."** Found the in-band error in text-to-sql, fixed
it, shipped `27bc14f` claiming the class was handled. Four other streaming
tools had the identical shape. The user's follow-up question surfaced it, not
any check of mine.

**Batch A's list was chosen by eye.** Ten files picked from tool names. It
missed eleven callers — including every call that spends the paid Gemini
budget, which are the most worth recording on the site. Fixed by *deriving*
the list: grep the backend for modules importing the LLM client, read the
routes they expose, map those to frontend callers. That surfaced
`/ai-code-detect/judge` and `/siem-triage/judge`, which no amount of reading
tool names would have.

**The detection pattern was too narrow.** It required a literal
`ML_UNIFIED_API` inside the fetch call, so it missed every file aliasing the
backend as `API` — AutoML train, the whole pipeline builder, the site chatbot,
and **DriftRunner's actual drift-detection call**, while happily instrumenting
its two metadata loads.

**Then the transformer went too wide.** Running it over everything swept up
`KeepAlive`, which pings `/health` on a timer from every open tab. Logging
that as `run_success` would have made the number meaningless — the same
failure as `tool_open` counting uploads, which had been fixed two commits
earlier.

**Said "not deployed yet" without checking.** Vercel had already deployed it.

---

## 6. A verification that reported clean while not running

Three separate attempts to compare lint against a baseline printed a
reassuring `0 vs 0`:

1. `zsh` does not word-split unquoted `$FILES`, so eslint received one giant
   filename and matched nothing.
2. `eslint -f unix` is not installed in this project and emits nothing at all.
3. The `grep` pattern did not match the formatter's output either way.

**A broken check that reports "clean" is worse than no check**, because it
manufactures confidence. The fix was to prove the harness can fail: inject a
deliberate type error, confirm `tsc` reports exactly 1, then remove it.

That test caught a second real problem — the `git checkout` used to undo the
injection silently reverted `useFSAISuggest`'s instrumentation, which was
restored and re-verified.

---

## 7. What the user said

> *"you are making a lot of mistakes, not only today but everyday, this is
> unacceptable."*

Correct, and the errors were not unrelated: three of them were one habit —
**reporting a state instead of checking it.**

Written to memory as `feedback_status_claims_need_evidence`, four rules:

- Status words ("done", "fixed", "deployed", "passing") require a command in
  the same turn that shows it.
- Fix the **class**, not the instance: grep the whole codebase for the shape
  and report the count *before* fixing.
- Prove a check can fail before trusting a pass.
- A 404 / empty / silent response is ambiguous — disambiguate with a control.

Rule 4 earned its place immediately: `GET /api/llm-log` returning **405**,
matching a known-existing route, proved the route was deployed and its 404 was
the auth gate working rather than a missing file.

---

## 8. Files kept under the limit rather than pinned

Three files hit the 400-line rule during this work. None had its pin raised.

| File | Action | Result |
|---|---|---|
| `QueryResultPanel.tsx` | SSE reader loop → `sqlExplainStream.ts` | 420 → 375 |
| `useTextToImageRunner.ts` | option lists → `textToImageOptions.ts` | 413 → 398 |
| `Chatbot.tsx` | four SVG icons → `ChatbotIcons.tsx` | 429 → 390 |

The first one is the interesting case: that reader loop existed in **three
near-identical copies**, which is precisely why the same in-band error fix had
to be written three separate times. `LOGGING_SPEC.md` itself was trimmed to
exactly 400 twice rather than shipped over.

---

## 9. The clip, at last

Recorded on the rebuilt recorder: 11 steps, 159s, 10.3 MB. **All 25
walkthrough clips are now on the rebuilt recorder.**

Steps 10 and 11 had to be rewritten first. They were written around a Mistral
false positive and spent a third of the narration on the yellow "Unconfirmed"
badge. With Cohere judging, both findings come back confirmed, the badge never
renders, and `expect: "Unconfirmed"` would have aborted the recorder — the
same guard that stopped three attempts yesterday, firing for the opposite
reason.

The rewrite describes the *mechanism*, not this run's outcome. A script that
names what the judge returned goes stale the moment the judge improves, which
is exactly what happened. New guards are on values the model does not choose:
the report header, and verbatim invoice PDF text.

**Audited frame by frame**, not by exit code — the lesson from the audit that
found 7 of 11 earlier clips wrong. Step 9 shows both rows at 76% and 85%; step
10 spotlights one row while explaining the double-check; step 11 lands exactly
on the side-by-side passages; the closing card points at the live site.

---

## 10. Still open

- ~~**`security_log` (§5b)**~~ — built after this list was written; see §11.
- **Search queries as a salted hash** — decided, not implemented. Length alone
  cannot count repeat zero-result searches. (Note the contrast with §11.3: for
  a SEARCH box a hash is the privacy-preserving upgrade; for a PASSWORD box
  even the length is too much. The difference is what an attacker can do with
  the field.)
- **`demo_abandon`** — reasoned about, never exercised.
- **Site chatbot still defaults to Gemini** — Cohere is not wired into
  `/api/chat` at all.
- **Returning visitors keep their old provider** — persisted in localStorage,
  so the Cohere default reaches new visitors only.
- **`verify-recon-warning.mjs`** — still untracked in `ml-portfolio`.
- **Two naming conventions in `events`** — `tool_open`/`tool_close` carry
  display names ("Data Drift Detection"), run events carry slugs ("drift").
  Pre-existing; renaming would orphan existing rows.

---

## 11. §5b built — the security log

Written after §10 listed it as the only unbuilt piece, when the user asked the
fair question: *"then what are you waiting for?"*

**What it records:** filename, extension, size, mime, a SHA-256 of the bytes,
prompt length, session and run id, country. **Never the file.** 30-day
retention, purged at 03:41 — after the analytics purge at 03:17, and far
shorter than the 14 months analytics get, because these fields are more
sensitive.

### 11.1 One listener, because uploads have two shapes

Tools send files two different ways: **FormData** for the ML endpoints,
**base64 inside a JSON body** for most of the vision ones. Hooking the
transport would have caught the first and silently missed the second — the
same class of miss as Part 278 §5's narrow detection pattern, which is why it
was avoided this time rather than discovered afterwards.

So the hook is a capture-phase `change` listener on every `input[type=file]`.
Every tool has one, whatever it does with the file next. The tool name comes
from the URL, so a tool added later is covered the day it ships.

It logs on **select**, not on send. A file chosen and then abandoned still
went into the page, and for a log whose question is "was anything malicious
put in here", that is the honest boundary.

### 11.2 Two independent locks on readability

§5b requires the table to be unreadable by anything the site exposes. That is
enforced twice, and the two do not back each other up — they fail separately:

1. **RLS on, no policies.** The anon key the browser holds can read nothing.
   The database refuses.
2. **No GET handler.** `/api/security-log` exports `POST` only. There is no
   URL that returns this data because none was written.

Lock 2 is one line someone could add in six months without knowing why it was
missing; Lock 1 would still refuse. Loosen Lock 1 and there is still no URL to
ask through.

The `sha256` column takes a 64-character hex digest or null and nothing else,
so it cannot quietly become a place content is smuggled into.

### 11.3 The password tool, and why nothing changes there

The user asked whether the Password Strength checker should be tracked in the
database after all, and asked for the recommendation to be researched rather
than asserted.

**The answer is no, and the current design is already the recommended one.**
The consensus is to do all password analysis in the browser and transmit
nothing — not the password, not a hash, not the length. The tool already does
the harder half correctly: for the breach check it computes SHA-1 locally,
sends only the first 5 hex characters to the API and matches the suffix in the
browser. That is k-anonymity — the API learns that someone checked a password
sharing a 5-character prefix with roughly 800 others, and never learns which.

**Length is the specific thing not to log.** It is the most useful single clue
for guessing a password, and recording it buys nothing the tool does not
already do client-side.

One clarification worth writing down, because "nothing is logged" is not
literally true: `tool_open` / `tool_close` still fire for that page. What is
excluded is anything about the password. Usage is ours to measure; the secret
is not. Confirmed too that the pwnedpasswords call is deliberately NOT wrapped
in `trackedFetch`, so a breach check creates no row.

The exclusion is enforced in **both** halves — the client helper and the
server route — because a promise that depends on every caller remembering is
not a promise.

### 11.4 A test that proved nothing, and the control that fixed it

The first exclusion test loaded `/tools/password-audit`, tried to upload a
file, and reported **0 rows**. That result was worthless: the page has no file
input at all, so there was nothing to block.

Redone properly — inject a real `File` and a real `change` event on the
password page (**0 rows**), then the identical injection on
`yara-file-scanner` (**1 row**). The second half is the control that makes the
first half mean something.

The browser-computed SHA-256 was also checked against `shasum -a 256` on the
same file: identical digest.

This is Part 278 §6's rule applied on purpose rather than after being caught:
**prove the check can fail before trusting a pass.**

### 11.5 Privacy page

Storing filenames for 30 days is a real disclosure, so §7 obliged an update in
the same commit. It now says what is kept, for how long, that the file itself
is discarded, why a filename is kept at all, and that the Password checker is
excluded entirely.

**Commits:** `020d7ec` (ML-Unified — SQL + spec), `8f38298` (ml-portfolio —
client, sink, privacy).

**Awaiting one action:** `supabase/security_log.sql` run once in the SQL
editor. Until then the client posts to a table that does not exist and fails
silently — nothing breaks, nothing is recorded.

**`LOGGING_SPEC.md` is now fully implemented.** What remains is in §10 and is
all decision, not construction: search queries as a salted hash, whether to
store content at all, and the two naming conventions already in `events`.
