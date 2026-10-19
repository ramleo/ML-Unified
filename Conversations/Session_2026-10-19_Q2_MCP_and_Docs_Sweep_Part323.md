# Part 323 — Q2 MCP server (shipped) + documentation sweep

Continues Part 322 (same day, 2026-10-19). Covers **Q2 M1 (MCP server)** and a sweep
that surfaced today's work (auth, profile pics, Q1 API, Q2 MCP) across every doc/UX
surface.

## Q2 — MCP server (M1 shipped)

Decisions (AskUserQuestion): **mount on the existing Space** at `/mcp` (one deploy,
reuses tool code; accepted the whole-site blast radius with a /health-first rollback
plan); **reuse Q1 keys** as Bearer tokens; **mirror the /v1 three** tools. OAuth 2.1 +
PKCE deferred.

- **Library:** FastMCP **4.1.1** over **Streamable HTTP**. Introspected the real API
  before writing (it drifts): `FastMCP(name, auth=...)`, `@mcp.tool`,
  `http_app(path, allowed_hosts=[...])` → app with `.lifespan`; auth = a custom
  `TokenVerifier.verify_token(token) -> AccessToken|None`.
- **`mcp_server.py`** — `ApiKeyVerifier` hashes the Bearer token and validates via the
  same `/api/keys/verify` (so one key works for REST + MCP). Three tools
  (tls_headers_check, email_auth_check, anomaly_detection_score) call the same tested
  logic behind `/v1`.
- **`app.py`** — `_mcp_app = mcp.http_app(path="/", allowed_hosts=[space host, localhost])`,
  a **combined lifespan** (app startup + MCP session manager), and `app.mount("/mcp")`
  **last** (after routers). Locally probed the mount: both `/mcp` and `/mcp/` → 401
  (auth reached, path resolves).
- **Deploy gotchas handled before shipping:**
  - Dockerfile copies root files individually → added `COPY mcp_server.py .` (else the
    import fails and the whole Space breaks).
  - Dependency check: `mcp` needs only `starlette>=0.27`, so `fastmcp==4.1.1` does **not**
    conflict with `fastapi==0.141.1`. Pinned in requirements.txt.
- **Commit `8f65b27`** (ML-Unified) + HF upload of `mcp_server.py`, `app.py`,
  `requirements.txt`, `Dockerfile` (full rebuild, ~12 min with deps).
- **Verified:** `/health` **200** (main backend unaffected — no rollback needed),
  `POST /mcp/` **401** without a key. **Finding:** on the real server `/mcp`
  **307-redirects to `/mcp/`** (Starlette mount trailing slash) — clients use `/mcp/`;
  both resolve to the gated endpoint. Full handshake with a valid key still TODO (user
  to mint a key).
- **Client config:** URL `https://wram1708-ml-unified.hf.space/mcp/`, header
  `Authorization: Bearer ak_live_…`.

## Documentation sweep (surfacing today's work)

- **Frontend `/docs`** — added an **MCP (for AI clients)** section (URL, bearer-key
  client config) next to the Public API (v1) section.
- **Changelog** (`/changelog`) — three user-facing entries: accounts/sign-in + profile
  pictures; the public API; MCP support.
- **Privacy page** — new **"If you create an account"** section: email + bcrypt-hashed
  password (Supabase Auth), profile row + avatar in a storage bucket, and API keys
  stored only as a hash with usage counters. Softened the old "no account" wording.
- **Homepage Hero** — a small "Developers: call the tools via the public API & MCP"
  pointer to `/docs`.
- **READMEs** (both repos) — a short Public API + MCP / accounts note.
- **TECH_STACK.md** — rewrote the **Auth** section (was "no end-user auth"); added
  `@supabase/ssr`, `react-easy-crop` (frontend) and `fastmcp` (backend).
- **PRD** `05-roadmap-extensions.md` — Q1 ✅, Q2 🚧 M1. **Memory** — roadmap updated
  (Q5/Q1 ✅, Q2 M1 ✅).

## State of the roadmap
Q5 ✅ · Q1 ✅ · **Q2 M1 ✅** · Q4 (eval) + Q3 (chatbot builder) remain. Q2 next steps:
OAuth 2.1+PKCE, MCP resources/prompts, larger tool set, and a live handshake test.
