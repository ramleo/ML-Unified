# Session — 2026-09-07 — The clips that refused to record

Continues from Part 279. Started as "re-record the walkthrough clips that
predate the title/closing cards" and turned into two production bugs, because
the recorder refuses to narrate something that is not on screen.

---
## 1. Which clips, and how that was established

The user asked whether start/end cards were still pending on the handbook
clips. They were — for exactly five of the twenty-five.

Title card shipped `d4dfa35` (2026-09-04 14:05), closing card `2c6cd16`
(16:52). Every clip recorded before those has neither. Five qualify:
`multimodal-rag` (Sep 1), `text-to-sql` and `optuna` (Sep 2),
`document-intelligence` and `prompt-injection-playground` (Sep 3).

**Timestamps were the hypothesis, not the evidence.** Confirmed by pulling
first and last frames with ffmpeg: `depth-parallax` (recorded after) opens on
"GUIDED WALKTHROUGH — Depth Parallax"; `optuna` opens straight into the tool
UI and ends on its last narration step. Cheap to check, and it would have been
embarrassing to re-record five clips on a filesystem-date guess.

---
## 2. The audit that matters is the frame, not the exit code

Recording setup: production build against both Spaces, served on :3300,
`DEMO_BASE_URL` pointed at it. Playwright drives real Chrome (headless renders
WebGL blank on this machine).

Every clip re-recorded here was checked on four things, because a clean exit
proves only that the script ran:

1. opens on the title card,
2. closes on the end card,
3. **the tool actually ran** — real values on screen, not an empty or errored
   panel,
4. **the narration matches the picture** at the moment it is spoken.

Point 4 is the one an assertion cannot cover, and it is how the earlier audit
found 7 of 11 clips wrong.

---
## 3. optuna — clean

Re-recorded, 144s, both cards present. The tool genuinely ran: tuned params
(`n_estimators` 305, `max_depth` 4) and real metrics. Narration checked at two
points — step 4 says "thirty trials" with the trials slider reading 30 and
spotlit; step 9 warns about the CV score with the winner-metrics panel
spotlit. Committed `1a62f4c`.

---
## 4. prompt-injection-playground — the guard earned its keep

The re-record aborted:

> `step 5 expected "High risk" on screen and it is not there — the recording
> would narrate something that did not happen`

Nothing was written; the old clip stayed intact.

### 4.1 Not a recording problem

Calling `/prompt-injection/check` with the demo's own payload:

```json
{ "heuristic_hits": [ { "category": "indirect", "matched_text": "AI: ignore" } ],
  "llm_verdict": null,
  "overall_risk": "medium" }
```

Three identical calls — not a flake. `llm_verdict: null`, so only the pattern
check contributed and the verdict fell to medium. The narration would have
said "High risk" over a screen showing medium.

The Space log gave the cause, rather than leaving it to inference:

```
POST https://api.mistral.ai/v1/chat/completions "HTTP/1.1 429 Too Many Requests"
llm.complete() failed for provider=mistral: Error code: 429 - 'Rate limit exceeded'
INFO: "POST /prompt-injection/check HTTP/1.1" 200 OK
```

Three retries, all 429, and the endpoint answers **200 OK** anyway. Today's
recurring shape: a 200 that is not a success.

### 4.2 What was actually wrong

The judge was **Mistral alone, no fallback** — the one provider whose free tier
is best-effort with no reserved capacity (Mistral support confirmed this on
2026-09-06; see [[project_llm_provider_status]]). Whenever Mistral is busy, a
tool advertising *two independent checks* silently ran one.

Worse than the medium verdict was the clean case. `_combine_verdict` could not
distinguish "the judge read this and found nothing" from "the judge never
answered", so a clean result reported:

> "No injection pattern matched and the LLM judge found no manipulation attempt."

That sentence asserts the judge cleared text it had never seen.

### 4.3 The fix

