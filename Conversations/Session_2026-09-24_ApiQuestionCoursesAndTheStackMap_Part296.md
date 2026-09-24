# Part 296 — "Can we build an API?", course research, and a code-verified stack map

Continues [Part 295](Session_2026-09-20_ThreeWorldsAndTheAppReskin_Part295.md).
2026-09-24. A no-code session: explained what an API is (the user is new to APIs),
verified YouTube courses via live search, and produced `TECH_STACK.md` — a
code-verified map of the whole stack. Nothing deployed.

The through-line: **answer from the code and from live search, never from memory —
the user explicitly asked for genuine, non-hallucinated recommendations, and a
stack map is only useful if every line is verified against the repo.**

---

## 1. "Can we create an API for my website?"

The user is new to APIs and asked what we can do, how, and why. Answered in plain
text (no code):
- They **already have an API** — the ML-Unified backend is FastAPI, which *is* an
  API framework; the frontends already call it. The real question is who else gets
  to use it and how.
- Laid out three directions: (1) make the ML tools publicly callable (keys + rate
  limits + OpenAPI docs), (2) Next.js API routes for the site itself, (3) just
  document/open what exists.
- Recommendation: start with **#1 scoped to one endpoint** (Titanic) to learn every
  core concept on something small and real. Flagged the free-HF-Space sleep/rebuild
  limit up front. Did **not** start building — offered a plan first.

---

## 2. Course research (all verified via live web search)

The user wanted genuine YouTube courses, no hallucination. Searched and returned
titles + links exactly as found, naming channels only where the source stated them.

- **APIs (general, English):** sequenced concept → use → build path. Concept:
  "What Are APIs? - Simply Explained". Use: "Master Python Requests in 15 Minutes".
  Build (their stack): "Python FastAPI Tutorial: Build a REST API in 15 Minutes"
  then a full FastAPI course. Deliberately excluded the freeCodeCamp "APIs for
  Beginners" full course (standing user preference).
- **API complete course in Hindi:** pointed to **FastAPI-in-Hindi** since that's
  their exact stack — "FastAPI Full Course 2026 in Hindi" (single-video) or the
  "Backend development with Python | FastAPI tutorial in Hindi" playlist, preceded
  by "What is REST API in Hindi?".
- **Networking — is there better than Hussein Nasser?** Honest answer: **no.** For
  networking-as-it-matters-to-web/API-devs (not CCNA), Hussein Nasser is the
  gold-standard single source; 2026 roundups rank him top. Keep his HTTP → Network
  Engineering order; only complement with ByteByteGo (system-design angle) after.
  Fixed the stray `?` on the user's pasted playlist URL. Excluded freeCodeCamp again.

Lesson reinforced: for every recommendation, open the link caveat — YouTube titles
get re-uploaded/reordered, so verify before investing hours.

---

## 3. TECH_STACK.md — code-verified stack across 18 categories

The user asked what the site uses for each of: frontend, backend, vectordb, sql db,
cache, auth, hosting, secret manager, cicd, IAC, observability, cloud, embedding —
then added LLM, agentic framework, storage, testing, blue-green. Grepped both repos
(ml-portfolio + ML-Unified) and wrote it up in `TECH_STACK.md` (repo root, 228 lines).

Key code-verified findings (not from memory):
- **Frontend:** Next.js 16 / React 19, Tailwind v4, Framer Motion, Three.js. HF
  Space apps are plain HTML/CSS/JS.
- **Backend:** FastAPI + Uvicorn; four services (ml-api, ml-vision, ml-sql,
  ml-qa-runner) + Next.js API routes on Vercel.
- **Vector DB:** ChromaDB + BM25 hybrid.
- **SQL DB:** Supabase (Postgres) for analytics/security logs; ml-sql introspects
  the *user's* SQLite/Postgres, not ours.
- **Embedding:** text `all-MiniLM-L6-v2` + `jinaai/jina-embeddings-v3`; images
  CLIP `openai/clip-vit-base-patch32`.
- **LLM:** default **Cohere** (`/api/chat` fallback); full set Claude/OpenAI/Gemini/
  Groq/Mistral/Cohere/Perplexity; Gemini paid, never a silent default.
- **Agentic:** **LangGraph** (`StateGraph`) for `/rag/agent`, a *soft dependency*
  that degrades to direct retrieval if not installed (`_LANGGRAPH_OK`) — not pinned
  in requirements. Plus CRAG + query router.
- **Testing:** pytest (+ pytest-playwright) backend; Vitest + Playwright frontend;
  two-tier (hard per-push, scored nightly evals).
- **Deliberate gaps** (fine for a portfolio, documented with what covers them and
  what to add if scaling): no Redis, no user auth (Turnstile + service-role key
  instead), no secret manager (platform env vars), no full IaC (Docker + render.yaml),
  no APM (Supabase logs + /health), no object storage (in-memory + ephemeral disk +
  client-side blobs), no named blue-green (Vercel atomic immutable deploys; HF
  rebuilds in place — why deploys are batched).

---

## Commits (all docs-only, no deploy, no HF upload)

| Commit | What |
|---|---|
| `cab8d04` | add TECH_STACK.md — 13 categories |
| `0acadbe` | expand TECH_STACK.md — LLM, agentic, storage, testing, blue-green (18 total) |

---

## Lessons

- **Verify before recommending, every time.** All course links came from live
  search, not recall; channels named only where the source stated them; the
  freeCodeCamp exclusion honored across all three course asks.
- **"What are we using?" is a code-lookup, not a memory recall.** Grepped both repos
  for each category — including exact embedding model IDs and the LangGraph soft-
  dependency guard — rather than answering from what I thought was true.
- **Name the deliberate gaps, don't hide them.** The stack map is more useful for
  listing what we *don't* have (Redis, auth, IaC, APM, object storage, blue-green)
  and what covers each today than for the parts that are obvious.
