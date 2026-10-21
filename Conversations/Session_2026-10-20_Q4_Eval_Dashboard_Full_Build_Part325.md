# Part 325 — Q4 eval dashboard: full build + hardening (2026-10-20)

Continues Part 324 (Q4 M1 + Q2 MCP verified + Q3 M1). This day turned the owner
`/eval` dashboard from M1 into a near-complete LLM-observability + quality product,
and fixed a run of CI and UI bugs along the way. Everything frontend is ml-portfolio;
backend is the HF Space (`wram1708/ml-unified`).

## "By tool" was all `unknown` — and the ContextVar/threadpool lesson
- **Root cause:** backend LLM rows logged `tool=""` because `set_call_context(tool=…)`
  was only called in `contradictions.py`. First cut tagged RAG + standalone tools via a
  ContextVar (`c030894`, `0d8e0f7`). **It didn't work for the main answer:** FastAPI
  drains a `StreamingResponse` generator across **thread-pool threads**, so a
  `ContextVar.set()` inside the generator never reaches the thread where the stream's
  row fires. Proven live (streamed cohere row still `tool=""`).
- **Fix (`dbb9cdd` +HF):** thread `tool` **explicitly** `stream_with_fallback →
  open_stream → stream_* → instrument → record_call` (ContextVar kept as fallback for
  synchronous callers). Verified live: streamed row tagged. Lesson saved:
  [[project_llm_calls_tool_tagging]]. **session_id/run_id have the same latent loss.**

## CI was red (pre-existing) — cleared
- **file-length:** `scripts/build-handbook.py` was 434 lines → split helpers into
  `scripts/handbook_render.py`, byte-identical output (ml-portfolio `115ff9f`).
- **e2e:** red since the Docker commit — CI builds `output:standalone` (no VERCEL) but
  Playwright runs `next start` (can't serve standalone), and the job had no Supabase
  env. Fixed: opt out of standalone when `NEXT_E2E=1` + dummy Supabase env in the e2e
  job (`c62c1b1`); verified 78/78 locally.
- **secret-scan regression:** the dummy `NEXT_PUBLIC_SUPABASE_ANON_KEY` tripped
  gitleaks' generic-api-key. Shortened it + added `.gitleaks.toml` allowlist for the
  historical commit; verified with the real gitleaks binary (`057bf6d`).
- Lesson saved: [[feedback_check_ci_after_push]] — check `gh run` after every push;
  verify deploys end-to-end, not from compile alone.

## Q4 M2 — offline quality scoring (golden set + LLM judge)
- Versioned golden set (`routers/eval_golden.py`) scored by a **Gemini judge**
  (different family from the Cohere generator) on anchored binary C/F/R criteria, with
  free `score_groundedness` as a pre-signal. Owner clicks **Run** on the Quality
  section → `/api/eval/run` creates the `eval_runs` row + asks the Space
  (`/internal/eval/run`, internal-token gated) to score in a background thread → posts
  to `/api/eval/ingest` (Space→Vercel callback like `call_log`; **no Supabase key on
  the Space**). `supabase/eval.sql` = `eval_runs` + `eval_scores` (service-role only).
  Commits ml-portfolio `d7dc426`, ML-Unified `2b984bd` (+HF).
- **First baseline revealed real signal + a harness artifact:** v1 used a `Tool: Eval`
  context that made the chat call itself "the Eval tool" and decline site questions.
  Switched to a neutral AIRaML-website-assistant context → `rag_v2`; now the chat
  *answers* site questions — and the low score exposed that it **confabulates when the
  KB lacks content**. That motivated the KB fix below.
- **Multi-model eval** (`3188234`/`1ce6e17`): a picker runs the set through any app
  model (Cohere/Gemini/Mistral); `eval_runs` gains `gen_provider`/`gen_model`.
- UI fixes along the way: progress bar appears instantly/indeterminate
  (`c577803`/`f0d1c81`, `44d331b`); show newest run so the bar shows (`6ad2834`);
  button tracks the started run (`eeecc2a`); pass-rate trend only for same-version runs
  (`99448a7`); per-item model dropdown (`353952d`, `/api/eval/scores`).

## RAG KB now ingests the handbook
- The public RAG KB (`data/knowledge_base/`) held only ML-theory docs → site/feature
  questions had nothing to retrieve. `scripts/sync_handbook_kb.py` strips the handbook's
  HTML and splits it into 72 per-chapter files under `data/knowledge_base/handbook/`;
  startup ingest indexes them. Live-verified a site answer now cites a handbook chapter.
  Commit `c3150bf` (+HF folder). [[project_rag_kb_handbook]]

## Navbar profile load — localStorage wasn't enough, SSR was
- The avatar was fetched entirely client-side (`/api/me` after hydration), blanking on
  every load. localStorage + placeholder (`1cbfe45`) only removed the network wait
  **after** hydration — the avatar still wasn't in the SSR HTML (confirmed by fetching
  the live page). **Real fix (`0bd72ec`):** the root layout reads a non-sensitive
  `airaml_me` cookie (kept fresh by NavAuth) and seeds an `IdentityContext`, so the
  avatar renders in the server HTML. Lesson updated in [[feedback_no_content_flicker_on_nav]].

