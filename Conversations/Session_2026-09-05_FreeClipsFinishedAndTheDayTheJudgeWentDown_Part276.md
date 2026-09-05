# Session 2026-09-05 — Part 276

## Free clips finished, and the day the judge went down

**24 commits.** 15 in `ml-portfolio`, 9 in `ML-Unified`.
**All 19 free walkthrough clips are now on the rebuilt recorder.**
**Six shipped bugs found, four of them user-visible.**
One clip still unrecorded, and the reason turned into most of the day.

---

## 1. What the day was meant to be

Continue Part 275's work: re-record the remaining free clips one at a time,
each on the rebuilt recorder with title card, closing card, aligned
narration and correctly timed actions. Fourteen were outstanding.

All fourteen are done. The queue that began the session is empty.

| Clip | Commit | Outcome |
|---|---|---|
| shap | `8c06909` | No changes — first clip whose script was already true |
| preprocessing | `f69da15` | UI bug fixed |
| feature-engineering | `2798061` | Three corrections |
| feature-selection | `56ef5f6` | Two false claims |
| pipeline-builder | `d60762f` | UI bug fixed |
| pipeline-cinema | `bed9be5` | One claim narrowed |
| email-auth-checker | `85e6ee7` | No changes |
| tls-security-headers-scanner | `36d475c` | No changes |
| dns-tunneling-detector | `81ef2d7` | Layout fix |
| malicious-package-scanner | `458628b` | UI bug fixed |
| password-audit | `6dc464c` | No changes |
| phishing-email-classifier | `47d4d6c` | No changes |
| yara-file-scanner | `796fae3` | No changes |
| realtime-analytics | `38e9d0e` | No changes — filmed against live Vercel |

Five needed nothing. Notably those were the ones where the claims were
checked against something outside the repo — live DNS, live HTTP headers,
HIBP, the raw bytes of a file — rather than against the code that produced
them.

---

## 2. Four shipped UI bugs, found by narrating tools out loud

Each is a case where the clip said something true and the tool did not back
it up. None would have been found by reading code.

**Preprocessing — a card with no "before".** The results summary shows four
before→after cards. Three carried real numbers; Missing had `"—"` hardcoded,
in both the panel and the modal copy, with `analyzed.total_missing` already
in scope in each. The panel promised a comparison and delivered three
quarters of one. Now reads 29 → 0.

**Pipeline Builder — the mode card lied.** Express Mode said *"Configure all
7 stages at once, then run the full pipeline."* It runs four. Optuna, SHAP
and Ensemble render LOCKED until those four finish. Confirmed by running it
and reading the grid before and after: four READY / three LOCKED, then four
DONE / three READY. The narration said the same wrong thing, so caption and
UI agreed with each other and both were wrong.

**Package Scanner — an honesty claim that wasn't on screen.** Step 5 said the
typosquat list "is not exhaustive and the tool says so". The tool did not say
so; "non-exhaustive" lived in a source comment. Since the narration's own
argument is that the admission is the point, the fix went into the tool
rather than the script.

**DNS Tunneling — the caption covered its own subject.** The single-hostname
verdict is the last element on the page, so the fixed caption sat on top of
the line explaining that both thresholds were crossed — while the narration
described it. `pb-12` → `pb-32`.

---

## 3. Five false claims in narration

- **feature-engineering** promised the result "goes straight on to feature
  selection". It doesn't — the panel offers Download CSV and nothing else.
- **feature-engineering** placed the date and frequency-encoding panels "on
  the left"; only interactions and ratios are in the sidebar.
- **feature-selection** said "fourteen methods". `fsTabs` defines sixteen.
  This was in the *blurb*, so the wrong number was the first thing on the
  title card.
- **feature-selection** called Top-K "a scoring method" one step after
  explaining that filters and scores are different groups. Top-K is a filter.
- **pipeline-cinema** said a failed stage "still plays with its scripted
  lines". The catch waits 2 seconds and moves on.

**The pattern worth keeping:** every one of these passed its `expect`. An
assertion catches a missing string; it cannot catch a sentence that is wrong
about a string that is present.

---

## 4. Two anchoring faults

**Off-screen numbers.** feature-engineering steps 7 and 8 both pointed at
`fe-results`, the whole results view — taller than the viewport, so the ring
fell outside the frame and the page sat scrolled onto the charts while the
caption read "ten columns went in and thirty came out". Three anchors added
so each step rings what it describes.

**Caption collision, twice.** A result panel pinned to the page bottom sits
under the fixed caption — feature-engineering's download card and DNS
tunneling's verdict. Two different fixes: move the anchor to an element the
caption can't reach, or give the page bottom padding.

