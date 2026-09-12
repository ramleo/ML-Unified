# Session 2026-09-06 — Part 277

## The provider day

**7 commits.** 6 in `ML-Unified`, 1 in `ml-portfolio`.
**Four LLM providers audited; three were broken or mispriced.**
Two of my own theories were disproved — one by the vendor, one by their docs.

The session began as a single follow-up question — *"check why is mistral key
dead?"* — and ended with every provider in the stack re-tested, re-ordered,
and in two cases un-broken. No feature was built. The site is meaningfully
cheaper and less fragile than it was this morning.

Detailed forensics live in Part 276 §12–16, which were appended to that file
as the work happened. This is the day's own account.

---

## 1. The question, and why it was answerable

Part 276 ended with "Mistral key — still dead; the fallback is carrying it."
A shrug, carried forward as a known unknown.

It turned out to be answerable in about fifteen minutes, for free, because
the previous day had already taught the two techniques it needed:

- **Read the Space's log buffer** rather than re-running the failure.
- **Let the service test its own secret.** `/rag/query` takes an arbitrary
  `provider` and `model` and falls back to the server-side key, so any
  credential question can be answered without the key ever entering a shell.

That second trick did most of the day's work. Every provider probe below used
it. No API key was handled, pasted, or logged at any point.

---

## 2. Being wrong twice, in public

| Theory | Basis | Verdict |
|---|---|---|
| Pending phone verification on the org | Billing page: no payment method, no subscription | Wrong |
| Monthly token cap exhausted | Mistral's own help doc lists a monthly cap | Wrong |
| **No reserved capacity on free tier** | Mistral support | **Correct** |

The second theory came from correcting the first — and the correction
contained its own error. §12 eliminated the monthly cap because the Limits
page does not display one; the doc says it exists. Fine. But §12's conclusion
also rested on *"a key created three hours ago cannot have exhausted
anything"*, and that was never evidence at all: limits are **organization**
level, so key age is irrelevant. A plausible sentence had been doing the work
of a fact.

The real answer, from Mistral support:

> Free access to Studio operates on a **best-effort basis — there's no
> reserved model capacity.** When paid subscribers are using the models,
> free-tier requests can be rejected, **even if you're well under the
> RPS/TPM numbers shown on your Limits page.**

Nothing was wrong with the account, the key, or the code. The variable was
**other people's load** — which is why no experiment run from our side could
ever have found it. The same request succeeds at 3am and fails at 3pm.

**The lesson that generalises:** two sections of inference lost to one
nine-line support ticket. The evidence gathered was not wasted — it is what
made the ticket short enough to be read — but it could have been sent a day
earlier.

### 2.1 The ticket

First draft ran to a full page of eliminated hypotheses. The user's reply:

> *"you think they will read all that??....keep it concise"*

Correct. The nine-line version kept only the two facts that stop a canned
"you're sending too fast" reply: a **cold** 429 after ten idle minutes, and a
key that had **never once** returned a 200. It got a real answer same day.

---

## 3. What the diagnosis walked past

While proving Mistral was dead, a question went unasked for a full section:
**what was answering instead?**

`generation.py`'s cascade was `mistral → gemini → cohere`. Gemini is the only
paid key in the project. So Mistral failing had quietly promoted the paid
provider to serve everything that fell through — and Cohere, free and third,
was never reached.

The user saw it immediately:

> *"gemini is paid one, if it is used in every call then my credits will get
> exhausted"*

Correct, and it got worse on inspection. `useRagChat.ts` and `Chatbot.tsx`
both open with `useState("gemini")` and send `provider` explicitly, so real
visitors were never touching the backend default at all — they were choosing
the paid key directly, from the first render, every time.

**The narrow lesson:** a schema default only applies to callers that *omit
the field*. The only caller exercising it was my own diagnostic probe, so the
mechanism I had measured was one I created.

---

## 4. The audit

Each provider was tested live before anything was changed.

| Provider | Found | Action |
|---|---|---|
| **Cohere** | Working. 200 OK, full answer, verified serving end to end | Promoted: cascade #1, tools-chat default |
| **Groq** | **All four model names dead** — 2× 404, 2× decommissioned | Names replaced, output capped |
| **Gemini** | Working, paid, and the default everywhere | Demoted to last resort |
| **Mistral** | Intermittent by design | Demoted to #2, kept as a free bonus |

### 4.1 Groq had been broken silently

Asked whether Groq could be the chatbot's free default, checking first turned
up that `llama-3.1-8b-instant`, `llama-3.3-70b-versatile`, `gemma2-9b-it` and
`mixtral-8x7b-32768` had all been retired. Anyone selecting Groq in either
chat had been getting *"Something went wrong"* — for however long that has
been true. It was found only because a cost question happened to walk past
it.

What made the failure legible was **Claude's** response on the same endpoint:
*"Claude is not configured yet"*. A missing key produces the polite message,
so Groq's key existed and the call itself was throwing.

