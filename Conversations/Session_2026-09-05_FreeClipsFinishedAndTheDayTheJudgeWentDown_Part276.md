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

---

## 12. Why the Mistral key was dead — the answer, at last

Written after §11, same day, when the user asked the obvious follow-up:
**"check why is mistral key dead?"** Yesterday the answer was a shrug and a
fallback. This time the logs the day had already taught us to read gave a
definite answer in about fifteen minutes and without spending a paid call.

### 12.1 What the log said

The Space log buffer still held everything since the 14:59 startup:

```
15:08:00  POST api.mistral.ai/v1/chat/completions  429
15:08:00  429   (SDK retry)
15:08:01  429   (SDK retry)
llm.complete() failed for provider=mistral:
  Error code: 429 - {'object':'error','message':'Rate limit exceeded',
                     'type':'rate_limited','code':'1300'}
```

Twelve Mistral calls since startup. **Twelve 429s. Zero 200s, ever.**

The decisive detail was the timestamp, not the status. `15:08:00` was the
first Mistral request in the nine minutes since the Space booted — cold, no
burst, an empty rate window. It was refused anyway. **A per-second limit
cannot be exceeded by a single cold request.** Yesterday's `_pace()` fix was
a real bug fixed for a real reason, but it was never this cause.

And 429, not 401, meant the credential was being *authenticated* and then
*refused*. The key was never "dead" in the sense everyone assumes.

### 12.2 Eliminating everything, one screenshot at a time

The user supplied console screenshots on request; each one closed a door.

| Hypothesis | Evidence | Verdict |
|---|---|---|
| Our burst pacing | Cold call, 9 min idle | ✗ |
| Per-second / TPM ceiling | Well under 1.00 req/s and 20,000 TPM | ✗ |
| Monthly token budget | Limits page has no monthly cap for chat models — only audio has one, and it reads `-` | **✗ — WRONG, see §14** |
| Model alias mismatch | See 12.3 | ✗ |
| Invalid / revoked key | Would be 401 | ✗ |
| Expired key | Console: active, **never** expires | ✗ |
| Stale key (Space holds an older one) | Console: **created 3 hours ago**, last used today | ✗ |

The Billing page: no payment method, no subscription, **US$0.00 credits**.

One trap worth naming. The user's earlier "usage 0.00 USD all month" reading
felt like proof that nothing had been consumed. It proves nothing at all —
on a free tier nothing is *billed*, so the dollar figure sits at zero whether
you burned every token or none. **It is the wrong meter**, and it had been
quietly reassuring us for a day.

### 12.3 Testing the alias without ever touching the key

The last live hypothesis was that our `mistral-small-latest` resolved to a
snapshot the org has no allocation for, versus the `mistral-small-2603` the
limits page actually lists.

Testing it needed the key. The key exists only as an HF Space secret, and
handing a live credential to a shell is exactly the mistake §7 of this same
log is about. So the Space tested it for us: `/rag/query` accepts an
arbitrary `provider` and `model` and falls back to its own `MISTRAL_API_KEY`.
Two POSTs, two model names, then read the log. **The secret never moved.**

First attempt returned in 1.0s with no upstream request logged — a cache hit
on an identical query. A probe that never reaches the thing being probed
looks exactly like a probe that succeeded. Re-ran with unique queries:

```
17:08:52  mistral-small-2603     429  code 1300
17:09:07  mistral-small-latest   429  code 1300
```

**Identical.** The explicit snapshot — the one the org's own limits page
grants 1.00 req/s and 20,000 TPM — refused a cold ~500-token request. Alias
hypothesis dead, and it was mine.

### 12.4 The answer *(superseded — see §14)*

Every variable was eliminated except the organization itself. Mistral
authenticates the key and refuses to serve completions to this org
regardless of model, volume or timing. A key **created three hours earlier**
had never once returned a 200 — a fresh key cannot have exhausted anything.

That is the shape of an org holding valid credentials that has never been
enabled to serve. On Mistral that gate is phone verification on the
organization, which fits everything visible: no payment method, no
subscription, zero credits, and a complete limits table displayed anyway.
Stated to the user as the likely cause with the reasoning shown, not as a
confirmed one — it cannot be confirmed from outside the console.

