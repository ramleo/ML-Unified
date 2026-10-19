# Part 324 — Q4 eval dashboard (M1) + Q2 MCP verified + Q3 M1 (chatbot foundation)

Continues Part 323 (same day, 2026-10-19).

## Q4 — LLM evaluation platform (M1 shipped)

Decision (AskUserQuestion): **performance & cost dashboard first** (no new LLM
spend), **owner-gated `/eval`**.

- **`/api/eval`** (owner-gated, service-role read) aggregates the existing
  `llm_calls` log over a window → totals (calls, success rate, p50/p95 latency,
  tokens, cost) + breakdowns by **tool / provider / model / status** + a **daily
  series**. No new LLM spend, no schema change (reuses the O3 cost/token columns).
- **`/eval` page + `EvalDashboard.tsx`** — stat tiles, a stacked ok/error
  calls-per-day chart, per-category magnitude bars, 7/30/90-day toggle. Status-red
  reserved for errors (dataviz). Profile menu → "LLM metrics"; proxy gates `/eval`.
- Reused what already existed: public `/api/llm-stats` (lighter per-provider view)
  and the O3 telemetry columns.
- Frontend-only. Commit **`3a509f8`** (ml-portfolio). Verifies on deploy (reads real
  `llm_calls`; couldn't exercise locally without owner login).
- **Next:** M2 offline golden-set + LLM judge (bounded cost), M3 online sampling
  (tail-based).

## Q2 — live MCP handshake + a real bug fixed

Ran a real FastMCP **client** against `https://wram1708-ml-unified.hf.space/mcp/`
with an `ak_live_` key.

- **Bug found:** first call returned **500** (auth passed — not 401). Reproduced
  locally with a mock verifier; the error was `'AccessToken' object can't be
  awaited`. Root cause: `ApiKeyVerifier.verify_token` was **synchronous**, but
  FastMCP `await`s it. (401 without a key worked because the verifier isn't called
  when there's no token.)
- **Fix:** made `verify_token` **async** and run the blocking key-verify via
  `asyncio.to_thread`. Local repro confirmed: async verifier → `initialize` 200.
  Commit **`e42727b`** (+ HF upload of `mcp_server.py`; fast rebuild, no dep change).
- **Verified live (full handshake):** initialize + tools/list OK (advertises
  `tls_headers_check`, `email_auth_check`, `anomaly_detection_score`); calling
  `tls_headers_check` returned a real result; a **bad key is rejected** (MCPError).
- This closes the "handshake TODO" noted in Part 323. **Q2 M1 complete.**
- Lesson: FastMCP's `TokenVerifier.verify_token` must be `async def` even though the
  introspected signature doesn't show it.

## Q3 — Multi-tenant chatbot builder (M1 shipped)

Decision (AskUserQuestion): **Supabase pgvector** for the per-tenant KB (chosen over
Chroma because the Space disk is ephemeral), and a **thin end-to-end slice** (backend
only, one hardcoded tenant, no UI) to prove isolation before building the builder.

- **Isolation (the hard part):** `ml-portfolio/supabase/tenants.sql` — `pgvector`,
  `tenants` + `tenant_chunks` (384-dim MiniLM) + `match_tenant_chunks(tenant_id, …)`
  that filters on `tenant_id`. RLS on, **no policies → service-role only**.
- **Boundary preserved:** frontend owns the control plane (holds the Supabase service
  role); the **Space stays stateless compute** — `routers/tenant_rag.py` adds
  `/internal/tenant/embed` (reuses the already-loaded MiniLM model) and
  `/internal/tenant/answer` (Cohere), both gated by `TENANT_INTERNAL_TOKEN`
  (`x-internal-token`), fail-closed. **No Supabase key on the Space.**
- **Frontend (owner-gated):** `/api/tenants` (create/list), `/api/tenant/ingest`
  (chunk → embed → store tagged `tenant_id`), `/api/tenant/query` (embed →
  tenant-scoped match → answer from only those chunks). Helper `lib/tenant/rag.ts`.
- **Commits:** ml-portfolio **`f4612ac`**, ML-Unified **`946a0d8`** (+ HF upload of
  `app.py` + `routers/tenant_rag.py`; no new dep, `routers/` copied wholesale so no
  Dockerfile change). Deploy verified: new endpoint flipped **404 → 401** at ~3.5 min
  (router mounted, fail-closed).
- **Isolation live-verified** on the real durable store (direct service-role script):
  gave tenant A a chunk whose embedding *exactly* equals the query (global nearest
  neighbour), then searched as tenant B with that same vector → B got only its own
  chunk (sim −1.000), **never A's secret**. A searching its own KB found it (sim 1.000).
  Test tenants cleaned up. → **cross-tenant leakage is structurally impossible.**
- **Setup (one-time):** run `tenants.sql`; set `TENANT_INTERNAL_TOKEN` in **both**
  Vercel and HF (same value).
- **Remaining:** M2 builder UI + generalize to N tenants; M3 embed widget (loader +
  sandboxed iframe + public-key→short-lived JWT + per-tenant origin/cost/rate limits);
  M4 reseller billing (Stripe Connect). `tenant_id` must come from auth/JWT, never user
  input. ~60–70% RAG engine reused later for richer retrieval (rerank/BM25/citations).

## Housekeeping
- A key was pasted in chat for testing → asked the user to revoke it.
- Roadmap/memory updated: Q5 ✅, Q1 ✅, Q2 M1 ✅, Q4 M1 ✅, **Q3 M1 ✅.**
- **PRD refreshed** (`docs/prd/05-roadmap-extensions.md`): Q3 M1 section added; stale
  top banner ("plans only") and summary-table rows updated to current statuses.
- **New docs committed** (ML-Unified, public): `docs/README.md` — a documentation map
  (core vs access/security vs per-subsystem, with a fastest-path reading order; commit
  **`f3c6175`**); `docs/LOGGING_OVERVIEW.md` — one map of the seven log stores, was an
  untracked leftover, confirmed secret-free and committed (**`00ee1cf`**).

## State of the roadmap
Q5 ✅ · Q1 ✅ · Q2 M1 ✅ · Q4 M1 ✅ · **Q3 M1 ✅** (multi-tenant chatbot foundation;
M2 builder UI → M3 embed → M4 billing remain).
Deferred: Q2 OAuth/resources/prompts/more-tools; Q4 M2/M3 quality scoring.
