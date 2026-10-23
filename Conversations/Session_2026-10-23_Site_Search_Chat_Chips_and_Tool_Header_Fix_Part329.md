# Part 329 — Site search, homepage chat chips, and the tool-header fix (2026-10-23)

Continues Part 328. All frontend (ml-portfolio / Vercel); no backend or HF changes.
This closed the standalone **autocomplete / site-search** UX item ([[project_autocomplete_idea]])
and fixed a site-wide tool-header layout bug. Every commit CI-verified green and
browser-verified with Playwright before shipping.

## Grounded site search box (`dfef3e8`)
A global search box in the navbar (icon + ⌘K overlay), built to be **website-only and
no-hallucination by construction**:
- **Structured asks** ("list tools", "what platforms") and as-you-type matches come
  straight from the REAL site data — `src/data/capabilities` (tools) + `registry.json`
  (platforms) via the existing `scoreCapability` ranker — rendered as links / a table
  with links. No model in that path, so nothing can be invented.
- **Free-form questions** reuse the existing `/api/chat` RAG assistant (handbook-grounded,
  already declines off-topic) — no new ungrounded generation.
- **Off-topic / no match** → a fixed "only this website" message.
- `src/components/SiteSearch.tsx` (272 lines), mounted in `Navbar.tsx`.
- Research first (grounding + scope-guard patterns): the standard pattern is index-only
  retrieval + "say not found" + structured data for structured asks — which this does.
- **Verified live:** "list tools" → 58-row table with links; "what is the capital of
  France?" → the assistant refused ("I don't have information… try a general search
  engine"), i.e. no hallucination.

## Homepage RAG chat starter chips — static + dynamic (`1d573e7`, `4feb738`)
The front-page chat opened to a blank box. Added clickable starter questions in the empty
state (click → sends). BOTH kinds, as asked:
- **Static** (`1d573e7`): per-section curated questions, shown instantly, zero cost.
  Extracted config to `chatbotConfig.ts` + refactored `send`→`sendText` so a chip can
  send without the input box. Kept `Chatbot.tsx` under 400 lines.
- **Dynamic** (`4feb738`): KB-derived questions generated from the real tool catalog via
  a new `GET /api/chat/suggest`, which reuses the proven `suggestQuestions` → Space
  `/internal/tenant/suggest` path and **caches in-module (6h TTL)** so it costs one
  free-provider call every few hours, NOT per visitor. `useStarterChips.ts` hook shows
  static instantly, swaps to dynamic when ready, falls back to static on any failure
  (keeps `Chatbot.tsx` lean).
- **Verified:** static chips render per section and send (grounded reply); the production
  `/api/chat/suggest` returns real grounded questions (EDA / Feature Engineering / Feature
  Selection / AutoML) and a repeat call returned the identical set → cache confirmed.
  Locally it returns `[]` (no `TENANT_INTERNAL_TOKEN`) and the UI falls back to static —
  verified post-deploy on Vercel.

Already existing (NOT rebuilt, found by grepping first): the per-tool chat (`ToolsAIChat`)
and embedded tenant bots (`EmbedWidget` → `/api/embed/suggest`) already had suggestion
chips. **Site-wide search typeahead needed no new backend** — it reuses existing data +
RAG. Tool-input autocomplete deliberately left (low value: tools take files/numbers/
dropdowns, not free text).

## Tool-header fix — one-line breadcrumb + non-wrapping pill (`df11e42`)
User flagged the Feature Engineering header: the "‹ Home / ‹ ML Pipeline" breadcrumb was
**stacked into two back-buttons** and the "runs in browser" pill **wrapped mid-word**.
Root cause: busy multi-step tool headers (`.tool-header-row`) cram breadcrumb + title +
pill + stepper + buttons into a fixed 60px / 1060px row, so flexbox **shrank the atoms**
until they wrapped internally. Site-wide fix via the shared pieces:
- **`ToolBackNav`** → a horizontal breadcrumb **trail** (one back chevron, then `Home ›
  Area`) instead of two stacked back-links. Shared → all ~50 tools.
- **`07-tools.css`**: `.tool-back-nav` nowrap + no-shrink (never stacks); `.tool-header-row`
  now **wraps and grows** (overriding the pages' inline `height:60` with `!important`, the
  established pattern) with the title forced to one line — so a tight header breaks
  BETWEEN controls, never inside them.
- **Extracted shared `RunsInBrowserBadge`** (`white-space:nowrap`) replacing the two inline
  copies (feature-engineering, preprocessing); `FSPageHeader`'s badge got nowrap too.
- **Verified:** FE + Preprocessing (busy — row now wraps to 2 clean lines, stepper on line
  2), JWT analyzer (lighter — one clean line, "Home › Security & Trust"), and phone width
  (no horizontal scroll, no mid-word wrapping).

## Lessons
- **Grep for what exists before building.** Half the "autocomplete site-wide" scope was
  already shipped (per-tool chat + tenant bots); only the homepage chat + a search box were
  missing. The "site search" turned out to need no new backend.
- **Grounded-by-construction beats a guardrailed LLM.** Structured asks answered from real
  data (a table of the actual tools) can't hallucinate; the LLM path only runs for free-form
  questions and reuses the already-scoped RAG.
- **Cache dynamic suggestions, don't generate per visitor.** A 6h in-module cache turns a
  per-open LLM cost into one call every few hours.
- **A shared layout bug is fixed in the shared component, not per page.** One `ToolBackNav`
  + CSS change fixed the breadcrumb across all ~50 tools; the only per-page work was the
  duplicated pill, which became a shared component.
- **Fixing a squeeze: don't let atoms wrap — let the container wrap between them.** nowrap
  the breadcrumb/title/pill, wrap-and-grow the row.

## State of the roadmap
Q5 ✅ · Q1 ✅ · Q2 🚧 M1+M2 (M3 OAuth deferred) · Q4 ✅ · Q3 ✅ (M4c deferred) ·
**autocomplete/site-search ✅**. Buildable roadmap essentially complete. Remaining:
go-live billing (live Stripe keys / India account) and the owner's manual
`supabase/eval_online.sql` step.
