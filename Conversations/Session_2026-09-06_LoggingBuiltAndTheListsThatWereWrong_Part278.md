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

Opened on the handbook with one clip left to record; ended with the whole
logging spec built. Every step was one ask at a time, each answer checked.

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

No shared fetch wrapper existed — 81 raw `fetch()` calls across 58 files. §5
already makes the argument for the backend — *"not at the twelve individual
Gemini call sites, which is how half of them end up uninstrumented"* — and it
holds identically on the frontend, so `trackedFetch` was built first and call
sites migrated to it. Same move on the backend: the four `stream_*` functions
in `llm.py` were renamed `_stream_*_raw` and re-exposed under their original
names wrapped in `instrument()`, so every caller got recording for free.

### 3.2 The Space never holds a database key

`llm_calls` is written by a Vercel route the Space posts to with a shared
secret (`AIRAML_LOG_TOKEN`), not by putting a Supabase key on the Space — its
logs were caught leaking a Gemini key on 2026-09-05, and a database key is far
worse. 404s when the secret is unset, so a deploy that forgets it fails closed.

Verified end to end: 8 Cohere calls, each followed by `POST /api/llm-log
200 OK` — and a 200 there only happens after the insert succeeds.

### 3.3 Stages 2, 3, 6, 8

- **Search** — debounced 800ms, not cosmetic: typing "segmentation" would emit
  twelve rows, eleven for prefixes nobody searched, and the early ones all look
  like zero-result searches — corrupting the exact number the spec calls the
  most valuable row on the page.
- **Demos** — abandonment decided on *unmount*, not pause. Pausing to read a
  caption is normal.
- **Exports** — 21 files build their own download, so instead of 21 edits: a
  listener for rendered `<a download>` plus a patched `URL.createObjectURL`
  for programmatic saves on detached anchors that bubble nowhere.
- **Sessions** — `visibilitychange`, not `beforeunload`, which mobile browsers
  routinely never fire. `session_end` is a floor, not a measurement.

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
the stream ends: finished → success with the real duration, broke → error,
cancelled → success with `completed: false` (mostly someone pressing Stop, and
counting that as an error would inflate the rate with changed minds).

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

**Then the transformer went too wide.** It swept up `KeepAlive`, which pings
`/health` on a timer from every open tab; logging that as `run_success` would
have made the number meaningless — the same failure as `tool_open` counting
uploads, fixed two commits earlier.

**Said "not deployed yet" without checking.** Vercel had already deployed it.

---

## 6. A verification that reported clean while not running

Three attempts to compare lint against a baseline printed a reassuring
`0 vs 0`: `zsh` does not word-split unquoted `$FILES` (eslint got one giant
filename), `eslint -f unix` is not installed here and emits nothing, and the
`grep` pattern matched neither output.

**A broken check that reports "clean" is worse than no check** — it
manufactures confidence. Fixed by proving the harness can fail: inject a type
error, confirm `tsc` reports exactly 1, remove it.

That caught a second problem — the `git checkout` undoing the injection had
silently reverted `useFSAISuggest`'s instrumentation, restored and re-verified.

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

11 steps, 159s, 10.3 MB. **All 25 walkthrough clips are now on the rebuilt
recorder.**

Steps 10 and 11 were rewritten first. Built around a Mistral false positive,
they spent a third of the narration on the yellow "Unconfirmed" badge — and
with Cohere judging both findings come back confirmed, the badge never
renders, and `expect: "Unconfirmed"` would have aborted the recorder. The same
guard that stopped three attempts yesterday, firing for the opposite reason.

The rewrite describes the *mechanism*, not this run's outcome: a script naming
what the judge returned goes stale the moment the judge improves, which is
precisely what happened. New guards sit on values the model does not choose —
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

**Records:** filename, ext, size, mime, a SHA-256 of the bytes, prompt length,
session/run id, country. **Never the file.** 30-day retention, purged at 03:41
— after the analytics purge at 03:17, and far shorter than analytics' 14
months because these fields are more sensitive.

### 11.1 One listener, because uploads have two shapes

Tools send files as **FormData** (ML endpoints) *and* as **base64 in JSON**
(most vision ones). Hooking the transport would have caught the first and
silently missed the second — §5's narrow-pattern miss, avoided this time
rather than discovered afterwards.

So: a capture-phase `change` listener on every `input[type=file]`. Every tool
has one whatever it does next, and the tool name comes from the URL, so a tool
added later is covered the day it ships.

It logs on **select**, not send. A file chosen then abandoned still went into
the page, and for "was anything malicious put in here" that is the honest
boundary.

### 11.2 Two independent locks on readability

