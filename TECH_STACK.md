# AIRaML — Tech Stack Reference

_Last verified from the codebase: 2026-09-24._

This is the honest, code-verified map of what the AIRaML project actually uses,
category by category. It covers both repos:

- **ml-portfolio** — the public website (Next.js / Vercel).
- **ML-Unified** — the ML backend (FastAPI / Hugging Face Spaces).

Where a category has **no dedicated tool**, that is stated plainly along with what
covers the need today and what we'd add if the project ever needed to scale.

---

## Stack at a glance

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 + React 19 on Vercel |
| Backend | FastAPI (Python) on Hugging Face Spaces |
| SQL DB | Supabase (PostgreSQL) |
| Vector DB | ChromaDB + BM25 (hybrid retrieval) |
| LLM | Cohere (default), + Claude / OpenAI / Gemini / Groq / Mistral / Perplexity |
| Agentic | LangGraph (soft dependency, degrades gracefully) |
| Testing | pytest (backend) · Vitest + Playwright (frontend) |
| CI/CD | GitHub Actions |
| Cloud | Vercel + Hugging Face + Supabase (all managed PaaS) |

The spine is: **Next.js/Vercel front → FastAPI/HF back → Supabase + ChromaDB for
data.** Everything else hangs off that.

---

## Category by category

### 1. Frontend
- **Framework:** Next.js 16 (App Router), React 19.2.
- **Styling:** Tailwind CSS v4 (`@tailwindcss/postcss`); design tokens in
  `src/app/styles/`.
- **Motion / 3D:** Framer Motion; Three.js via `@react-three/fiber` + `drei`.
- **Icons:** `lucide-react` (project rule: no emoji in UI, inline SVG only).
- **Other libs of note:** `react-markdown` + `remark-gfm` + `rehype-raw` (handbook/
  docs rendering), `@mediapipe/tasks-vision` (in-browser vision demos),
  `@zxcvbn-ts/*` (password-strength tool), `pagedjs` (print/PDF layout),
  `stemmer` (client-side search matching), `gifenc` (GIF export).
- **Note:** the three HF Space apps that open from "Open the platform"
  (`index.html` / `eda.html` / `vision.html`) are **plain HTML/CSS/JS**, not React
  — reskinned to match the portfolio design.

### 2. Backend
- **Framework:** FastAPI 0.141 + Uvicorn (Python).
- **Services (microservice-style split under `services/`):**
  - `ml-api` — the main API (classic ML, EDA, vision, RAG, security/trust tools).
  - `ml-vision` — vision models, split out for its own deploy.
  - `ml-sql` — the Text-to-SQL platform.
  - `ml-qa-runner` — the QA / Testwright platform runner.
- **Key Python libs:** scikit-learn, pandas, numpy, scipy, XGBoost, LightGBM,
  CatBoost, SHAP (explainability), OpenCV (headless), PyMuPDF / pypdf / python-docx
  (document parsing), skops (safe model serialization).