**A grep lesson, learned three times.** `data-wt="eauth-dns"`,
`ra-newest-export` and `recon-chip-0` all appeared missing to a literal grep.
All three are built as template literals or passed through a component prop.
I announced "the anchor doesn't exist" more than once before checking.

---

## 5. CI: two failures, one hiding the other

**`73362d4` — No space left on device.** The install list said why:
`nvidia-cusparselt-cu13`, `nvidia-nccl-cu13`, `triton`, `cuda-toolkit`.
Nothing pins torch; `sam2` and `sentence-transformers` both need it, so pip
took the default PyPI wheel — the CUDA build — and put several GB of GPU
runtime on a runner with no GPU, for tests that never ask for one. Fixed by
installing torch and torchvision from the CPU index first, plus dropping
~25 GB of unused runner toolchains.

**`fbf670d` — a deploy job to a service that no longer exists.** Fixing the
tests revealed it: `needs: test`, so while the disk failure stood, deploy was
skipped. The job curled three Render hooks;
`ml-unified.onrender.com` does not answer at all. It had passed on Sep 3.

Moving deploys into CI was considered and rejected: rule 5 batches changes
because each upload costs a 2–5 minute rebuild serving 500s, and a job firing
on every push cannot batch.

**The lesson:** a broken thing hid behind another broken thing. Had the tests
stayed red longer, the dead deploy path would have stayed invisible.

---

## 6. The reconciliation clip, and a day of being wrong in public

The last free clip is done; the first *paid* clip is not. What happened
instead is the most useful part of the session.

### 6.1 The recorder refused to lie

Three recording attempts, all aborted at step 9:

> step 9 expected "% match" on screen and it is not there — the recording
> would narrate something that did not happen

The guard built in Part 274 did exactly its job.

### 6.2 A silent failure worth more than the clip

Mistral returned 429 on every judge call. The route still returned **200 OK
with an empty report**, and the UI printed:

> No discrepancies found — 6 contract/invoice passage pairs checked

`judge_fn` returns `None` when a call is rate-limited, and
`if not (verdict and verdict["contradicts"])` put that in the same branch as
a judge that looked and cleared the pair. So a provider outage rendered as a
confident all-clear **on a tool whose entire job is catching a discrepancy
before you pay an invoice.**

Fixed in both paths (`1603c9a`, `7b5d7d3`): failures counted separately and
returned as `judge_failures`, the false all-clear suppressed entirely rather
than shown alongside a warning.

**Only the recorder's `expect` caught this.** A person using the tool would
have seen a clean report and believed it.

### 6.3 Verifying a failure path without paying for it

Claiming the fix "compiles and deploys" wasn't good enough, and the user
asked how it could actually be verified. Answer: let the page run for real
and intercept the one paid response.

Playwright `page.route()` on `/rag/reconciliation`, real ingest (free, local
embeddings), synthetic reply. Both branches rendered on the live deployment,
**zero API calls** — and `recon-clean` was confirmed absent from the DOM, not
merely hidden.

### 6.4 Being wrong, in order

The diagnosis took far longer than it should have, and the record of how is
worth more than the conclusion:

1. **"It's our burst pacing."** Mistral allows 1.00 req/s and the code fired
   six calls with no gap. True, and a real bug — fixed in `a0a3fea`. Not the
   cause: the first call after 42 minutes of silence was also refused.
2. **"It's the Space's shared IP."** Plausible, stated with appropriate
   hedging, and **wrong** — Gemini succeeded from that same IP an hour later.
3. **"Both providers are refusing, so it's environmental."** Also wrong.
   Mistral was refusing; Gemini was failing because its key had been burnt.

**Why it took so long:** [`llm.py`](../services/ml-api/routers/rag/llm.py)
logged only the status code on a Gemini error and threw away the body. A 429
from Google can mean the per-minute quota, the per-day quota, no billing, or
an API never enabled — **and the body says which**. Hours were spent
inferring something Google was stating plainly. Fixed in `172459b`.

The user's instruction — *"check the code properly"* — was the correct
response to me theorising, and it was right both times they said it.

### 6.5 What actually fixed it

A Gemini fallback (`3b74472`), plus the user rotating the Gemini key. The
log tells the story cleanly:

```
15:09:07  mistral ×3 (SDK retries)
15:09:09  judge: mistral failed, falling back to gemini
15:09:11  gemini ✓ … and gemini for everything after
```

Both planted discrepancies caught — Net 30 vs Net 15 at 76% match, $145/hr
vs $165/hr at 85% — and both decoys (4% fuel surcharge, 1% monthly interest)
correctly ignored.

**Still open:** `judge` and `confirm` latch separately, so Mistral is retried
twice per scan — about six wasted calls and four seconds. And the Mistral key
is still dead.

