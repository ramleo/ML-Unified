# Part 314 — observability O6 (agent span timing) + Page Inspector coverage

Continues [Part 313](Session_2026-10-09_ObservabilityO3bToO5_TsColumnBug_PerPageLogs_Part313.md).
2026-10-09. Closed the observability roadmap: shipped **O6** (per-node span timing for
the LangGraph agent), then a Q&A that pinned down exactly how broad the per-page error
log ((A) Page Inspector) really is.

Two through-lines:
- **O6 was wiring on an existing stream, not new infrastructure.** The agent already
  emitted `agent_step` SSE per node; O6 added *how long each node took* — no new table,
  no new sink. Scope was deliberately kept to live timing.
- **"Which pages are logged?" is answered by where errors are *captured*, not by the
  inspector.** The honest answer turned out to be "the whole website," and it took
  reading four files to say so with evidence instead of guessing.

---

## Arc 1 — stale-doc cleanup (`ML-Unified abc12a7`)
Session opened by noting (A) Page Inspector + (B) 4xx-body capture in
`OBSERVABILITY_PLAN.md` (they were only in the Part 313 log, not the roadmap). Docs-only.

## Arc 2 — O6: per-node agent span timing
Backend (`ML-Unified 3c2dbe0`, HF) + frontend (`ml-portfolio e4000e7`) + docs
(`ML-Unified 34b56a5`).

- **New `agent_spans.py`** — `SpanTimer` (`lap()` for the graph-stream loop where each
  update means a node just finished; `add()` for the web fallback + generate stream which
  run outside that loop) plus the shared `STEP_MAP`/`sse` moved out of `agent.py` so the
  step vocabulary and the timing live in one place.
- **`agent.py`** now emits `ms` on every live `agent_step` and a `spans:[{node,ms}]`
  breakdown on `done`, timing each graph node, the CRAG web fallback, and the generate
  stream. Stayed at 339 lines (under the 400 cap) by offloading to `agent_spans.py`.
- **Frontend** — the Agent Graph tile shows a total-ms badge + an ordered per-node
  breakdown (Route/Decompose/Retrieve/Web search/Grade/Rewrite/Generate), so the trace
  shows *where* latency went.
- **Verified live** on the Space (new code serving, not just RUNNING): a sample run read
  `routing 916 · decomposing 772 · retrieving 5304 · grading 770 · generate 1222` ms —
  retrieval dominated, exactly the attribution O6 exists to surface.

**Decisions:**
- **Live-only, no durable `agent_spans` table.** The generate call is already logged to
  `llm_calls`, and free-tier retention is short — a per-node history table would cost more
  than it's worth right now. (Offered as the heavier alternative; declined.)
- **`siem_triage.py` left alone.** It's a single LLM judge call — one span by nature,
  already in `llm_calls`. The roadmap over-scoped it as multi-hop; it isn't.
- **Modularize-first, enforced.** `useRagChat.ts` was **369 lines** (over the 350
  modularize-first threshold) — so before adding spans wiring I extracted the SSE
  event-dispatch into `ragSseHandlers.ts` (369 → 325). The extraction *is* where the new
  `spans` handling landed, so the rule produced a cleaner cut, not busywork.
- **Span-node → diagram-node aliasing.** Backend span names don't 1:1 the 5 diagram
  nodes: `generate`→`generating`, `websearch`→(retrieval phase), `decomposing`→(routing
  phase). The breakdown list names every span honestly rather than silently folding them.

## Arc 3 — how broad is the Page Inspector, really?
User asked how to test "logs per page" and whether it covers the whole site or a few
tools. Answered with evidence, not assumption, by tracing the capture path:

- **Frontend = site-wide.** Root `app/layout.tsx` mounts `<AnalyticsTracker />` on every
  page → `useAnalytics` registers global `window.error` + `unhandledrejection` listeners
  that POST to `/api/error` with `location.pathname` as the route. So any uncaught error
  on **any** page lands in `errors` → the Page Inspector. (One deliberate skip: routes
  containing "password".)
- **Backend = whole backend.** Every route through `error_capture_dispatch` logs 500s
  with route + trace id.
- **~6 tools enrich it.** text-to-sql, drift, optuna, multimodal-rag, document-intelligence
  and the RAG chat also call `trackRunError` for *handled* errors (e.g. an in-band stream
  error delivered inside a 200, which never throws to `window.onerror`). Enrichment on top
  of the global net, not the net itself.
- **Blind spot:** SSR/server-component render errors don't reach the browser `window`
  handler — they surface as backend/Vercel errors instead. No root `global-error.tsx`
  (only `tools/automl/error.tsx`), but uncaught *client* errors still fire `window.onerror`.

**Why an error log and not an access log** (asked explicitly): (1) page views already exist
as `page_view` analytics events + raw Vercel/HF request logs, joined by trace id — an
access log would duplicate them; (2) a row per request blows Supabase free-tier retention,
while errors are rare and high-value; (3) the content-free privacy posture logs what's
*wrong*, not every visit. The Inspector answers "what broke on this page," not "who visited."

## Testing recipe (handed to the user)
- Dashboard: `/tools/realtime-analytics` → teal **Page Inspector** tile → **set range to
  30d** (defaults to today; the only logged error is 2026-09-30, so "today" looks empty
  but isn't).
- API: `GET /api/error-detail?range=30d` (page picker) and `?route=/verify&range=30d`
  (one page's occurrences). Verified live — returned `/verify (1)`.
- Fresh end-to-end: `POST /api/error` with a labelled `TestError` + `x-trace-id` header →
  new route appears carrying the trace id. Safe (one content-free row; bumps the
  `frontend_errors` SLO count by 1, won't breach); cleanup is one `delete from errors`.

## Key decisions / lessons
- **Scope telemetry to value ÷ retention.** Live spans over a durable table when the
  expensive signal (the LLM call) is already persisted and retention is short.
- **The modularize-first rule can pay for itself.** The split demanded by the 350-line cap
  was exactly where the new feature belonged.
- **Answer coverage questions from the capture path, not the reader.** "Which pages are
  logged" is decided by `AnalyticsTracker` in the root layout, not by the inspector tile.
- **Name an over-scoped roadmap item down.** `siem_triage` as "multi-hop" was wrong; a
  single judge call is one span.

## Commits
| Repo | Commits |
|---|---|
| ML-Unified | `abc12a7` ((A)/(B) roadmap note) · `3c2dbe0` (O6 backend, HF) · `34b56a5` (O6 docs — roadmap complete) |
| ml-portfolio | `e4000e7` (O6 frontend: spans in trace UI + `ragSseHandlers.ts` extraction) |

## Open / next
- **Observability roadmap O1–O6 complete.** Nothing left on it.
- Still parked (external prereqs): R5 authed testing, learn-from-edits Phase 1, R8 email
  alerts (Resend); user-side key rotation E9/E10.

Related: [[project_sentry_error_reporting]], [[feedback_llm_calls_ts_column]],
[[reference_logging_spec]], [[feedback_debug_first]], [[feedback_file_length]].
