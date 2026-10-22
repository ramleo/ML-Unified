# Part 327 — Q3 M3→M4b (embed widget, self-serve, Stripe billing) + Q4 M3 online judge-scoring (2026-10-22)

Continues Part 326. This day finished the **Q3 chatbot arc** (M3 embed widget → M4a
self-serve → M4b Stripe billing), added branding/UX polish, and shipped **Q4 M3**
(online judge-scoring), which **completes Q4**. Frontend = ml-portfolio (Vercel);
backend = HF Space `wram1708/ml-unified`. All commits CI-verified green; backend changes
HF-uploaded + Space confirmed RUNNING.

## Q3 M3 — embeddable chatbot widget (frontend-only)
Research → chose **Approach A** (loader + sandboxed iframe + mint-token) with all four
abuse controls. Key research reframe: the per-visitor **origin check is weak alone**
(spoofable), so the hard backstops are the rate limit, daily cap, and kill switch.
- **Loader** `public/embed/v1.js`: one `<script data-bot="pk_…">` → floating bubble +
  **sandboxed cross-origin iframe** (`/embed/widget`). Mints the session as a **simple
  CORS request** (text/plain, NO preflight — a preflight can't carry the key) from the
  host page, so the server sees the real `Origin` → checks the per-bot **allowlist** →
  **HS256 JWT** bound to `{tenant, origin}` (hand-rolled, no dep) → handed to the iframe
  over a strict 2-type postMessage channel → JWT-gated `/api/embed/query` (same-origin).
- **Controls (server-side):** origin allowlist, short JWT, per-IP rate limit (reuses
  `rate_limit_hit`), hard daily message cap (`tenant_embed_charge` RPC) + publish **kill
  switch**. Owner **Embed** tab + owner-gated `/api/tenants/[id]/embed`. Schema
  `supabase/tenant_embed.sql`. `/embed/widget` carved out of the site's
  `X-Frame-Options`/`frame-ancestors 'self'` in next.config so it's framable.
- **Fix:** widget used `height:100%` → the site's dark body showed through below the
  chat; anchored root to `position:fixed; inset:0` with its own white ground.
- Commits: `9820e21` (M3), `b3f1b11` (fill fix). Needs `EMBED_JWT_SECRET` env + migration.
- Verified end-to-end on a dummy localhost page; a non-allowlisted origin
  (`127.0.0.1` vs `localhost`) was correctly refused.

## Q3 M4a — self-serve (flip the owner gate + plan tiers)
Decisions: self-serve first (billing next); **publish gated behind a paid plan** (free
users build/test, can't go live = the cost guard); **flat tiers**.
- `profiles.plan` ('free'|'pro', service-role-only writes — `supabase/profiles_plan.sql`).
- `src/lib/auth/user.ts` (`getAuthedUser`) + `plan.ts` (`getPlan`/`canPublish`/`maxBots`;
  free = 2 bots, owner unlimited).
- **8 tenant routes flipped** owner-only → any signed-in user, keeping `owner_id=user.id`
  scoping (the isolation boundary — **audited on every route**, the only security crux).
- Publish gate in `/api/tenants/[id]/embed` (owner exempt; `can_publish` in GET for the
  UI). Free bot cap on `POST /api/tenants`. New `/app/chatbots` (owner keeps
  `/portfolio/chatbots`); profile-menu "Chatbots" for non-owners.
- Commit `adcdd23`. Needs `profiles_plan.sql` (degrades closed pre-migration).

## Q3 M4b — Stripe Billing (self-serve upgrade)
Research reframe: the PRD's "Stripe **Connect**" is over-scoped — Connect only applies to
routing end-users' money to tenants' own accounts (reseller payouts). We charge users for
our platform → plain **Stripe Billing**. (Connect = M4c, deferred.)
- Hosted **Checkout** + **Billing Portal** (no card data touches us; no publishable key /
  client Stripe.js). `src/lib/billing/stripe.ts`; `/api/billing/checkout`, `/portal`,
  `/webhook` (signature-verified, raw `req.text()` — the SINGLE source of truth that flips
  `profiles.plan` on `checkout.session.completed` / `customer.subscription.updated|deleted`,
  mapping back via `stripe_customer_id`), `/status`. UI `/app/billing` (Free vs Pro,
  Upgrade / Manage, banners); profile-menu Billing link. **Pro = publish + 10 bots**, no
  trial. Schema `supabase/billing.sql`. Added the `stripe` SDK (^23).
- Commit `bcf058b`. Needs `STRIPE_SECRET_KEY` + `STRIPE_PRICE_PRO` + `STRIPE_WEBHOOK_SECRET`
  (test mode) + migration — degrades honestly ("upgrades aren't available yet") until set.
- **User completed the Stripe test-mode setup and confirmed the full flow works**
  (sign up → Upgrade → test card `4242…` → Pro → publish unlocks; Portal cancel → Free).

### Stripe setup notes (dashboard reality, 2026)
- **Webhooks moved to Workbench** (Developers → Workbench → Webhooks). New flow offers a
  **payload format**: must pick **Snapshot** (our handler reads `event.data.object`; Thin
  only sends IDs and would break it).
- **Customer portal** lives at Settings → Billing → Customer portal (or
  `/test/settings/billing/portal`); a one-time **Save** activates it. Keep "next
  generation portal" OFF.
- **Restricted key** (`rk_test_…`) works only with the right write scopes; the **standard
  Secret key** (`sk_test_…`) is simplest.
- **Account country can't be changed** to/from India after creation (data-localization) —
  irrelevant for test mode; real ₹ payouts need an India account (invite-only) or an alt
  processor (Razorpay/etc.). Noted as go-live housekeeping.
- **Branding**: the public **name** lives under Settings → Business → **Account details**
  (already "AIRaML"); the **Branding** tab only sets icon/logo/colours (no name field).

## UX polish (several small commits)
- **Persona char counter** (`count / 16,000`, red at cap, `maxLength`) + gate the embed
  **Install** block behind the plan (free users saw a dead snippet). `dc0bf21`.
- **Disabled-Publish hint** shows *why* ("Add an allowed site first" / "Upgrade to
  publish") beside the button; later **dropped the `not-allowed` ⊘ cursor + native
  tooltip** (the ⊘ covered the tooltip). `ccdf01b`.
- **Chat persistence**: the Test chat survives tab switches via `sessionStorage` per bot +
  a **Clear chat** button. **Markdown tables**: `ChatMarkdown` table/th/td styling +
  backend grounding hint telling the model to emit Markdown tables. `3c31c7e` (FE) +
  `6b22c3a` (BE, +HF).
- **Favicon = navbar logo**: replaced the neural-node favicon with the brand "AI" tile so
  the tab icon matches the header. `a921b69`. (Generated downloadable `airaml-icon.png` /
  `airaml-logo.png` for Stripe branding from the real gradient via `sharp`.)

## Q4 M3 — online judge-scoring (completes Q4)
Purpose: the offline golden set is a canned test and the health signals are proxies;
M3 scores a **sample of REAL answers users received** so the dashboard shows live quality.
- **Reference-free + content-free**: on the live RAG answer path (`query.py`, where
  question/answer/chunks are in memory), sample a fraction — **tail always** (low-confidence
  or groundedness < 0.5) + **small random** (default 8%) under a **daily cap** (200) — and a
  **background thread** has Gemini judge the answer vs the retrieved context → **faithful +
  relevant → pass** (no "correct" online; no reference). It **never blocks** the response
  and **POSTs only the verdict** — question/answer/context are never stored.
- Space: `routers/rag/online_judge.py` (`maybe_judge`) + a one-line hook in `query.py`.
  Frontend: `online_scores` (service-role; `surface` column future-proofs tenant bots),
  `/api/eval/online-ingest` (AIRAML_LOG_TOKEN-gated), `/api/eval/online` (owner aggregator),
  `EvalOnline` panel + new **"Online quality"** section on `/eval`.
- Reuses `GEMINI_API_KEY` + `AIRAML_LOG_TOKEN`; env-tunable
  `EVAL_ONLINE_SAMPLE_RATE` / `_DAILY_CAP` / `_TAIL_GROUNDEDNESS`. Needs `eval_online.sql`.
- Commits: ml-portfolio `9ffdef3`, ML-Unified `1cb09e7` (+HF). **Q4 now complete (M1+M2+M3).**

## Lessons
- **Embed origin check is weak alone** — design the hard controls (rate limit, daily cap,
  kill switch) as the real backstops; the origin allowlist is cost-steering.
- **Simple CORS request avoids the preflight key problem** — a preflight can't carry a
  custom header, so put the key in a text/plain body (no preflight).
- **Flipping an auth gate is only as safe as the per-row scoping** — audit every query for
  `owner_id=user.id` before relaxing the gate.
- **Stripe "Connect" ≠ "Billing"** — Connect is for marketplaces/payouts; a plain SaaS
  subscription is Billing. Don't over-scope.
- **Verify the right CI run** — a `gh run watch` once latched onto a stale/other run and
  reported a false green; confirmed the actual run before claiming success.

## Handbook — Chatbot builder chapter (follow-up)
After confirming PRD + memory were already current (but the public handbook was
not), added a user-facing chapter so the chatbot builder is discoverable like the
API/MCP are. Owner-only features (eval dashboard, online judge) deliberately stay
out of the public handbook — their record is the PRD roadmap + the owner nav.
- **New Part 3 · Chapter 7 "Chatbot builder"** in the handbook: build & test, Free
  vs Pro plans, the embed `<script>` snippet, the five abuse controls. Extracted the
  two hand-authored platform chapters (Developer access + Chatbot builder) into
  `scripts/handbook_platform_chapters.py` so `build-handbook.py` stays under the line
  limit. Regenerated `public/handbook.md`. ml-portfolio `852d8cf`.
- **KB re-sync** so the public RAG bot knows the new chapter: ML-Unified `81b5b6a`
  (+HF `9345655`/`33ea24d`). **Bug fixed in `sync_handbook_kb.py`:** `clean()`
  stripped every `<…>` tag, which blanked the embed `<script>` snippet inside the
  fenced code block; now code fences are protected from tag-stripping.
- Verified end-to-end on the live Space (RUNNING): the public bot answers "how do I
  embed a chatbot, what plan?" correctly, citing the new sections.
- **Lesson:** twice this follow-up I stated before checking — called CI "not
  triggered" (it had run green; the Actions API just lagged) and claimed some tools
  were appendix-only (all 58 have full chapters). Check the command output first.

## State of the roadmap
Q5 ✅ · Q1 ✅ · **Q4 ✅ (M1+M2+M3)** · **Q3 ✅ (M1→M4b)** · Q2 🚧 M1.
Remaining: Q2 MCP extras (OAuth 2.1 + PKCE, resources/prompts, bigger tool set), Q3 M4c
(reseller/Connect, deferred), autocomplete site-wide, go-live billing (live Stripe keys /
India account).
