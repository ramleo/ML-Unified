# Observability — plan & roadmap

**Status:** proposed 2026-10-08; §7 decisions made 2026-10-08. **O1 + O2 shipped
(O1 verified live); O3 complete (O3a frontend + O3b backend LLM telemetry, 2026-10-09);
O4 code shipped 2026-10-09 — backend Sentry events now carry the trace id; the one
remaining step is user-side: set the `SENTRY_DSN` Space secret to activate capture.
O5 is next.** Builds on what already ships:
Sentry (errors), the DIY error store, the Supabase analytics dashboard, and
`docs/LOGGING_SPEC.md` (the single source of truth for what the site logs — any change
here changes that file and the privacy page too).

Through-line: **we already have two of the three pillars in partial form; the missing
one is correlation.** The value of observability is not more dashboards — it is being
able to follow one user action from the browser, through the Next API route, into the HF
Space, down to the LLM provider, as a single linked story. That spine (a trace id) is
what we lack, and most of it is cheap to add on tooling we already pay nothing for.

---

## 1. What observability is (the 2025 consensus)

Three signal types, correlated by a shared id — the correlation is the product, the
pillars are just storage formats:

- **Metrics** — time-series numbers: request rate, error rate, latency percentiles. Cheap
  to store, good for alerting on SLO burn.
- **Logs** — timestamped structured events, the richest context, the signal of last resort.
- **Traces** — a tree of spans across service boundaries, linked by a trace id.

Modern practice adds **RUM** (real-user monitoring: Core Web Vitals — LCP, INP, CLS),
and, for AI apps, **LLM observability**: every model call a span carrying provider, model,
token counts, dollar cost, latency and a quality/eval score, under the **OpenTelemetry
GenAI semantic conventions** so the keys are portable across any backend.

