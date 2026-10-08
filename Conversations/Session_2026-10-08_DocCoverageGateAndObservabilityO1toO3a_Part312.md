# Part 312 — a doc-coverage CI gate, then observability from plan to O3a

Continues [Part 311](Session_2026-10-07_TestwrightToolGuideInAppWiring_Part311.md).
2026-10-08. Started by reconciling the pending list against live state, built the
one no-blocker item (a doc-coverage CI gate), then took observability from research
→ roadmap → three shipped slices (O1 correlation id, O2 RUM, O3a LLM telemetry).

Two through-lines:
- **Build on what already pays nothing and is already there.** O1's trace id turned
  out to already exist (`trackedFetch`'s `run_id`); O3's `llm_calls` already had most
  columns; the error store already had a `meta` jsonb. Each feature was mostly *wiring
  what was there*, not new infrastructure.
- **Check the shared-infra assumption before you ship it.** A custom request header
  would have tripped CORS preflight on every direct Space call — caught by reading the
  CORS config first, not after.

---

## Arc 0 — pending list, reconciled against live state
Read the last 5 parts + `docs/`. Found the docs were stale in places (OPEN_ISSUES
dated 2026-09-13 still listed E6 open though Part 310 closed it; the Testwright plan
still said R8 "in progress" though it shipped). Live-verified each claim. Net
actionable item with no blocker: **the doc-coverage CI check** (Part 310 Arc 6).
Everything else is parked on a missing prerequisite (R5 authed app, learn-from-edits
data) or is a user-side key rotation (E9/E10).

## Arc 1 — doc-coverage CI gate (`ml-portfolio 5919311`)
The handbook job proves the generated book is *in sync*; it cannot prove the sources
*exist*. `scripts/check-doc-coverage.py` (123 lines) enumerates the three relations CI
can see, reusing `handbook_sources.py` so sources are parsed one way:
- **A. tool dir → capabilities card** (allowlist `CARD_EXEMPT` = `rag-analytics`,
  `text-to-sql`, the two deliberate card-less dirs).
- **B. tool guide → wired in a `.tsx`** (locks in Part 311 so a guide can't go
  handbook-only again).
- **C. platform → in-app guide or chapter.**
Proved green on HEAD **and** red on a planted violation of each invariant (a check that
can't fail is worthless — [[feedback_status_claims_need_evidence]]). **Inherent limit,
stated in the script:** a pure behavior change in an existing file has no footprint to
enumerate — always needs human review.

## Arc 2 — handbook is current
Regenerated → no diff (the `handbook` CI job enforces this every push). All 58 card
titles + 5 platforms present; 60 tool dirs all have a `userGuide.ts`. The PDF/`.md`
download carries full info on every tool + platform. Caveat recorded for the user: the
handbook is only as deep as what was *written into* each guide — complete on *what*
exists, only as detailed as the author made it on *how* each behaves.

## Arc 3 — observability: research → roadmap (`docs/OBSERVABILITY_PLAN.md`)
Searched the 2025 consensus (three pillars + RUM + LLM obs under OTel GenAI semconv).
Inventoried what exists: Sentry (errors-only, `tracesSampleRate:0`), the DIY error
store, Supabase analytics, `providerAlert`, `LOGGING_SPEC`. **The missing pillar is
correlation** — no id links browser → Next route → Space → provider. Decided (all the
user's calls, §7): **Sentry free tier + Supabase, no new paid vendor**, telemetry shaped
to OTel semconv for portability; sampling errors 100% / traces 10% / LLM 100%; set the
backend DSN (O4). [[feedback_no_unilateral_provider_swaps]]

## Arc 4 — O1 correlation id, verified live
- **The id already existed.** `trackedFetch` mints a per-run `run_id` and logs it but
  **never put it on the wire**. O1 = send it as `x-trace-id` from the one chokestream
  (78 callers for free). FE `b02df24`.
- **CORS check first.** A custom header triggers a preflight; confirmed the Spaces use
  `allow_headers:["*"]` and `enforce_origin` admits our origin *before* injecting the
  header — else every direct tool call would have broken. [[feedback_shared_infra_hidden_assumptions]]
- **Backend** `security/trace.py` middleware captures/echoes the id, holds it in a
  contextvar, stamps 500s into `errors.meta.trace_id` (**no migration** — reused the
  existing `meta` jsonb) + the request log. BE `fd43ea4`, HF-uploaded, **verified live**:
  echoes a caller id and mints a 32-hex one when absent.
- **Route-stamping** (`2cb0486`): `chat`/`ai-explain`/`ai-tools` read the id, set a Sentry
  tag, thread it into the `PROVIDER_AUTH_FAIL` log line (Vercel log search); `/api/error`
  merges the header into `meta.trace_id`.

## Arc 5 — O2 RUM / Web Vitals (`ml-portfolio 0c95e5c`)
`tracesSampleRate` 0 → 0.1 on the client: the default `browserTracingIntegration`
records a sampled transaction and attaches Core Web Vitals (LCP/INP/CLS/FCP/TTFB) for
free. Replay stays **off**; a new `beforeSendTransaction` strips query strings so a trace
is as content-free as an error; privacy page updated (LOGGING_SPEC §7). Server tracing
left at 0 — deferred to O4 with the outbound-propagation-to-providers decision.

## Arc 6 — O3a LLM telemetry (frontend)
- **The table was already most of the way there.** `llm_calls` had provider/model/
  status/latency/**run_id** already — and `run_id` *is* the trace id, so correlation
  needed **no `trace_id` column**. Migration `llm_calls_o3.sql` only added
  `input_tokens`/`output_tokens`/`cost_usd`/`operation` (additive, idempotent; user ran it).
- `lib/llmTelemetry.ts`: per-provider usage extractor (each provider reports tokens in
  its own shape), a **dated** price table (verified, not guessed — Claude Haiku 4.5 $1/$5
  via the claude-api skill; Gemini 2.5 Flash $0.30/$2.50 via web; free tiers $0;
  [[feedback_verify_before_recommending]]), and a fire-and-forget `recordLlmCall`.
- Captured success **and** failure in `chat` (`2875a84`), `ai-explain` (`2875a84`),
  `ai-tools` (`47b1977`). **Decision:** `ai-tools` logs **server-key calls only** — a BYOK
  call is the caller's spend, not ours (same scoping as the E3 alert).
- Dashboard: `/api/llm-stats` (aggregates cost / success / tokens / p95 / per-provider,
  mirrors `/api/error` windowing) + `AnalyticsLLMPanel` (the `AnalyticsErrors` single-hue
  bar idiom — honor the existing design system) (`a9a6801`).

## Key decisions / lessons
- **Migration-free when a jsonb already exists.** O1 correlation landed in
  `errors.meta.trace_id` with no schema change; O3 only grew the table for genuinely new
  numeric fields.
- **Scope cost logging to our own spend.** Logging a BYOK call's "cost" would misreport
  — only server-key calls are ours to count.
- **A header is a shared-infra change.** Verify CORS/preflight before adding one, the same
  way a new dependency gets checked against the thing that consumes it.
- **Stale docs cost trust.** Two plan docs disagreed with shipped reality; reconcile the
  live state before quoting a pending list. [[feedback_verify_pending_before_building]]

## Commits
| Repo | Commits |
|---|---|
| ml-portfolio | `5919311` (doc-coverage gate) · `b02df24` (O1 wire) · `2cb0486` (O1 routes) · `0c95e5c` (O2 RUM) · `2875a84` (O3a chat+ai-explain) · `47b1977` (O3a ai-tools) · `a9a6801` (O3a dashboard) |
| ML-Unified (backend, HF) | `fd43ea4` (O1 trace middleware; HF-uploaded, verified live) |
| ML-Unified (docs) | `1f08fb1`·`639150c` (observability plan + §7 decisions) · `791c3b0`·`4475e5e` (O1/O2/O3a status) |

## Open / next
- **O3b** — backend `call_log.record_call` tokens/cost + thread trace id into its context
  (HF upload). **O4** — set backend `SENTRY_DSN` + propagate trace id into backend errors.
  **O5** SLOs/burn-rate alerts. **O6** multi-hop tracing for the two real agents.
- Still parked: R5 authed testing, learn-from-edits Phase 1, R8 email alerts; user-side
  key rotation E9/E10.

Related: [[project_testwright_qa_platform]], [[reference_logging_spec]],
[[project_sentry_error_reporting]], [[feedback_shared_infra_hidden_assumptions]],
[[feedback_status_claims_need_evidence]], [[feedback_no_unilateral_provider_swaps]].