Of the three replacements the user supplied, two existed and one did not
(`minimaxai/minimax-m2.7` → 404; Groq's message cannot distinguish "wrong
name" from "no access", so it was left out and later dropped).

The two Qwen models were refused for a different reason entirely:

> Request too large ... **output tokens per minute (OTPM): Limit 1000,
> Requested 2048.**

Not the model — the *ask*. With no `max_tokens`, the SDK requested 2048 and
Groq rejects the whole request before generating a token, which in a log is
indistinguishable from a dead provider. Capped at 900 and it works.

Meanwhile the site chatbot already sent `max_tokens: 400`, so its only fault
was the retired name. **Two different bugs behind one generic error string.**

---

## 5. Efficiency work

**`4cbbf59`** — a dead provider was being rediscovered six times per
reconciliation scan: the judge and confirm chains each held their own latch,
and the OpenAI SDK retried each twice before our code saw a failure. One
shared latch plus `max_retries=0` took it to one round trip. Measured against
a stubbed dead primary: **6 → 1**, fallback count unchanged.

`max_retries=0` deserves its reasoning recorded, because Mistral support
recommended the opposite (exponential backoff). Backoff assumes congestion
clearing in seconds; this refused for hours, and our calls are already paced.
A retry landing 0.4s later inside the same rejection window buys nothing but
latency.

**`51d6866`** — query expansion got the same treatment. It is optional by
design (degrades to `[query]`), yet every question on the site opened with
three doomed Mistral requests and ~2s of dead time before retrieval started.

---

## 6. Commits

| Commit | Repo | What |
|---|---|---|
| `4cbbf59` | ML-Unified | Shared judge latch, `max_retries=0` — 6 dead-provider round trips → 1 |
| `7a6d78a` | ML-Unified | Part 276 §12–13: Mistral diagnosed |
| `51d6866` | ML-Unified | Cohere ahead of Gemini; expansion stops retrying |
| `dadc6b3` | ML-Unified | Part 276 §14: correcting §12 |
| `db8f2eb` | ML-Unified | Mistral demoted after support's answer; Cohere the default |
| `33acb43` | ML-Unified | `max_tokens` on the OpenAI-compat streamer; Groq capped at 900 |
| `03202ca` | ML-Unified | Part 276 §15–16 |
| `94df800` | ml-portfolio | Cohere default; four dead Groq names replaced |

Every backend commit was uploaded to the Space and the served source re-read
to confirm the deploy — including one upload that timed out **after** landing
one of two files, caught by checking what the Space actually had rather than
blind-retrying both.

---

## 7. Verification, including the check that failed

The first post-deploy Groq probe returned `served_provider: cohere` — the
call had landed while the Space was still on old code. Re-run against the
rebuilt Space: `served_provider: groq`, 123 tokens, complete answer, **no
`<think>` leakage** despite Qwen being a reasoning model.

One gap was stated rather than papered over: the judge-latch fix is proven by
a local stub test, not by a live reconciliation scan, because that spends
real Gemini calls on a self-check. The deployed-source check is what could be
proven for free.

Cohere was also tested on judge-shaped JSON, including the paraphrase pair
that is a recorded live false positive — both verdicts correct, both parsed.
Then the swap was **recommended against**: the drain was Q&A and it was
already fixed, judge errors cost more than Q&A errors on a tool that shipped
a false all-clear the day before, and two passing cases show capability, not
equivalence.

---

## 8. Lessons

1. **Some causes are invisible from the client.** "Best-effort, no reserved
   capacity" cannot be told apart from a cap, a block, or a dead key by any
   test run from outside.
2. **Ask the vendor sooner.** Two sections of inference, beaten by nine lines.
3. **Non-deterministic is worse than broken.** A dependency that fails
   honestly gets handled; one that works intermittently gets trusted.
4. **Check whether an inference is load-bearing.** "A fresh key can't have
   exhausted anything" was never evidence, and a conclusion sat on it.
5. **"Not shown in the UI" is not "does not exist."**
6. **When a provider dies, ask what took over.** A whole section can be spent
   on a dead dependency without noticing the fallback is the expensive one.
7. **A schema default only applies to callers who omit the field.**
8. **A generic error string can hide two unrelated bugs.**
9. **Verify after the rebuild, not during it.**
10. **Test the names you are handed** — including the ones you expect to
    work, and the ones you expect to fail.

---

## 9. Still open

- **contract-invoice-reconciliation clip** — unrecorded; the tool works.
- **Five paid clips** — document-intelligence, multimodal-rag, optuna,
  prompt-injection-playground, text-to-sql.
- **Logging spec** — agreed, nothing built. `LOGGING_SPEC.md` §9 has the
  order.
- **Returning visitors keep Gemini.** The provider choice is persisted in
  `localStorage`, so the new Cohere default reaches new visitors only.
- **Site chatbot still defaults to Gemini** — Cohere is not wired into
  `/api/chat` at all, and Groq there is capped at 400 output tokens.
- **Groq's free tier is 1000 output tokens/minute**, shared across all
  visitors — roughly two answers a minute before it starts refusing.
- **`verify-recon-warning.mjs`** — untracked in `ml-portfolio`.
- **Three `RENDER_*` secrets** — unused.