## Dashboard expansion + 3D + model comparison
- **Section layout** (Overview/Volume&cost/3D/Breakdowns/Answer quality/RAG health/
  Errors), **token-split + p99** tiles, **drill-down + top-errors + traces**, cost/
  latency trend lines + period deltas, groundedness column.
- **Live RAG health** (`5d1bb9c`, `a7ad088` +HF): Space logs one content-free row per
  query (`routers/rag/rag_log.py` → `/api/rag-log` → `rag_queries`); `/api/eval/rag`
  → cache-hit rate, answer-source mix, groundedness drift, low-confidence/web-fallback.
- **3D call explorer** (`04881a4`): react-three-fiber scatter (latency×tokens×cost).
  **Slow ≠ download:** the 1.1 MB (~350 KB gz) wasn't the issue — the scene built ~800
  WebGL objects (400 spheres + 400 drei `<Line>`), stalling on mount. Collapsed to one
  instanced mesh + one line buffer (`ecd24f5`); made it opt-in (load-on-click); added a
  reset-view button + a data-driven read-out + a dynamic axis description.
- **Model comparison** (`c477f22`, `e608dd9`): Bars / Lines / Radar / Quality-vs-speed
  scatter.

## Portkey-inspired items (all three)
- **Budget panel** (`/api/eval/budget`, `EVAL_MONTHLY_BUDGET_USD`) + **per-request
  traces** (`/api/eval/trace`, llm_calls by run_id) — `ea52d5c`.
- **User feedback** 👍/👎 on chat answers → `answer_feedback` via `/api/feedback`
  (content-free, gated like analytics), read by `/api/eval/feedback` — `1c35c8a`.
- **In-dashboard guide** modal (`d4524c7`) explaining every section.
- Researched Portkey's analytics (observability page) for the feature set; borrowed
  traces + feedback + budget.

## Housekeeping
- **Setup the owner must run (one-time SQL):** `supabase/eval.sql`,
  `supabase/rag_queries.sql`, `supabase/answer_feedback.sql`. Optional env
  `EVAL_MONTHLY_BUDGET_USD` (default $10). No new secrets.
- **Docs refreshed:** PRD `docs/prd/05-roadmap-extensions.md` Q4 section updated to the
  full current state (fixed the stale "~40–50% / missing store-runner-dashboard" line);
  handbook is auto-generated (CI-enforced) and owner-only `/eval` isn't in it by design.
- Memory updated: [[project_platform_roadmap]], [[project_llm_calls_tool_tagging]],
  [[project_rag_kb_handbook]], [[feedback_check_ci_after_push]],
  [[feedback_no_content_flicker_on_nav]].
- A test API key pasted in chat earlier still needs revoking (owner action).

## State of the roadmap
Q5 ✅ · Q1 ✅ · Q2 🚧 M1 · **Q4 🚧 M1+M2** (+ live RAG health, model compare, 3D,
budget, traces, feedback; **M3 tail-based online judge-scoring remains**) · Q3 🚧 M1
(M2 builder UI → M3 embed → M4 billing remain). Lessons this day: ContextVars don't
cross FastAPI's streaming threadpool; a first-paint gap must be closed in the server
render; 3D "slowness" was scene construction, not bytes; check CI after every push.