**Nothing in this codebase is at fault.** Pacing, alias, rate ceilings and
monthly caps all came back clean. What the user has is one sentence for
support: *error code 1300, type rate_limited, on `mistral-small-2603`, first
call from a key created today, org has never received a 200.*

### 12.5 The one thing that was ours

Visible in every trace above: **three identical 429s per call site.** The
OpenAI SDK retries twice before our code sees a failure, and the judge and
confirm paths each latched independently — so one dead provider cost six
round trips and ~4 seconds per scan instead of one.

Three changes, all small:

- `llm.py` — `stream_groq_openai` and `complete` now take `max_retries`,
  threaded into the OpenAI client. Default unchanged for every other caller.
- `contradictions_judge.py` — judge calls pass `max_retries=0`. `_pace()`
  already guarantees the spacing the limit wants, so a failure there is a
  refusal, not congestion a retry can outrun; the SDK's extra attempts land
  inside the same window, fail identically, and only delay the fallback.
  Added `new_chain_state()`, a latch that can be shared.
- `contradictions.py` — the reconciliation endpoint builds **one** latch and
  hands it to both chains, so whichever finds the primary dead spares the
  other the same discovery.

Measured with a stubbed dead primary over 3 judge+confirm rounds:

| | Mistral round trips | Gemini calls |
|---|---|---|
| Before | 6 | 6 |
| After | **1** | 6 |