- **Judge cascade** — Cohere (free, reliable) then Mistral. **Gemini
  deliberately excluded**: it is the only paid key and this endpoint is public
  and unauthenticated, so including it would let anyone spend money by pasting
  text into a box.
- **`run_judge` returns `(verdict, judge_ran)`**, and `judge_ran` rides on the
  response so the UI can tell the two cases apart.
- **`_combine_verdict` says so** rather than reporting a confident low on half
  the evidence.

Unit-tested before deploying, including the exact failing case:

| Situation | Before | After |
|---|---|---|
| weak hit + judge unreachable | `medium`, silent | `medium` + "pattern check alone" |
| no hit + judge unreachable | `low`, "judge found no manipulation" — **false** | `low` + "treat as inconclusive" |
| no hit + judge cleared it | `low` | unchanged |

**The frontend had its own lie.** The null-verdict branch read *"LLM judge
unavailable (no server key configured)"* — a specific cause the response cannot
support, and simply wrong here: the key was fine, the provider was rate-limiting.
Same fault as Part 278 §12's "origin-checked" comment. It now states what
happened, with a warning chip on the verdict itself rather than buried in the
second column.

Backend `cd7f985` (uploaded to `wram1708/ml-unified`), frontend `f6da13c`.
Verified live after the rebuild: `risk=high, judge_ran=True,
verdict=(True,'high')` — Cohere answering where Mistral 429'd.

### 4.4 Then it recorded

12/12 steps, 156s, both cards. Step 5 shows High risk with both panels
populated and the summary line naming the judge as the driver. Step 11 —
the benign control — shows Low risk, with the judge explaining it as "a routine
request for an updated calendar invite".

That last one is the check worth having: the benign sample contains "please
ignore my previous email", bait a naive detector flags. A detector that simply
says "injection" to everything would pass step 5 and fail step 11. Committed
`26c2243`.

---
## 5. document-intelligence — stale narration, and a bill

Aborted at step 7: `expected "need review" on screen`. Steps 3-6 passed, so
extraction was fine, including the exact date and total the demo asserts.

Calling `/document/analyze` with the same sample and parsing the SSE:

- all four stages ran, **Validate included**
- **13 fields**, while step 7 narrates *"Fifteen fields in all, and only nine
  of them…"*
- **zero flagged** — every field returns `{"status": "ok"}`, so the
  "N need review" text never renders and step 8's "Flagged" badge does not
  exist

Validation is not broken; it finds nothing wrong. The clip describes an older
run. Unlike §4, there is no bug here — the script is stale.

### 5.1 The thing that was not on the list

The same stream reports:

```
{"step": "analyze", "provider": "gemini (cached)"}
```

`_llm.py`'s `_CASCADE_ORDER` is **mistral → gemini → cohere → cerebras**. With
Mistral 429ing, every document analysis falls through to **Gemini, the only
paid key, while free Cohere sits one position later** — on a public,
unauthenticated endpoint.

Same root cause as §4, opposite symptom: the injection judge degraded quietly,
this one **bills** quietly. Found only because a clip refused to record.

---
## 6. Open at the end of this part

- **Cascade order in `_llm.py`** — put Cohere ahead of Gemini so the paid key
  is genuinely last. Recommended, not yet done: it is a provider-order change.
- **document-intelligence narration** — needs rewriting to 13 fields and to
  whatever validation actually reports, before that clip can be recorded.
- **Three clips still without cards** — `document-intelligence` (blocked on the
  above), `multimodal-rag`, `text-to-sql`. The last is deliberately left until
  end: its provider plumbing changed today (Part 279 §11.4).
- `_generate.py` is 366 lines, over the 350 threshold; the split was skipped by
  explicit instruction and is due next time that file is touched.

---

Continued in **Part 281** — the clip backlog closed, the document tool's
provider chain repaired, and the frontend's first automated tests:
`Session_2026-09-12_TheTestsThatFoundSixBrokenPages_Part281.md`
