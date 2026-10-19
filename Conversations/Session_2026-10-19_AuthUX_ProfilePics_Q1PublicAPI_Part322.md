# Part 322 — auth-UX polish, profile pictures, and Q1 Public API (shipped)

Session of 2026-10-19. Three bodies of work, all shipped and (where possible)
live-verified: the deferred auth-UX items from Part 321, profile-picture upload, and
**Q1 — the public API** (M1+M2+M3). Process throughout: research → propose options →
ask (AskUserQuestion) → build → verify → ask before commit.

---

## 1. Auth-UX pass (the 5 open items from Part 321)

Decisions (via AskUserQuestion): avatar+initials in the navbar; full **owner-aware**
profile dropdown; owner **lands on the homepage**; share-links get a **dedicated page**.

- **Profile dropdown** (`NavAuth.tsx`) — avatar (initials) → menu with identity header
  (email + role), owner's My portfolio / Share links / API keys, Account, Settings,
  Sign out (a menu item, not a mismatched chip). Click-outside + Escape + ARIA.
- **Owner lands on homepage** — `/app` router redirects everyone to `/`; the portfolio
  and managers are reached from the menu.
- **New pages** — `/account` (identity, role, member-since, change password),
  `/settings` (appearance: theme + palette), `/portfolio/share` (recruiter links moved
  off `/portfolio`).
- **`/api/me`** — `{ email, role, avatarUrl, isOwner }` so the client is owner-aware
  without `OWNER_EMAIL` ever reaching the browser.
- Commits: `53c55ac` (ml-portfolio), `4303c54` (ML-Unified Part 321 resolved).

## 2. Profile pictures

Decisions: public bucket + public URL; upload **with crop/zoom**; keep the mobile
avatar dropdown; available to **all signed-in users**.

- `supabase/avatars.sql` — `profiles.avatar_url`, public `avatars` bucket, per-user
  storage RLS.
- `/api/avatar` (POST/DELETE) — session-scoped; uploads to `<uid>/avatar.jpg` and
  writes `avatar_url` **via the service-role key**, so uploading can never touch `role`
  (profiles has no UPDATE policy on purpose).
- `AvatarEditor.tsx` + `lib/cropImage.ts` — react-easy-crop modal → square JPEG →
  upload; navbar updates live via a window event; initials fallback.
- Commit `9f851ee`.

## 3. Fixes found by live testing

- **Avatar flicker on nav** (`94376a3`) — menu used `<a>` (full reload) so identity
  re-fetched and blanked. Fix: `next/link` client nav + in-memory identity cache so
  the avatar stays painted. → saved memory `feedback_no_content_flicker_on_nav`.
- **Site title** (`d3a1656`) — default title was "AIRaML — 50 free machine-learning
  tools"; the hardcoded count goes stale. Now "AIRaML — Free machine learning & AI
  tools in your browser"; description de-numbered.
- **Revocable-list UX** — revoked items lingered. Brought **both** the API-keys panel
  (`45eaf93`) and the recruiter share-links panel (`4961a83`) to parity: revoked
  hidden behind a "Show revoked (N)" toggle, permanent **Delete**, per-row
  "Revoking…/Deleting…" state. Free-tier key budget now defaults to **$0** (`2558a5a`).
  → saved memory `feedback_revocable_list_pattern` (apply to ALL such lists at once).

---

## 4. Q1 — Public API (COMPLETE: M1 + M2 + M3)

Let third parties call the tools with an API key. Decisions (AskUserQuestion):
**validate via a token-gated frontend route + no Supabase key on the Space**;
**owner-only** key issuance; **cheap/no-LLM endpoints first**; **tier-ready** model
(free + paid) now, Stripe deferred.

### M1 — key management (frontend + store), commit `34e1845`
- `supabase/api_keys.sql` — stores only a **SHA-256 hash** + prefix; RLS
  service-role-only; `tier` (free/paid), `monthly_quota`, `budget_usd`,
  `request_count`, `spend_usd`, monthly `period_start`, `expires_at`, `revoked`.
- `/portfolio/keys` (owner, in the profile menu) — create (key shown **once**), list,
  revoke, delete.
- `/api/api-keys` (GET/POST/DELETE) + `/api/api-keys/revoke` — owner-gated.
- `/api/keys/verify` — **token-gated** (`API_KEYS_VERIFY_TOKEN`); the Space calls it
  to validate a key by hash and meter use (checks revoked/expired/quota/budget,
  monthly reset). A $0 budget blocks only spending calls, not zero-cost ones.

### M2 — backend `/v1/` router (→ HF deploy), commit `15ee2ea`
- `security/api_key.py` — `require_api_key` dependency: reads `X-API-Key`, per-key
  in-memory burst limit, then **verifies every request** against the frontend route
  (accurate quota metering; **fail-closed** if the token is unset). Sync `def` so the
  blocking httpx call runs in FastAPI's threadpool. Space holds **no Supabase key**.
- `routers/public_api.py` — `/v1/` router (key-gated), reusing existing tested logic:
  `POST /v1/tls-headers/check` `{host}`, `POST /v1/email-auth/check` `{headers}`,
  `POST /v1/anomaly-detection/score` `{baseline, events}`. All no-LLM → no spend yet.
- Verified live: 401 without/with bad key; all three return 200 with a real key
  (anomaly correctly flagged the outlier). Quota metering confirmed.

### M3 — public discovery + docs (→ HF deploy), commits `3949634` + `c80bcda`
- Ungated **`/v1/openapi.json`** (meta_router) — trimmed OpenAPI 3.1 of only `/v1/*`,
  with the `X-API-Key` scheme and the Space server URL. Verified: 3 paths, scheme
  present, server set.
- **Public API (v1)** section on the frontend `/docs` page — how to get a key, the
  header, the endpoints with a curl example, limits, link to the spec.

### Deferred (by design)
Per-call **spend** metering (only matters once LLM tools enter `/v1/`); a per-key
per-minute slowapi limit if the in-memory burst guard proves thin; monetization/Stripe
if ever charging (the schema's `tier` is the seam).

---

## Setup the owner performed (one-time)
- Ran `supabase/avatars.sql` and `supabase/api_keys.sql` in Supabase.
- Set `API_KEYS_VERIFY_TOKEN` on **both** Vercel and the HF Space
  (`wram1708/ml-unified`, Settings → Variables and secrets → Secret). `API_KEYS_VERIFY_URL`
  defaults to the Vercel URL.

## HF deploy note
Token lives in the **git credential helper** (keychain), NOT the `hf` remote URL
(which is a plain URL). Retrieve via `git credential fill` piped into Python; never
print it. Strip `services/ml-api/` when uploading. See `reference_hf_deploy` memory.

## Commits (chronological)
`53c55ac` auth-UX · `4303c54` Part321-resolved · `9f851ee` avatars ·
`94376a3` flicker · `2558a5a` free=$0 · `d3a1656` title · `45eaf93` keys-UX ·
`4961a83` share-links parity · `34e1845` Q1 M1 · `15ee2ea` Q1 M2 (+HF) ·
`3949634` Q1 M3 backend (+HF) · `c80bcda` Q1 M3 docs.

## Reference docs updated (local-only)
`ml-portfolio/docs/ACCESS_AND_AUTH.md`, `ML-Unified/docs/prd/05-roadmap-extensions.md`
(Q1 marked ✅), `02-cross-cutting-systems.md`.

## What's next
Roadmap remaining: **Q2 (MCP)** — reuses the Q1 key layer to expose a curated tool
subset to AI clients; then Q4 (eval platform), Q3 (chatbot builder).
