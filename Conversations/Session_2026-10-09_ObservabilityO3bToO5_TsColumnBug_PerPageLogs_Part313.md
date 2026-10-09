# Part 313 — observability O3b→O5, the ts-column bug, and per-page logs

Continues [Part 312](Session_2026-10-08_DocCoverageGateAndObservabilityO1toO3a_Part312.md).
2026-10-09. Carried the observability roadmap from O3a to O5 (backend LLM telemetry,
backend Sentry trace-tagging, SLOs + burn alerts), then a real SLO breach the new
scorecard surfaced led to a latent-bug find, a measurement fix, and the per-page
error log the user asked for.

Three through-lines:
- **Keep building on the funnel that already exists.** O3b put tokens/cost on the
  one `instrument()` wrapper and threaded the trace id via the existing contextvar;
  O4 reused `error_capture_dispatch`; (A) reused the `errors` table. Each feature was
  wiring, not new infrastructure.
- **A check that silently *passes* on a typo is as bad as one that can't fail.** The
  `isMissingSchema` catch was broad enough to turn a wrong column name into a fake
  "run the migration" — hiding 283 real rows from O3's panel for days.
- **An SLO has to measure the right thing.** A per-call success SLO counted recovered
  free-tier throttles as failures (79.9%); the user-facing number was 99.0%.

---

## Arc 1 — O3b backend LLM telemetry (`ML-Unified 96a4bca` + `ml-portfolio 8e1fd48`)
The backend telemetry funnel is `instrument()` in `routers/rag/llm.py`, which POSTs via
`call_log.record_call` → the Vercel `/api/llm-log` sink → Supabase (the Space holds no
DB key). O3b: `record_call` now carries input/output tokens, estimated cost (price table
**mirrored** from the frontend `llmTelemetry.ts` so a backend and frontend row for the
same model agree), and `operation`; and `run_id` falls back to `current_trace_id()` at
the funnel, so every backend LLM call joins the O1 spine with no per-site change.
**Token capture with zero request-shape change:** Claude via the SDK's
`get_final_message().usage`, Gemini + Cohere from the SSE already parsed. **Groq/
OpenAI-compat skipped** — their usage needs `stream_options`, which not every compatible
base accepts, and they're free-tier ($0). The sink (`/api/llm-log`) had to learn the four
new fields too — a backend telemetry change is only as good as the sink that persists it.

## Arc 2 — O4 backend Sentry trace-tag + a verifiable DSN
- **Tag placement is load-bearing** (`b5bbcf9`). A backend 500 should pivot to the same
  frontend action as the DIY error-store row. The tag can **not** go in `before_send`:
  the trace middleware is *outer*, so its `finally` resets the trace contextvar before the
  exception reaches Sentry's outer auto-capture. It goes in `error_capture_dispatch`'s
  except block, where the contextvar is still live (the same place the store POST reads it).
- **Make "is it working" answerable** (`4371a65`). A malformed `SENTRY_DSN` makes
  `sentry_sdk.init` raise, which we swallow → the Space boots but Sentry is silently
  dormant. `init_error_reporting()` now records its result; the admin-gated
  `/security/status` returns `sentry_active`. User set the **FastAPI** DSN on the Space
  (Next.js DSN stays on Vercel), curled the endpoint → `sentry_active:true`. Backend
  Sentry **verified live** without needing a real 500. [[project_sentry_error_reporting]]