Sources: [Three pillars (OneUptime, 2025)](https://oneuptime.com/blog/post/2025-08-20-three-pillars-of-observability-logs-metrics-traces/view),
[Observability fundamentals (Guance, 2026)](https://www.guance.com/learn/articles/observability-fundamentals-guide),
[OTel LLM observability](https://opentelemetry.io/blog/2024/llm-observability/),
[LLM monitoring with OTel (Grafana)](https://grafana.com/blog/ai-observability-llms-in-production),
[GenAI semantic conventions (OneUptime docs)](https://oneuptime.com/docs/telemetry/ai-llm-observability).

## 2. Can we apply it here? Yes — and partly already is

The site is an LLM-heavy, multi-tier app (browser → Next API routes on Vercel → two HF
Spaces → LLM providers), which is exactly the shape observability is for. We already run
error tracking and content-free product analytics. The gap is tracing/correlation, RUM,
latency/SLOs, and first-class LLM-call telemetry. All of it can be added **without a new
paid vendor** — see §4.

## 3. What we already have (inventory)

| Pillar | Have today | Where |
|---|---|---|
| **Errors** | Sentry (frontend, **errors only**) + DIY error store (Supabase `errors` + `error_groups` RPC + the AnalyticsErrors panel) + `providerAlert.ts` auth-failure rows | `src/sentry.*.config.ts`, `src/app/api/error/route.ts`, `src/lib/providerAlert.ts` |
| **Logs** | The LOGGING_SPEC vocabulary events → Supabase (client wiring complete); backend `security/events.py` + `error_reporting.py` | `src/lib/logEvents.ts`, `docs/LOGGING_SPEC.md` |
| **Metrics (partial)** | Realtime Analytics dashboard — usage counts, `llm_calls`, events; budget caps + per-IP/route rate limits enforced | `realtime-analytics`, `src/lib/analytics*.ts` |
| **Traces** | **none** — `tracesSampleRate: 0` both ends; no trace id crosses tiers | — |
| **RUM** | **none** — no Web Vitals; Session Replay deliberately off (privacy) | `src/instrumentation-client.ts` |
| **LLM obs (partial)** | provider/cascade logged; auth-failure alerts; daily budget caps | `providerAlert.ts`, backend cascades |
| **Synthetic/uptime (partial)** | Testwright R8 monitors re-run saved tests on a schedule | `QA_*` / `ml-qa-runner` |

## 4. Gaps vs best practice, and the stance on each

1. **No correlation id across tiers** — the biggest gap. One click can touch 3–4 services
   and nothing links the rows. *Fix: O1.*
2. **No RUM / Web Vitals** — we can't see real users' LCP/INP/CLS. *Fix: O2.*
3. **No latency percentiles / SLOs / burn-rate alerts** — only counts today. *Fix: O3, O5.*
4. **LLM telemetry incomplete** — no per-call token/cost/latency/quality span, no GenAI
   semconv, no multi-hop tracing of the two real agents (`rag/agent.py` LangGraph,
   `rag/crag.py`). (This is Part 310 Arc 5's finding.) *Fix: O3, O6.*
5. **Backend blind spots** — `error_reporting.py` is a no-op until `SENTRY_DSN` is set, and
   HF Space logs are an ephemeral buffer wiped on every upload/restart. *Fix: O4.*

**Design stance (not a vendor commitment — see §7):** do **not** add a paid APM
(Datadog/Honeycomb). Build on what costs nothing and we already run — **Sentry's free tier**
(its Performance/tracing, Web Vitals and LLM-monitoring features are available there) plus
**Supabase** as the metrics store. Shape all new telemetry to **OpenTelemetry GenAI
semantic conventions** so the keys are portable if we ever move to Grafana Cloud's free
tier or self-host. That gives the vendor-neutral benefit OTel is prized for without paying
for or locking into a vendor now.

**Constraints that shape everything below:** Vercel Hobby + free HF Spaces + Supabase free
(short retention, no always-on collector); HF disk is ephemeral; the privacy posture is
content-free telemetry and no Replay — any new signal stays content-free and updates the
privacy page.

## 5. Roadmap

Ordered by value ÷ effort. Tiers: **NOW** (no blocker) · **NEXT** · **LATER**.

| # | Tier | Item | Why | Effort |
|---|---|---|---|---|
| **O1** | NOW | ✅ **shipped + verified live 2026-10-08.** Correlation id across tiers. The per-run id `trackedFetch` already mints now rides `x-trace-id` to the backend (FE `b02df24`); `security/trace.py` middleware captures/echoes it and stamps it on 500s (`errors.meta.trace_id`, no migration) + the request log (BE `fd43ea4`, HF live — echo verified both paths). Next API routes read it onto their error logs + a Sentry tag (`2cb0486`). **Remaining for O3:** a real `trace_id` column on `llm_calls` (deferred with that table's per-call growth). | The correlation spine — turns 4 disconnected rows into one story. No vendor needed; pure plumbing on existing logging. | S–M |
| **O2** | NOW | ✅ **shipped 2026-10-08 (FE, pending DSN verify).** `tracesSampleRate` 0 → 0.1 on the client (`instrumentation-client.ts`): the default `browserTracingIntegration` records a sampled pageload/navigation transaction and attaches Core Web Vitals (LCP/INP/CLS/FCP/TTFB). Replay stays off; `beforeSendTransaction` strips query strings; privacy page updated. Server tracing left at 0 — deferred to O4 with the outbound trace-propagation decision. | Real-user performance we are blind to today; cheap, already-installed SDK. | S |
| **O3** | NEXT | ✅ **O3a shipped 2026-10-08 (frontend).** Every server-key LLM call in `chat`, `ai-explain`, `ai-tools` logs one `llm_calls` row — provider, model, input/output tokens, estimated cost, latency, outcome — joined by `run_id` (= trace id). `lib/llmTelemetry.ts` (per-provider usage extractor + dated price table + `recordLlmCall`); migration `llm_calls_o3.sql` (run live); dashboard panel `AnalyticsLLMPanel` + `/api/llm-stats` (cost, success rate, tokens, p95, per-provider). BYOK calls not logged (caller's spend). **O3b (backend) shipped 2026-10-09:** `call_log.record_call` now carries input/output tokens, estimated cost (price table mirrored from `llmTelemetry.ts`) and `operation`, and falls back to O1's `current_trace_id()` for `run_id` at the funnel — so every backend LLM call joins the same spine with no per-site change. Usage captured for Claude (`get_final_message().usage`), Gemini + Cohere (from the SSE already parsed); Groq/OpenAI-compat skipped (would need `stream_options`, and they're free → $0). The Vercel `/api/llm-log` sink now persists the four new fields. | Closes the LLM-obs gap; makes cost and provider health visible; builds directly on `providerAlert.ts` + `llm_calls`. | M |
| **O4** | NEXT | ✅ **code shipped 2026-10-09; one user-side step left.** Backend Sentry events now carry the trace id: `error_capture_dispatch` sets a `trace_id` tag while the trace contextvar is still live — it must be set here, not in `before_send`, because the trace middleware is outer and its `finally` resets the contextvar before the exception reaches Sentry's outer auto-capture. So a Sentry 500 pivots to the same frontend action as the DIY-store row (which already carried the id via O1). **Remaining (user-side):** set the `SENTRY_DSN` Space secret — `init_error_reporting()` is a no-op until then, so backend Sentry capture stays dormant. Keeps evidence off the ephemeral disk. | Removes the backend blind spot that LOGGING_SPEC exists to fight; low effort once the DSN is set. | S |
| **O5** | NEXT | **SLOs + burn-rate alerts.** Define 3–4 SLOs (API route availability, LLM success rate, p95 latency) as Supabase views + a dashboard tile; alert via the existing `providerAlert` dedup pattern. | Moves from "counts" to "are we meeting a target"; alert on burn, not raw thresholds. | M |
| **O6** | LATER | **Multi-hop tracing for the real agents.** Per-node spans for `rag/agent.py` (LangGraph), `rag/crag.py`, `siem_triage.py` (retrieve → rerank → generate → verify), surfaced in the existing MMRAG-08 trace panel. | The only genuinely multi-step flows (Part 310 Arc 5); single-call tools don't need it. | M–H |

**Suggested first slice:** O1 then O2 — together they give end-to-end correlation plus
real-user performance on tooling we already run, no new vendor, no cost. O3/O4 next.

## 6. Inherent limits (stated, not hidden)

- **Telemetry only shows what is instrumented** — a behavior with no span/log is invisible,
  the same floor as the doc-coverage check. Observability narrows the dark, it doesn't
  remove it.
- **Free-tier retention is short** — Sentry/Supabase free tiers cap history; durable
  long-term analysis still means rolling our own summary rows (as the analytics dashboard
  already does).
- **Sampling hides rare events** — a 0.1 trace sample will miss some. Errors are always
  captured; traces are sampled for cost.

## 7. Decisions (made 2026-10-08)

1. **Vendor — Sentry free tier + Supabase (the stack already in use).** No new account,
   no cost, no lock-in: Sentry's free tier already carries tracing, Web Vitals and LLM
   monitoring; Supabase is already the metrics store. All new telemetry is shaped to OTel
   GenAI semconv keys so a later move to Grafana Cloud free or self-host needs no
   re-instrumentation. Rejected: Datadog/Honeycomb (paid, overkill) and self-host
   (infra + security burden on a free public site).
2. **Sampling — errors 100%, traces 10% (`tracesSampleRate: 0.1`), LLM spans 100%.**
   Errors are rare and always kept; 10% traces is the standard start (enough for patterns
   and p95, cheap on free-tier quota — tune up if traffic is low); LLM calls are captured
   in full because they are low-volume, high-value, and the cost/token figures are only
   trustworthy if complete.
3. **Backend `SENTRY_DSN` — set it (O4).** Already wired (`error_reporting.py` is a no-op
   only because the DSN is blank), so it is a one-variable change that lights up backend
   error capture and lets O1's trace id link a Space failure back to the frontend action —
   closing the ephemeral-HF-log blind spot LOGGING_SPEC exists to fight. Same Sentry
   project as the frontend is fine (simpler); a second project is optional.

Standing: telemetry stays **content-free** and **Session Replay stays off** (privacy);
any new signal updates the privacy page.

Related: `docs/LOGGING_SPEC.md`, `docs/ERROR_TRACKING.md`,
`Session_2026-10-04_…_Part310.md` (Arc 5 — where agent observability applies).
