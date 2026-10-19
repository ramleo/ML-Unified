# Part 324 — Q4 eval dashboard (M1) + Q2 MCP handshake verified

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

## Housekeeping
- A key was pasted in chat for testing → asked the user to revoke it.
- Roadmap/memory updated: Q5 ✅, Q1 ✅, Q2 M1 ✅, Q4 M1 ✅; **Q3 remains.**

## State of the roadmap
Q5 ✅ · Q1 ✅ · Q2 M1 ✅ · Q4 M1 ✅ · **Q3 (multi-tenant chatbot builder) — not started.**
Deferred: Q2 OAuth/resources/prompts/more-tools; Q4 M2/M3 quality scoring.