- **Also:** Next.js **server / API routes** on Vercel handle the live LLM features
  and server-only secrets (the site's own lightweight backend).

### 3. Vector DB
- **ChromaDB** (embedded) as the vector store for RAG.
- **BM25** keyword index alongside it for **hybrid retrieval** (dense + sparse).
- Lives in `services/ml-api/routers/rag/` (`ingest.py`, `store.py`, `retrieve.py`,
  `rerank.py`, …).

### 4. SQL DB
- **Supabase (PostgreSQL)** — the managed relational database.
- **Used for:** analytics / event logging and security logging
  (`supabase/security_log.sql`, `supabase/retention.sql`; `llm_calls` per the
  logging spec).
- **Separate concern:** the `ml-sql` Text-to-SQL tool introspects **SQLite and
  PostgreSQL** schemas (`aiosqlite`) — but those are the _user's connected
  databases_, not our own infrastructure.

### 5. Cache system
- **No dedicated cache server** — there is no Redis or Memcached.
- **What covers it today:**
  - In-process model caches (e.g. `_large_vision_cache` dict holding a loaded ONNX
    session).
  - On-disk model cache (`vision_cache/`, `VISION_CACHE_DIR`) so model weights
    aren't re-downloaded each call.
- **Caveat:** HF Space disk is ephemeral — disk cache does not survive a
  restart/rebuild without paid persistent storage.

### 6. Auth
- **No end-user authentication** — there are no user accounts, logins, or sessions.
- **What exists instead:**
  - **Cloudflare Turnstile** (`NEXT_PUBLIC_TURNSTILE_SITE_KEY`) for bot protection
    on abuse-prone endpoints.
  - A Supabase **service-role key** used **server-side only** (never shipped to the
    browser) for privileged writes.

### 7. Hosting system
- **Frontend:** **Vercel** (Next.js native; `output: standalone` only for the local
  Docker path, never on Vercel).
- **Backend:** **Hugging Face Spaces** (Docker) — the live backend.
- **Also present:** `render.yaml` (a Render blueprint for `ml-api` + `ml-vision`)
  and `docker-compose.yml` for local dev — but HF is the deployed backend.

### 8. Secret manager
- **No dedicated secret manager** — there is no Vault, Doppler, or AWS Secrets
  Manager.
- **What covers it today:** platform environment variables —
  - **Vercel env vars** for the site (LLM keys, Supabase keys, Resend, etc.).
  - **Hugging Face Space secrets** for the backend.
- Secrets are referenced by name in code (`process.env.*`), never committed.

### 9. CI/CD
- **GitHub Actions.**
  - ML-Unified: `ci.yml`, `nightly-evals.yml` (scored model-output tests),
    `security-watch.yml`.
  - ml-portfolio: `ci.yml`.
- **Deploy flow:** Vercel auto-deploys the site on push to `main`; the HF Space is
  updated by a **manual upload** step (per project workflow, backend files are
  uploaded to the Space after each backend commit).

### 10. IaC (Infrastructure as Code)
- **Partial only** — declarative config, but no full IaC tool.
  - `Dockerfile`s (per service + portfolio), `docker-compose.yml`, `render.yaml`.
- **No Terraform / Pulumi / CloudFormation.** Infra is provisioned through the
  Vercel / HF / Supabase dashboards.

### 11. Observability / monitoring
- **Home-grown**, no third-party APM.
  - Custom analytics + event logging to **Supabase** (`AnalyticsTracker` component,
    `useAnalytics` hook, `llm_calls` table per the logging spec).
  - `/health` endpoints on the FastAPI services (also used as Render/HF health
    checks).
  - Platform logs (Vercel logs, HF Space run logs).
- **No Sentry / Datadog / Grafana / Prometheus.**

### 12. Cloud platform
- **Vercel** (frontend hosting) + **Hugging Face** (backend Spaces) + **Supabase**
  (managed Postgres) — all managed PaaS.
- **No AWS / GCP / Azure** used directly for infrastructure.

### 13. Embedding
- **Text (RAG):** `all-MiniLM-L6-v2` (default sentence embeddings) and
  `jinaai/jina-embeddings-v3` (dense retrieval), feeding ChromaDB.
- **Images:** **CLIP** (`openai/clip-vit-base-patch32`) — used for image embeddings
  in multimodal RAG and tools like style/face cloaking and photo search.

### 14. LLM
- **Default provider:** **Cohere** (free tier) for the site's chat (`/api/chat`
  falls back to `provider = 'cohere'`).
- **Full provider set:** Anthropic (Claude), OpenAI, Google Gemini, Groq, Mistral,
  Cohere, Perplexity — selectable per feature.
- **Backend RAG** streams via Groq / Claude / Gemini / Cohere
  (`stream_groq_openai`, `stream_claude`, `stream_gemini`, `stream_cohere`).
- **AutoML wizard** offers Gemini 2.5 / Anthropic / OpenAI (GPT-4o Mini) / Groq.
- **Policy:** Gemini is **paid and never a silent default**; no unilateral
  provider/model swaps — provider is explicit per call.

### 15. Agentic framework
- **LangGraph** — an agentic RAG loop (`StateGraph`) behind `POST /rag/agent`
  (SSE streaming), in `routers/rag/agent.py` + `agent_nodes.py`.
- **Soft dependency:** if `langgraph` isn't installed, the endpoint **degrades
  gracefully** to direct retrieval (`_LANGGRAPH_OK` guard) — it is not pinned in
  `requirements.txt`.
- **Related patterns:** CRAG (corrective RAG, `crag.py`), a query router
  (`query_router.py`), and graph retrieval (`graph_retrieve.py`). The QA /
  Testwright platform runs its own Author/Run/Discover/Heal stage loop separate
  from LangGraph.

