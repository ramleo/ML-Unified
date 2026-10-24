# TC-P19 — Parts 320–330

**Prefix:** TC-P19
**Parts covered:** 320–330 (11 sessions)
**Status:** ✅ Complete
**Method:** Inline — no subagents; full line-by-line re-read of all session logs (Part 330 incl. its same-day follow-up round).

Covers: the ClamAV/hybrid-gate/durable-rate-limit security hardening; the full platform-roadmap arc — **Q5 auth** (+ auth-UX, avatars), **Q1 public API**, **Q2 MCP** (M1 + M2 expanded surface), **Q4 eval platform** (M1→M3, dashboard, online judge), **Q3 chatbot builder** (M1 isolation → M4b Stripe billing + embed widget); plus site-search, homepage-chat starter chips, the tool-header fix, and the homepage-chat grounded-RAG rework and its copy/links/context + upload-affordance follow-up.

---

## Security Hardening (Part 320)

### TC-P19-001
**Category:** Feature
**Test Name:** ClamAV deep-scans uploads; the gate is hybrid fail-closed/enforce-once-ready
**Steps:**
1. Upload EICAR, a benign 30MB doc, and a 55MB doc; check `/health`.
**Expected Result:** EICAR→400, 30MB→200, 55MB→413; `gate_or_raise` runs **YARA mandatory/fail-closed** (in-process; can't-run→503) + **ClamAV enforced once `clamd.ping()` is ready** (warmup falls back to YARA); `/health` reports `clamav.reachable` + DB revision. 50MB cap set in BOTH `body_size._ROUTE_CAPS` and `MAX_FILE_BYTES`.
**Automation Hint:** API tests + health probe.
**Source:** Part320 (`5a415e5`/`a3a4644`)

### TC-P19-002
**Category:** Feature
**Test Name:** Durable cross-instance rate limit (DB-backed, fails open)
**Steps:**
1. Hit the audit route past the cap across instances.
**Expected Result:** `rate_limit_hit(bucket, ip_hash, max, window)` (salted IP HMAC via `AIRAML_LOG_TOKEN`) flips `true,true,true,false,false` at cap 3; mirrors the existing `log_security_event` limiter (no new vendor); fails open if the SQL isn't applied.
**Automation Hint:** rate-limit function test.
**Source:** Part320 (`e00dc65`)

### TC-P19-003
**Category:** Architecture
**Test Name:** Verify a daemon with a probe, not a log-grep; a grep hit is a lead
**Steps:**
1. Confirm ClamAV's DB downloaded; re-check a flagged `dangerouslySetInnerHTML`.
**Expected Result:** `--quiet` hid freshclam and clamd logs to a file, so the `/health` probe is the durable proof; the XSS "finding" was withdrawn after reading all three usages (theme script hardcoded, `mdToHtml` escapes-first, map SVG first-party) — read the impl before claiming a bug.
**Automation Hint:** none (method).
**Source:** Part320

---

## Q5 Auth + Auth-UX + Avatars (Parts 321–322)

### TC-P19-004
**Category:** Feature
**Test Name:** Auth model — public tools, user home, owner portfolio, recruiter share-link
**Steps:**
1. Visit as anon, a user, the owner, and via `/r/<token>`.
**Expected Result:** Tools need no login; a user → signed-in homepage; owner (identity = `OWNER_EMAIL` env, not a DB role) → `/portfolio`; recruiters view via a secret, expiring, revocable share-link, no login. Supabase Auth (`@supabase/ssr`), gate in `src/proxy.ts`.
**Automation Hint:** per-role route checks.
**Source:** Part321 (`d011b8c`/`0ef53d9`)

### TC-P19-005
**Category:** Feature
**Test Name:** Owner-aware profile menu without leaking OWNER_EMAIL
**Steps:**
1. Sign in; open the avatar dropdown.
**Expected Result:** Avatar (initials) → menu with identity header (email + role), owner-only items, Account/Settings/Sign out (a menu item); `/api/me` returns `{email,role,avatarUrl,isOwner}` so the client is owner-aware without `OWNER_EMAIL` reaching the browser; owner lands on `/`.
**Automation Hint:** dropdown + `/api/me` test.
**Source:** Part322 (`53c55ac`)

### TC-P19-006
**Category:** Bug-Regression
**Test Name:** Avatar upload can never change role; no flicker on nav
**Steps:**
1. Upload an avatar; navigate between pages.
**Expected Result:** `/api/avatar` writes `avatar_url` via the service-role key (profiles has no self-UPDATE policy, so upload can't touch `role`); navigation uses `next/link` + an in-memory identity cache (was `<a>` full-reload → avatar blanked); later SSR-seeded from an `airaml_me` cookie so it's in the server HTML.
**Automation Hint:** upload + nav assertions.
**Source:** Part322 (`9f851ee`/`94376a3`) / Part325 (`0bd72ec`)

### TC-P19-007
**Category:** Feature
**Test Name:** Revocable lists hide revoked + toggle + permanent delete + pending state
**Steps:**
1. Revoke an API key and a share-link.
**Expected Result:** Both panels: revoked hidden behind "Show revoked (N)", permanent Delete, per-row "Revoking…/Deleting…" — applied to ALL such lists at once. `feedback_revocable_list_pattern`.
**Automation Hint:** revoke/delete UI test.
**Source:** Part322 (`45eaf93`/`4961a83`)

### TC-P19-008
**Category:** Feature
**Test Name:** Q1 public API — keys stored as hash, every call verified, Space holds no DB key
**Steps:**
1. Mint a key at `/portfolio/keys`; call `/v1/tls-headers/check` without/with it.
**Expected Result:** `api_keys` stores only SHA-256 hash + prefix (RLS service-role); `require_api_key` verifies EVERY request via token-gated `/api/keys/verify` (quota/budget/revoked/expiry; fail-closed if the token is unset) — the Space holds no Supabase key; 401 without a key, 200 with; `/v1/openapi.json` ungated.
**Automation Hint:** API tests + metering.
**Source:** Part322 (`34e1845`/`15ee2ea`/`3949634`)

---

## Q2 MCP (Parts 323–324, 328)

### TC-P19-009
**Category:** Feature
**Test Name:** MCP server mounts on the Space, reuses Q1 keys as Bearer
**Steps:**
1. POST `/mcp/` without and with a valid `ak_live_` key.
**Expected Result:** FastMCP 4.1.1 over Streamable HTTP; `ApiKeyVerifier` validates via the same `/api/keys/verify` (one key for REST + MCP); combined lifespan, mounted last; `/mcp` 307-redirects to `/mcp/`; `/health` 200 (main backend unaffected). Dockerfile `COPY mcp_server.py`.
**Automation Hint:** MCP handshake test.
**Source:** Part323 (`8f65b27`)

### TC-P19-010
**Category:** Bug-Regression
**Test Name:** `verify_token` must be async (FastMCP awaits it)
**Steps:**
1. Full MCP handshake with a valid key.
**Expected Result:** `initialize` + `tools/list` 200 — `ApiKeyVerifier.verify_token` is `async def` (blocking key-verify via `asyncio.to_thread`); a sync version gave 500 `'AccessToken' object can't be awaited` (401-without-key worked because the verifier isn't called with no token).
**Automation Hint:** live handshake.
**Source:** Part324 (`e42727b`)

### TC-P19-011
**Category:** Feature
**Test Name:** Q2 M2 — expanded MCP surface (6 tools + resources + prompts), curated
**Steps:**
1. Authed `tools/list`; read `airaml://handbook/{section}`.
**Expected Result:** 6 tools (added attack-surface, yara, prompt-injection with a heuristic fallback), resources (`airaml://tools`, `airaml://handbook` + section template with a path-traversal guard), 3 prompts; LLM-only no-fallback tools (ai-code, siem) and bulky-input intrusion excluded. Package named `mcp_ext/` (NOT `mcp/` — would shadow the SDK); `COPY mcp_ext/`.
**Automation Hint:** authed `tools/list` (only check that proves the count).
**Source:** Part328 (`4d18b21`)

### TC-P19-012
**Category:** Feature
**Test Name:** Groq added as a free fallback before the paid key (judge + document)
**Steps:**
1. Call the judge tools / document analyze when Cohere+Mistral 429.
**Expected Result:** cohere → mistral → **groq (`openai/gpt-oss-120b`, separate rate-limit pool)** for judges; document text cohere → groq → gemini; vision groq `qwen/qwen3.8-27b` → gemini (NOT strictly safe — a wrong-but-non-empty vision answer is used, a user-approved accuracy/cost trade). Read provider memory first (`llama-3.3-70b-versatile` is retired).
**Automation Hint:** cascade test with the first two stubbed.
**Source:** Part328 (`e1a5558`/`d29c310`/`bbaa457`)

---

## Q4 Eval Platform (Parts 324–327)

### TC-P19-013
**Category:** Feature
**Test Name:** Owner /eval dashboard aggregates llm_calls (no new LLM spend)
**Steps:**
1. Open `/eval`.
**Expected Result:** `/api/eval` (owner-gated) → totals + breakdowns by tool/provider/model/status + daily series over 7/30/90d from the existing `llm_calls` (O3 columns); gated in `proxy.ts`.
**Automation Hint:** dashboard integration.
**Source:** Part324 (`3a509f8`)

### TC-P19-014
**Category:** Bug-Regression
**Test Name:** The `tool` tag is threaded explicitly (ContextVar is lost across the streaming threadpool)
**Steps:**
1. Make a streamed RAG answer; check `llm_calls.tool`.
**Expected Result:** Tagged (not `""`) — `tool` threaded `stream_with_fallback → open_stream → stream_* → instrument → record_call`; a `ContextVar.set()` inside the `StreamingResponse` generator never reaches the thread the row fires on (session_id/run_id have the same latent loss). `project_llm_calls_tool_tagging`.
**Automation Hint:** streamed-row tool assertion.
**Source:** Part325 (`dbb9cdd`)

### TC-P19-015
**Category:** Feature
**Test Name:** Q4 M2 offline golden set scored by a cross-family judge
**Steps:**
1. Run the Quality section.
**Expected Result:** Versioned golden set scored by a Gemini judge (different family from the Cohere generator) on binary C/F/R; `/api/eval/run` → Space `/internal/eval/run` (internal-token) → background thread → `/api/eval/ingest` callback (no Supabase key on the Space); a neutral website-assistant context (`rag_v2`) fixed a harness artifact where the chat called itself "the Eval tool" and declined.
**Automation Hint:** eval run e2e.
**Source:** Part325 (`d7dc426`/`2b984bd`)

### TC-P19-016
**Category:** Bug-Regression
**Test Name:** The public RAG KB includes the handbook (site questions had nothing to retrieve)
**Steps:**
1. Ask the homepage chat a site/feature question.
**Expected Result:** Cites a handbook chapter — `sync_handbook_kb.py` strips the handbook HTML into 72 per-chapter KB files (startup ingest); previously the KB held only ML-theory docs so the chat confabulated. `project_rag_kb_handbook`.
**Automation Hint:** grounded-answer assertion.
**Source:** Part325 (`c3150bf`)

### TC-P19-017
**Category:** Efficiency
**Test Name:** The 3D call explorer's slowness was scene construction, not bytes
**Steps:**
1. Open the 3D explorer.
**Expected Result:** One instanced mesh + one line buffer (was ~800 WebGL objects — 400 spheres + 400 `<Line>` — stalling on mount); opt-in load-on-click; the 1.1MB bundle was never the issue.
**Automation Hint:** none (measurement).
**Source:** Part325 (`ecd24f5`)

### TC-P19-018
**Category:** Feature
**Test Name:** Q4 M3 online judge-scoring (reference-free, content-free, completes Q4)
**Steps:**
1. Serve real RAG answers; check the Online-quality panel.
**Expected Result:** Samples real answers — tail always (low-confidence or groundedness<0.5) + small random (8%) under a daily cap (200); a background thread has Gemini judge faithful+relevant→pass (no "correct", no reference); never blocks the response; POSTs ONLY the verdict (question/answer/context never stored). Needs `eval_online.sql`.
**Automation Hint:** online-judge sampling test.
**Source:** Part327 (`1cb09e7`)

---

## Q3 Chatbot Builder (Parts 324–327)

### TC-P19-019
**Category:** Architecture
**Test Name:** Tenant isolation is structural (pgvector filter + RLS service-role)
**Steps:**
1. Give tenant A a chunk equal to the query vector; search as tenant B with that vector.
**Expected Result:** B gets only its own chunk (never A's), A finds its own — `match_tenant_chunks(tenant_id,…)` filters on `tenant_id`, RLS on with no policies (service-role only); the Space stays stateless compute (`/internal/tenant/*`, `TENANT_INTERNAL_TOKEN`, no Supabase key). Cross-tenant leakage is structurally impossible.
**Automation Hint:** isolation test via service-role script.
**Source:** Part324 (`f4612ac`/`946a0d8`)

### TC-P19-020
**Category:** Feature
**Test Name:** Chatbot builder (owner UI, owner_id-scoped, platform-ready)
**Steps:**
1. Create a bot; configure persona/provider/model; paste KB; test.
**Expected Result:** `/portfolio/chatbots` (Configure/Knowledge/Test); `tenants.config` drives a config-aware `/internal/tenant/answer` (any allowlisted provider, grounding on top); everything scoped on `owner_id` so self-serve is a gate flip, not a rewrite (Option A).
**Automation Hint:** builder e2e.
**Source:** Part326 (`bdc7942`/`36e7161`)

### TC-P19-021
**Category:** Bug-Regression
**Test Name:** Every tenant LLM path has provider fallback (answer, suggest, complete)
**Steps:**
1. Rate-limit the bot's primary provider.
**Expected Result:** `_generate()` falls primary→others on all three paths (answer + suggestions + ghost-text), response names the provider used — a single hard dependency made the answer AND chips AND completion go dark when Cohere 429'd.
**Automation Hint:** outage test on all three paths.
**Source:** Part326 (`1a15597`)

### TC-P19-022
**Category:** Feature
**Test Name:** Embed widget — sandboxed iframe, preflight-free session mint, four controls
**Steps:**
1. Embed `<script data-bot="pk_…">` on an allowlisted vs non-allowlisted origin.
**Expected Result:** Loader mounts a sandboxed cross-origin iframe; mints the session as a **simple CORS request** (text/plain, no preflight — a preflight can't carry the key) so the server sees the real Origin → allowlist → HS256 JWT bound to `{tenant,origin}` → JWT-gated `/api/embed/query`; non-allowlisted origin refused. Hard backstops = rate limit + daily cap (`tenant_embed_charge`) + kill switch (origin check is weak alone).
**Automation Hint:** embed e2e both origins.
**Source:** Part327 (`9820e21`)

### TC-P19-023
**Category:** Feature
**Test Name:** Self-serve + Stripe billing (publish gated behind a paid plan)
**Steps:**
1. As a free user build a bot, try to publish, upgrade via Checkout, publish.
**Expected Result:** 8 tenant routes flipped owner-only→any signed-in user keeping `owner_id=user.id` scoping (audited every route); free can build/test (2 bots) but publish requires Pro; `profiles.plan` flipped ONLY by the signature-verified Stripe `/webhook` (raw `req.text()`, single source of truth); hosted Checkout/Portal (no card data touches us). Stripe Billing, not Connect (Connect = reseller payouts, M4c).
**Automation Hint:** plan/publish + webhook test.
**Source:** Part327 (`adcdd23`/`bcf058b`)

---

## Site Search, Chat Chips, Tool Header, Grounded Chat (Parts 329–330)

### TC-P19-024
**Category:** Feature
**Test Name:** Grounded site search — structured asks from real data, no hallucination
**Steps:**
1. Search "list tools", a free-form question, and "capital of France".
**Expected Result:** "list tools" → a 58-row table with links straight from `capabilities`+`registry.json` via `scoreCapability` (no model, can't invent); free-form reuses `/api/chat` RAG; off-topic → the fixed website-only message.
**Automation Hint:** search e2e for each path.
**Source:** Part329 (`dfef3e8`)

### TC-P19-025
**Category:** Feature
**Test Name:** Homepage chat starter chips — static instant + dynamic cached
**Steps:**
1. Open the homepage chat; click a chip.
**Expected Result:** Static per-section chips render instantly (zero cost, send on click via `sendText`); dynamic KB-derived chips from `/api/chat/suggest` swap in when ready, cached in-module 6h (one free call every few hours, not per visitor), fall back to static on failure.
**Automation Hint:** chip render + send + cache test.
**Source:** Part329 (`1d573e7`/`4feb738`)

### TC-P19-026
**Category:** Bug-Regression
**Test Name:** Tool header — breadcrumb trail on one line, no mid-word wrap
**Steps:**
1. Load a busy tool header (Feature Engineering) and a light one (JWT) at desktop + phone.
**Expected Result:** `ToolBackNav` renders a horizontal trail (one chevron, `Home › Area`), not two stacked back-links; `.tool-header-row` wraps-and-grows (overriding inline `height:60`) so a tight header breaks BETWEEN atoms, never inside; shared `RunsInBrowserBadge` (`nowrap`) replaces the inline pills. Fixed across ~50 tools from the shared pieces.
**Automation Hint:** header layout assertions + phone width.
**Source:** Part329 (`df11e42`)

### TC-P19-027
**Category:** Feature
**Test Name:** Homepage chat is grounded in the site RAG, copyable, website-only
**Steps:**
1. Ask "what does Testwright do?", "How can I upload a CSV?", "capital of France".
**Expected Result:** `/api/chat` proxies the Space's `/rag/query` (handbook-grounded, accumulates the SSE token stream); Groq pins `qwen/qwen3.8-27b`; off-topic declines because no source is a real KB file (all `web:` → website-only decline); transcript selectable with a per-reply Copy button.
**Automation Hint:** grounded + decline + copy checks.
**Source:** Part330 (`9411d0b`/`b17d979`)

### TC-P19-028
**Category:** Bug-Regression
**Test Name:** Chat follow-ups resolve against context; both bubbles copyable; links open new-tab
**Steps:**
1. Ask about preprocessing, then "give me the link to go"; copy your own message; click an internal link.
**Expected Result:** Copy button on BOTH user and assistant bubbles; internal paths/`[label](/path)` become `<a target="_blank">` links; a short/referential follow-up is resolved into a standalone retrieval query by prefixing the prior question (history aids GENERATION but not RETRIEVAL — a contextless follow-up embeds to the wrong KB chunks), so it retrieves `15-data-preprocessing.md` and returns `/tools/preprocessing`.
**Automation Hint:** follow-up + copy + new-tab assertions.
**Source:** Part330 (`4ae9d1e`/`da772d6`)

### TC-P19-029
**Category:** Bug-Regression
**Test Name:** File inputs have a visible upload affordance (EDA + Multimodal RAG)
**Steps:**
1. Open the EDA tool and the Multimodal RAG add-image popover.
**Expected Result:** EDA shows a dashed drop-zone (icon, "Drop your CSV here / or click to browse", drag-and-drop, 10MB hint) over a hidden native input; Multimodal RAG shows a styled "Choose an image" button. Site-wide audit of 44 controls found only these 2 bare (42 already hid the native input); the regex that flagged 4 was lossy over `=>` arrows — confirm each hit by hand.
**Automation Hint:** upload-affordance presence check (production-verified for EDA).
**Source:** Part330 (`da772d6`)

---

## Cross-cutting / Process (Parts 320–330)

### TC-P19-030
**Category:** Architecture
**Test Name:** Fail-open vs fail-closed is a per-concern choice
**Steps:**
1. Review each guard's failure mode.
**Expected Result:** YARA (reliable, in-process) → fail-closed; ClamAV (daemon warmup) → enforce-once-ready; read paths that expose data (audit lookup) → fail-closed; a limiter that could break capture → fail-open.
**Automation Hint:** none (design).
**Source:** Part320

### TC-P19-031
**Category:** Architecture
**Test Name:** Chart palettes key off the site's theme mechanism, not prefers-color-scheme
**Steps:**
1. Render the /eval charts under `html.light`.
**Expected Result:** Tokens keyed to `html.light` (site default = dark) match the page — keying off `prefers-color-scheme` mismatched; steps validated with the dataviz `validate_palette.js` for both surfaces.
**Automation Hint:** computed-color check per theme.
**Source:** Part326

### TC-P19-032
**Category:** Architecture
**Test Name:** Flipping an auth gate is only as safe as the per-row scoping
**Steps:**
1. Relax 8 tenant routes from owner-only to any signed-in user.
**Expected Result:** Every query audited for `owner_id=user.id` (the isolation boundary) before relaxing the gate — the only security crux of self-serve.
**Automation Hint:** per-route scoping audit.
**Source:** Part327

### TC-P19-033
**Category:** Architecture
**Test Name:** Verify the right CI run / don't conflate platform lag with failure
**Steps:**
1. Confirm a deploy after a push.
**Expected Result:** `gh run watch` can latch onto a stale/other run (false green) — confirm the actual run; Vercel can lag ~15–20 min showing a deploy (not disconnected), and a stuck GitHub `doc-coverage` check (all steps succeeded, run=success, check `in_progress`) is a glitch cleared by `gh run rerun`. Check command output before claiming state.
**Automation Hint:** none (method).
**Source:** Parts326/327

### TC-P19-034
**Category:** Architecture
**Test Name:** Grep for what exists before building
**Steps:**
1. Scope "autocomplete site-wide".
**Expected Result:** Half was already shipped (per-tool `ToolsAIChat` chips, tenant-bot `EmbedWidget` chips); only the homepage chat + a search box were missing, and the search needed no new backend.
**Automation Hint:** none (method).
**Source:** Part329

---

**Total: 34 test cases, Parts 320–330.**