§5b requires the table to be unreadable by anything the site exposes, enforced
twice — and the two fail separately rather than backing each other up:
**RLS on with no policies** (the browser's anon key reads nothing; the database
refuses) and **no GET handler** (there is no URL that returns this data
because none was written).

Lock 2 is one line someone could add in six months without knowing why it was
missing; Lock 1 still refuses. Loosen Lock 1 and there is still no URL to ask
through.

### 11.3 The password tool, and why nothing changes there

Asked whether the Password checker should be tracked after all, with the
recommendation researched rather than asserted.

**No — the current design is already the recommended one.** The consensus is
to analyse in the browser and transmit nothing: not the password, not a hash,
not the length. The tool already does the harder half — for the breach check
it computes SHA-1 locally and sends only the first 5 hex characters, matching
the suffix in the browser. That is k-anonymity: the API learns someone checked
a password sharing a prefix with ~800 others, never which.

**Length is the specific thing not to log** — the single most useful clue for
guessing a password, and it buys nothing the tool does not already do
client-side.

Worth recording because "nothing is logged" is not literally true:
`tool_open`/`tool_close` still fire there. Only the password is excluded —
usage is ours to measure, the secret is not. The pwnedpasswords call is also
deliberately not wrapped in `trackedFetch`, so a breach check creates no row.

Enforced in **both** halves, client and server: a promise that depends on
every caller remembering is not a promise.

### 11.4 A test that proved nothing, and the control that fixed it

The first exclusion test loaded `/tools/password-audit`, tried to upload, and
reported **0 rows** — worthless, because that page has no file input at all.

Redone: inject a real `File` and `change` event on the password page
(**0 rows**), then the identical injection on `yara-file-scanner` (**1 row**).
The second half is what makes the first mean anything. The browser-computed
SHA-256 also matched `shasum -a 256` exactly.

§6's rule applied on purpose rather than after being caught: **prove the check
can fail before trusting a pass.**

### 11.5 Privacy page

Filenames kept for 30 days is a real disclosure, so §7 obliged an update in
the same commit: what is kept, for how long, that the file itself is
discarded, why a filename is kept at all, and that the Password checker is
excluded entirely.

**Commits:** `020d7ec` (ML-Unified — SQL + spec), `8f38298` (ml-portfolio —
client, sink, privacy).

**Awaiting one action:** `supabase/security_log.sql` run once in the SQL
editor. Until then the client posts to a table that does not exist and fails
silently — nothing breaks, nothing is recorded.

**`LOGGING_SPEC.md` is now fully implemented.** What remains is §10, all
decision rather than construction.

---

## 12. A comment that claimed a protection that did not exist

The user read §11.2's "two locks" and asked the question that mattered:

> *"you said 'that file contains only code for writing', isn't it risky, what
> if someone unauthorized writes something harmful?"*

Checking it produced something worse than the risk. The route's header said it
was **"origin-checked"**. There was no origin check anywhere in the file; the
only real protection was field clamping.

**A comment asserting a protection that does not exist is worse than no
comment** — the next reader stops looking. §5's habit in a new costume:
describing a state rather than checking it, written into source where it
outlives the conversation.

### 12.1 Exposure, and what was added

A public POST with no origin check, no rate limit, no body cap. An attacker
could not read the table, reach another, run SQL, or store anything large —
every field is clamped, `sha256` takes 64 hex chars or null. They *could*
insert junk rows, and **a security log you can flood is one you cannot
trust**: a real event can be buried under ten thousand fabricated ones.

Added: an **Origin allow-list** (stops another site POSTing from a visitor's
browser; does *not* stop curl, which can send any Origin — no header check
can), a **60/min per-IP limit** (best-effort; serverless instances share no
memory), and a **4KB body cap**. Residual risk is stated in the file, with the
real fix if ever needed: a server-minted signed token, not a bigger header
check.

### 12.2 The ordering bug the test found

The guards were placed *after* the Supabase env check. Locally, where that key
is empty, **every request returned the same 500** and not one guard was
reached — the test could not tell blocked from allowed. Guards run first now,
which is also right on the merits: a forged request should be refused on its
own terms, not masked by a 500 about our own configuration.

### 12.3 Verified separately, with a control

| Case | Result |
|---|---|
| no Origin | 403 |
| Origin: evil.example | 403 |
| 5KB body | 413 |
| good Origin | 500 — guards passed, local Supabase key empty |
| 65th rapid POST | 429 |
| real browser upload | 500, correct payload |

The fourth row is the control: without it, five rejections prove only that the
route rejects everything.

One more catch: the browser run first returned **429**, which looked like a
bug and was not — the rate-limit test seconds earlier had eaten the same
bucket, since localhost sends no `x-forwarded-for` and both fell into
`unknown`. Restarting cleared it.

**Commit:** `c91dbd0`.