## Arc 3 — O5 SLOs + burn alerts (`ml-portfolio 74f2f52`, `ML-Unified 1c60fb3`)
One content-free `/api/slo` scorecard — a single source of truth over Supabase views
(reuses `/api/llm-stats`' math) — for four SLOs: LLM success ≥98%, LLM p95 ≤12s, backend
5xx count, frontend error count. Dashboard tile `AnalyticsSLO.tsx` (status chip = colour
**and** word). Alerting **reused the proven security-watch model**, not `providerAlert`:
`.github/workflows/slo-watch.yml` polls `/api/slo` every 30 min and fails on any `breach`
→ GitHub's free failure email (ungated endpoint, no secret). Honest scope stated in code:
fast-burn (single-window), not SRE multi-window burn-rate; ratio SLOs stay "insufficient"
under MIN_SAMPLE calls; count targets scale with the window.

## Arc 4 — the ts-column bug (`ml-portfolio f367eeb`)
The live SLO came back `needs_setup:true` though the tables exist. **Debug-first** (a node
script against Supabase, printing only the error) found it: `column llm_calls.created_at
does not exist` — the table's timestamp column is **`ts`**. Both `/api/slo` (O5) and
`/api/llm-stats` (O3) filtered on `created_at` → Postgres **42703** → `isMissingSchema`
(which matches 42703) swallowed it as `needs_setup`. **So O3's LLM panel had been silently
showing "run the migration" despite 283 real rows.** The `errors` table *does* use
`created_at` (it postdates the convention) — so `/api/slo`'s errors query was correct and
untouched. Saved as [[feedback_llm_calls_ts_column]] so it can't bite a third file.

## Arc 5 — the breach was real; the metric was wrong
With `ts` fixed, the 30d LLM success SLO read **79.9%** (50/249) — a breach. Breaking the
50 failures down (evidence, not inference): **48 Mistral 429** "Rate limit exceeded" + **2
Cohere 422**. The 48 match the known free-tier contention pattern ([[project_llm_provider_status]]),
and the cascade recovers from them — the user still gets an answer. So three fixes:
- **SLO 429-exclusion** (`e7e2ea2`): a recovered 429 is not a user-facing failure. Excluding
  rate-limit 429s from the success denominator and the p95 sample moved 79.9% → a truthful
  **99.0%** (PASS). Surfaced separately as `rate_limited_excluded`, not hidden.
- **(B) capture the response body** (`ML-Unified 8d1a6ed`, HF): the two Cohere 422s were
  undiagnosable because only the generic `"Client error 422 for url"` was stored — the body
  naming the reason went to the ephemeral Space log. `describe_error` now folds the provider
  response body (openai/anthropic `.body`, httpx `.text`) into `error_message`, content-free,
  so the next 4xx self-explains.
- **(A) Page Inspector** (`0c53daf`): the per-page error log the user asked for ("like HF
  logs"). `/api/error-detail` returns the pages that had errors, or one page's individual
  occurrences (time, source, kind, enriched message, trace id). The in-app drill-in that
  `AnalyticsErrors` (grouped) lacked; raw tails stay in Vercel/HF logs, joined by trace id.

## Key decisions / lessons
- **Set a Sentry tag where the trace contextvar is still live.** An outer middleware's
  `finally` reset makes `before_send` see an empty id — place it in the inner except.
- **A broad `isMissingSchema` catch hides column typos.** 42703 (undefined column) looks
  identical to a missing table; a wrong column name became a silent "needs_setup". Verify a
  `needs_setup` against the live schema before trusting it.
- **Mirror a price/column convention, don't assume it.** `llm_calls`=`ts`, `errors`=
  `created_at`; the older table predates the newer one.
- **Scope an SLO to user-facing success.** Counting recovered throttles as failures measures
  provider contention; exclude them and surface the throttle count separately.
- **Capture the response body or the next error is a mystery.** [[feedback_debug_first]]

## Commits
| Repo | Commits |
|---|---|
| ml-portfolio | `8e1fd48` (O3b sink) · `74f2f52` (O5 scorecard/tile/workflow) · `f367eeb` (ts fix) · `e7e2ea2` (SLO 429-exclusion) · `0c53daf` (A Page Inspector) |
| ML-Unified (backend, HF) | `96a4bca` (O3b telemetry+trace) · `b5bbcf9` (O4 Sentry trace tag) · `4371a65` (O4 sentry_active) · `8d1a6ed` (B 4xx-body capture) |
| ML-Unified (docs) | `96a4bca`·`b5bbcf9`·`1c60fb3` (OBSERVABILITY_PLAN status O3b→O5) |

## Open / next
- **O6** (LATER) — multi-hop per-node tracing for `rag/agent.py` (LangGraph), `rag/crag.py`,
  `siem_triage.py`. The only observability item left.
- User-side: nothing pending — backend DSN set + verified; `SECURITY_STATUS_TOKEN` rotated
  (it was pasted in chat). Optionally note (A)/(B) in OBSERVABILITY_PLAN.md (not yet done).
- Still parked: R5 authed testing, learn-from-edits Phase 1, R8 email alerts; key rotation E9/E10.

Related: [[feedback_llm_calls_ts_column]], [[project_sentry_error_reporting]],
[[reference_logging_spec]], [[project_llm_provider_status]], [[feedback_debug_first]],
[[feedback_status_claims_need_evidence]].