---

## 7. A live key in the logs

Found while reading Space logs for the 429: **the Gemini API key in
plaintext**, repeatedly.

Nothing was wrong with how it was stored — it is a Space secret read from the
environment. Google's API is what exposes it: Gemini takes its key as a URL
query parameter, and httpx logs whole request URLs at INFO.

**Two paths leaked it, not one.** httpx's own request line, and our WARNING
in `llm.complete()`, which formats httpx's exception — and the exception text
carries the URL too. Silencing httpx would have closed only the first, which
is the trap.

`e5f47e7` installs a redaction filter on the root logger: closes both paths,
covers all twelve Gemini call sites, and covers the thirteenth. Verified
against both real log lines. Header-authenticated providers were never
affected.

The user rotated the key. The local copy of the log was deleted, and `/tmp`
scanned for other copies.

**`6120f0f`** — a follow-up: the import had been placed below
`logging.basicConfig` to make the ordering obvious, which ruff's E402
forbids. Only the *call* needs to be there. Also a lesson in linting with the
version CI pins: local ruff 0.16.6 reported four errors that CI's 0.9.10
never checks.

---

## 8. Two questions worth recording

**"What framework and vector DB are we using?"** — Native FastAPI, no
orchestration framework. `langchain-core` sits in `requirements-base.txt` and
**nothing imports it**; the RAG pipeline is hand-written. ChromaDB with a
persistent client, `all-MiniLM-L6-v2` for dense retrieval, `rank-bm25` for
sparse, RRF for fusion. `jinaai/jina-embeddings-v3` for photo search, a
separate Chroma collection for optional Cohere Embed v4 vision. The user
chose to leave the unused `langchain-core` line in place for now.

**"Why is the key in plaintext if I made it an environment variable?"** —
Answered in §7. The storage was never the problem.

---

## 9. The logging specification

The session's last substantial work, and it came directly from §6: the day
was slow because **nothing was written down anywhere durable.** Space logs
are a buffer wiped by every restart; the Space disk is ephemeral. The two
facts that mattered — key rotated ~14:50, first success 15:09:11 — both
existed and were never readable together.

**`a434c4c`** — `ML-Unified/LOGGING_SPEC.md`, plus a memory entry so it
survives being forgotten.

Eight journey stages, ~25 event types. The plumbing turned out to be sound
and the vocabulary nearly empty: 51 of 52 tool pages track something,
`page_view` fires from 61 files, and only **five event types are ever
emitted** — with `error` having one call site in the entire codebase.

**Decided:** a `security_log` table, service-role only, holding filename,
extension, size, mime, sha256 and prompt length for **30 days**. Filenames
stored, on the reasoning that a payslip's *name* reveals a name while its
*contents* reveal a salary, an employer, an address and a tax number — a
different order of exposure. **The password tool is excluded entirely**; its
promise that the password never leaves the browser is currently true.

**Left open, with both sides written down:** storing content itself.
Deferring costs nothing, because the sha256 recorded from day one lets a
later sample match an earlier event.

**Recorded as an obligation:** the privacy page states its analytics claims
are *"the exact insert in api/track/route.ts"* and that it is wrong if those
change. Any logging change ships with a privacy page change.

---

## 10. Lessons

1. **An `expect` catches a missing string, not a wrong sentence.** Five false
   claims all passed their assertions.
2. **Read the error body before theorising.** A day of inference over
   something the provider was stating plainly.
3. **Check template literals before saying an anchor is missing.** Three
   times.
4. **Lint with the version CI pins.** A newer linter manufactures work.
5. **A broken thing can hide behind another broken thing.** The dead deploy
   job was invisible while the tests were red.
6. **Verify a failure path by faking the response, not by buying one.**
7. **"Be careful with API calls" means wait for a yes**, not explain the cost
   and proceed in the same breath. I did the latter and was rightly called on
   it.
8. **The clip that could not be recorded was the most valuable one.** Four
   shipped bugs, a leaked credential and a logging specification came out of
   a video that still does not exist.

---

## 11. Still open

- **contract-invoice-reconciliation clip** — unrecorded. The tool works now.
- **Mistral key** — dead; the Gemini fallback is carrying it.
- **Double-latch** — judge and confirm retry Mistral separately, ~6 wasted
  calls per scan.
- **Logging spec** — agreed, nothing built. §9 has the order.
- **Five paid clips** — document-intelligence, multimodal-rag, optuna,
  prompt-injection-playground, text-to-sql.
- **`verify-recon-warning.mjs`** — untracked in `ml-portfolio`; keep as a
  test or delete.
- **Three `RENDER_*` secrets** — now unused.