Fallback count unchanged — no answer is lost. Ruff 0.9.10 (CI's pin) clean.
The ml-api pytest suite could not run locally (`slowapi` and the rest absent
from the venv); that coverage is CI's, and it was reported as CI's.

**`4cbbf59`**, pushed, all three files uploaded to the Space. Space restarted
17:23:41 and the deployed source was re-read from the Space to confirm the
fix is what it is actually serving.

A deliberate gap, stated rather than papered over: the behavioural proof is
the local stub test. No live reconciliation scan was run against the Space,
because that spends real Gemini calls on a self-check — which §10.7 of this
log is precisely about. The deployed-source check is what could be proven
for free.

### 12.6 Lessons

9. **The timestamp is the evidence, not the status code.** A 429 says
   "refused". A 429 on a cold call after nine minutes of silence says
   "refused for a reason that has nothing to do with rate".
10. **$0.00 usage on a free tier measures nothing.** No spend is the
    definition of the tier, not a reading of consumption.
11. **A probe that hits a cache is not a probe.** A 1.0s response with no
    upstream log line is a null result wearing a green tick.
12. **The service can test the credential for you.** Any endpoint that takes
    a model name and falls back to a server key will run the experiment
    without the secret ever entering a shell.
13. **Say which hypothesis was yours when it dies.** The alias theory was
    mine, argued confidently, and wrong.

---

## 13. Still open (revised after §12)

Resolved since §11: the **Mistral diagnosis** (answered — org-level, not
ours) and the **double-latch** (fixed, `4cbbf59`).

- **contract-invoice-reconciliation clip** — unrecorded. The tool works now.
- **Mistral** — **§14 supersedes this.** Read API → Usage: monthly token cap
  or org-level block. The remedy is pay-as-you-go if it is the cap, not a
  support ticket and not credits.
- **Logging spec** — agreed, nothing built. §9 has the order.
- **Five paid clips** — document-intelligence, multimodal-rag, optuna,
  prompt-injection-playground, text-to-sql.
- **`verify-recon-warning.mjs`** — untracked in `ml-portfolio`; keep as a
  test or delete.
- **Three `RENDER_*` secrets** — now unused.

---

## 14. Correction to §12 — and the drain it exposed

Written 2026-09-06, after the user pasted Mistral's own help article. Two
things in §12 are wrong. They are marked in place rather than edited away,
because a log that quietly rewrites its own mistakes is worth less than one
that shows them.

### 14.1 What the doc says

> The API enforces three limits:
> **Requests per second** (concurrent requests) · **Tokens per minute**
> (input + output throughput) · **Tokens per month** (overall consumption
> cap).
>
> Rate limits ... are **set at the organization level and apply across all
> your workspaces.**

### 14.2 Wrong thing #1 — the monthly cap

§12.2 eliminated "monthly token budget" on the grounds that the Limits page
shows no monthly cap for chat models. The page doesn't display one in the
per-model cards; **the limit exists anyway.** Absence from a UI panel was
read as absence from the system. The row is struck, and the hypothesis is
live again.

### 14.3 Wrong thing #2 — the reasoning, which is worse

§12.4's load-bearing argument was: *a key created three hours ago cannot have
exhausted anything.* The doc kills it in one clause — limits are **set at the
organization level**. The budget belongs to the org, not to the key. A key
minted three hours ago inherits whatever the org has been spending since
Mistral became the default RAG provider on 2026-08-24.

Key age proves nothing, and a conclusion was built on it anyway. §12.6's
lesson 13 was about naming a dead hypothesis as mine; this is the same fault
one level down — not a wrong guess but a wrong *inference*, stated with the
same confidence as the parts that were actually evidenced.

### 14.4 The revised picture

Monthly-cap exhaustion now fits every observation:

| Observation | Fits? |
|---|---|
| Cold 429 after 9 minutes idle | ✓ a monthly cap ignores idle time |
| Both `-latest` and `-2603` refused | ✓ org-level, not per-model |
| $0.00 billed | ✓ free mode is never billed |
| Zero 200s, ever | ✓ once the cap is hit, everything stops |

Still unconfirmed — **API → Usage** settles it, and remains unread. One
tension worth holding: Mistral's free allowance is generally understood to be
large, so a portfolio site exhausting it in five days is surprising. If Usage
shows headroom, the cap theory dies too and it is back to an org-level block.

Also from the doc, and it changes the remedy: tiers unlock only through
**pay-as-you-go**, and track **cumulative billed amount**. *"Adding credits
does not raise your rate limits."* Topping up the US$0.00 balance would
achieve nothing. §12.4's advice to open a support ticket was wrong.

### 14.5 The drain §12 never noticed

The user's reply to all this was the sharp question of the day:

> *"gemini is paid one, if it is used in every call then my credits will get
> exhausted"*

Correct, and worse than assumed. `generation.py`'s cascade was
`mistral → gemini → cohere`. Mistral being dead did not just break the judge
— it silently promoted **Gemini, the only paid key here, to de-facto provider
for every question on the site.** That had been true for a day. §12 diagnosed
the dead provider in detail and never once asked what was answering in its
place.

Cohere was already third in that list and had never been reached. Probed
through the Space (same trick as §12.3 — the service tests its own secret):

```
05:27:26  POST https://api.cohere.ai/v2/chat  "HTTP/1.1 200 OK"
```

143 tokens, full correct answer, no Gemini call in the trace.

A second finding fell out of the same log: **three Mistral 429s fired before
Cohere ran, on a query that had not selected Mistral at all.** Query
expansion pins Mistral deliberately (so it cannot spend the selected
provider's budget — see `query.py`'s comment), so every question on the site,
whatever provider the user picked, opened with three doomed requests and ~2s
of latency. Yesterday's `max_retries=0` covered the judge only.

**`51d6866`** — Cohere promoted ahead of Gemini; expansion passes
`max_retries=0`. Deployed, and the Space's served source re-read to confirm.

### 14.6 The judge fallback — offered, then argued against

Cohere was tested on judge-shaped JSON, including the paraphrase pair that is
a recorded live false positive ("due within 30 days of invoice date" vs "Due
date: 30 days from issue"):

| Case | Expected | Cohere | Parser |
|---|---|---|---|
| USD 12,500 vs USD 15,200 | true | true | ✅ |
| the 30-day paraphrase | false | false | ✅ |

Case A arrived inside a ```json fence; `_parse_judge_response`'s `\{.*\}`
regex handles it, verified by feeding both verbatim responses through the
real parser.

Then the swap was recommended **against**, having offered it:

- the drain was Q&A, and `51d6866` already closed it; reconciliation is a
  handful of calls behind a two-document upload
- judge errors cost more than Q&A errors — this is the tool that shipped a
  false "No discrepancies found" the day before
- two passing cases show capability, not equivalence

Gemini stays the judge's fallback. Cohere is now a known-viable substitute if
Gemini ever fails, which is worth having written down and not worth acting
on.

### 14.7 Lessons

14. **"Not shown in the UI" is not "does not exist."** A limits page that
    omits a limit is a rendering decision, not a fact about the system.
15. **Check whether an inference is load-bearing before trusting it.** The
    key-age argument was never evidence; it was a plausible sentence doing
    the work of one.
16. **When a provider dies, ask what took over.** A whole section can be
    spent diagnosing a dead dependency without noticing the fallback is the
    expensive one.
17. **Offer an option and still argue against it.** Having built the evidence
    for the judge swap, the right answer was that the saving did not justify
    the risk.

---

## 15. Mistral answered — and both theories were wrong

The user sent a nine-line ticket (§14 asked; the first draft ran to a page
and the user's reply was *"you think they will read all that??"* — the short
version kept the two facts that stop a canned answer: a cold 429 after ten
idle minutes, and a key that had never once returned a 200). Mistral replied
the same day.

### 15.1 The answer, verbatim in substance

> Free (evaluation/prototyping) access to Studio operates on a **best-effort
> basis — there's no reserved model capacity.** When paid subscribers are
> using the models, free-tier requests can be rejected, **even if you're well
> under the RPS/TPM numbers shown on your Limits page.** This is expected
> behavior for free mode, not a bug or account block.
>
> Since you're on free mode with no payment method, you're **not being
> blocked by a hidden monthly token cap** ... credits are not consumed while
> on free mode.

### 15.2 The scoreboard

| Section | Theory | Verdict |
|---|---|---|
| §12.4 | Org-level refusal, likely pending phone verification | Right shape, wrong reason |
| §14.4 | Monthly token cap exhausted | Wrong |
| — | No reserved capacity; rejected when paid traffic is busy | **Correct** |

Neither theory was testable from outside, because the variable is **other
people's load**. The same request succeeds at 3am and fails at 3pm. Every
experiment in §12 and §14 assumed the answer was a property of our account —
a limit, a cap, a block, a key. It was a property of the shared system at the
moment we asked.

That also explains the one thing that never fit: a free allowance large
enough that a portfolio site should not exhaust it in five days (§14.4's
"tension worth holding"). It never was exhausted.

### 15.3 What it changes in the code

Mistral is not down, was never mis-keyed, and needs no fix. It is
**non-deterministic by design** — and that is worse than being broken,
because a provider that works at 3am and fails at 3pm cannot be first
anywhere. It was first in four places.

Their own advice — *implement retry with exponential backoff* — does not
apply here. Backoff assumes congestion that clears in seconds; this was
measured refusing for hours. `max_retries=0` plus the latch stays.

**`db8f2eb`** demotes it where it was primary:

- `generation.py` cascade → `cohere, mistral, gemini`. Cohere first (free,
  reliable), Mistral second (free when capacity exists, one ~0.5s round trip
  when not), Gemini last because it is the only paid key.
- `query_helpers.py` `QueryRequest` default → `cohere` / `command-a-03-2025`.
  The comment it replaces called Mistral "the proven-reliable default", which
  is exactly the claim support disproved.

Left alone deliberately: the judge's Mistral primary and the Mistral-pinned
query expansion. Both are optional-degrading and now cost one round trip;
changing them buys little and the judge's accuracy is worth more than the
call (§14.6).

### 15.4 The real Gemini exposure — a second correction

§14.5 said Mistral's death "silently promoted Gemini to de-facto provider for
every question on the site". True in outcome, **wrong in mechanism**, and the
mechanism matters.

`useRagChat.ts:50` and `Chatbot.tsx:76` both open with
`useState("gemini")`, and the UI sends `provider` explicitly on every
request. So visitors were never using the backend default at all — they were
choosing Gemini directly. The cascade only ever applied to callers that omit
the field, which in practice meant the diagnostic probes in §12.3 and §14.5.

So the backend reorder is correct and worth having, but it is **not** the
change that stops the spend. That change is two `useState` lines in
`ml-portfolio`, and it is a user-facing default, so it was raised rather than
made.

The lesson is narrower than "check the frontend": a default in a schema is
only a default for callers who *omit the field*. The probe that omitted it
was mine, so the mechanism I measured was the one I had created.

### 15.5 Lessons

18. **Some causes are unobservable from the client.** "Best-effort, no
    reserved capacity" cannot be distinguished from a cap, a block or a dead
    key by any experiment run from outside — every §12/§14 test assumed the
    answer lived in our account.
19. **Ask the vendor sooner.** Two sections of inference were beaten by one
    nine-line ticket. The evidence gathered was not wasted — it is what made
    the ticket short enough to be read — but the ticket could have gone out
    a day earlier.
20. **Non-deterministic is worse than broken.** A dependency that fails
    honestly gets handled; one that works intermittently gets trusted.
21. **A schema default only applies to callers who omit the field.** The
    "default provider" was not what any real user was using, and the only
    caller exercising it was my own probe.

---

## 16. Groq was dead too, and nobody knew

Chasing the Gemini spend led straight into a bug that had nothing to do with
cost. Asked whether Groq could be the free default for the site chatbot
(§15.4), the honest first step was to check rather than assume.

### 16.1 Four names, four failures

`/api/chat` on the live site returned *"Something went wrong"* for Groq while
Gemini answered normally — and Claude returned its own *"not configured yet"*
message. That third response is what made the first one legible: a missing
key produces the polite message, so Groq **had** a key and was throwing.

Every Groq model name in the two repos, tested live through the Space:

| Model | Where | Result |
|---|---|---|
| `llama-3.1-8b-instant` | site chatbot | 404 `model_not_found` |
| `llama-3.3-70b-versatile` | tools chat | 404 `model_not_found` |
| `gemma2-9b-it` | tools chat | 400 `model_decommissioned` |
| `mixtral-8x7b-32768` | tools chat | 400 `model_decommissioned` |

Groq had retired all four. Anyone selecting Groq in either chat had been
getting an error, silently, for however long that has been true. It was found
only because a cost question happened to walk past it.

### 16.2 The user's three replacements

Offered `qwen/qwen3.6-27b`, `qwen/qwen3.8-27b`, `minimaxai/minimax-m2.7`.
Tested rather than trusted, which was worth doing in both directions:

- Both Qwen names **exist** — refused for an unrelated reason, below.
- `minimaxai/minimax-m2.7` → 404. Groq's message covers two cases without
  distinguishing them ("does not exist **or you do not have access to it**"),
  so it was left out rather than shipped as a broken dropdown entry. The user
  later dropped it.

The Qwen refusal was the interesting part:

> Request too large ... on **output tokens per minute (OTPM): Limit 1000,
> Requested 2048.**

Not the model, not the key — the *ask*. With no `max_tokens` set, the SDK
requested 2048, and Groq rejects the whole request up front when expected
output exceeds the tier cap. It never generates a token, so the log reads
exactly like a dead provider. `llm.py` now accepts `max_tokens` and
`generation.py` caps Groq at 900.

Notably the site chatbot already sent `max_tokens: 400`, so its only problem
was the retired model name — two different bugs wearing the same error
message.

### 16.3 What shipped

- **`94df800`** (ml-portfolio) — tools chat defaults to Cohere; chatbot model
  → `qwen/qwen3.6-27b`; four dead names removed from the tools list, two
  verified ones added.
- **`33acb43`** (ML-Unified) — `max_tokens` on the OpenAI-compat streamer,
  Groq capped at 900.

Verified after deploy, and the first check failed honestly: a Groq query came
back `served_provider: cohere` — the call had landed while the Space was
still serving old code. Re-run against the rebuilt Space:
`served_provider: groq`, no fallback, 123 tokens, a complete answer, and **no
`<think>` leakage** despite Qwen being a reasoning model.

Final state of the four providers:

| Provider | State |
|---|---|
| Cohere | free, reliable — tools-chat default |
| Groq | free, working again — capped at 900 output tokens |
| Gemini | **paid** — no longer any chat's default, last in the cascade |
| Mistral | intermittent by design — demoted, kept as a free bonus |

### 16.4 Lessons

22. **A generic error message hides the difference between two bugs.** "Something
    went wrong" covered a retired model in one app and an oversized request in
    another; only the raw API body separated them.
23. **The provider that answers politely tells you about the one that doesn't.**
    Claude's "not configured yet" proved Groq's key existed, which turned a
    vague failure into a specific one.
24. **Test the names you are handed, including the ones you expect to work.**
    Two of three were fine, one was not, and the two that were fine failed for
    a reason nobody had guessed.
25. **Verify after the rebuild, not during it.** The first post-deploy check
    measured the old code and would have read as a failed fix.