### 16. Storage
- **No dedicated object storage** — there is no S3 or Supabase Storage bucket for
  user files.
- **What covers it today:**
  - Files are processed **in-memory** or on the Space's **ephemeral disk**;
    model weights are cached on disk (`vision_cache/`).
  - Browser-side exports (CSV / GIF / PDF) are built client-side via
    `Blob` + `URL.createObjectURL` and downloaded — nothing is persisted server-side.
- **Caveat:** HF Space disk does not survive restart/rebuild, so anything written
  there is temporary by design.

### 17. Testing
- **Backend:** **pytest** (+ `pytest-playwright`); config in `pytest.ini` /
  `conftest.py`. Two tiers — deterministic shell gets **hard assertions per push**
  (CI), model output gets **scored property assertions nightly**
  (`nightly-evals.yml`).
- **Frontend:** **Vitest** (unit) + **Playwright** (`@playwright/test`, end-to-end
  UI checks).
- **Runs via** GitHub Actions on every push, plus the nightly eval workflow.

### 18. Blue-green deployment
- **Not used as a named blue/green setup** — but the effect is covered where it
  matters:
  - **Vercel** deploys are **atomic and immutable** — each push builds a new
    immutable deployment and the production alias is flipped to it, giving
    zero-downtime releases and **instant rollback** (promote a previous
    deployment). This is Vercel's model, not classic blue/green, but delivers the
    same safety for the site.
  - **Hugging Face Space** rebuilds **in place** — during the 2-5 min rebuild the
    Space serves proxy 500s (brief unavailability). There is no second
    environment to cut over to; this is why backend deploys are **batched and
    verified once** rather than shipped one at a time.

---

## External services (not infra, but part of the picture)

- **LLM providers:** Anthropic, OpenAI, Google Gemini, Groq, Mistral, Cohere,
  Perplexity. (Gemini is paid and never a silent default; Cohere/Groq free tiers in
  active use.)
- **Web search:** Tavily.
- **Email:** Resend.
- **News:** NewsAPI.

---

## Accessing the API docs (auto-generated)

FastAPI auto-generates interactive API docs from the code. None of the three
services disable them (`docs_url` is left at its default), so every service exposes:

- `/docs` — **Swagger UI**, interactive: expand an endpoint, click **"Try it out"**,
  and fire a real request from the browser.
- `/redoc` — **ReDoc**, a cleaner read-only view of the same spec.
- `/openapi.json` — the raw **OpenAPI** spec (machine-readable).

**The port only appears locally.** `<url>:<port>/docs` is how you reach a server on
your own machine; once deployed to a real domain the port is implied (443 for HTTPS)
and drops out of the URL — you use **domain + `/docs`**.

**Live (main backend, verified 200):**
- https://wram1708-ml-unified.hf.space/docs
- https://wram1708-ml-unified.hf.space/redoc
- https://wram1708-ml-unified.hf.space/openapi.json

**Local:**
```bash
cd services/ml-api
uvicorn app:app --reload --port 8000
# then open http://localhost:8000/docs
```

The other services (`ml-sql`, `ml-vision`) each have their own `/docs` at their own
URL/port — they are separate FastAPI apps.

---

## Summary of the gaps (deliberate, and fine for a portfolio)

| Category | Gap | Covered today by | Add later if scaling |
|---|---|---|---|
| Cache | No Redis/Memcached | In-process + disk cache | Redis / Upstash (shared, survives restarts) |
| Auth | No user accounts | Turnstile + service-role key | Supabase Auth or NextAuth (accounts/sessions) |
| Secret manager | No Vault/Doppler | Vercel + HF env vars | Doppler / Vault (rotation, audit, one source) |
| IaC | No Terraform/Pulumi | Docker + render.yaml | Terraform (reproducible infra) |
| Observability | No APM | Supabase logs + /health | Sentry (errors) + Grafana/Prometheus (metrics) |
| Storage | No object store | In-memory + ephemeral disk + client-side blobs | S3 / Supabase Storage (durable user files) |
| Blue-green | No named blue/green | Vercel atomic immutable deploys | Second HF Space + alias cutover for the backend |

None of these block a portfolio/demo project. They are the first things to
introduce only if AIRaML ever grows real, sustained traffic or paying users.
