# Conversation — 2026-07-01 — RAG Phase 2 Features + Critical Root-Cause Debugging (Part 139)

## Summary
Continued from Part 138. Shipped RAG Phase 2 features (reranker UI polish, document upload/delete management, stopword filtering, query expansion). Then a user bug report ("wrong source shown") triggered a long debugging chain that uncovered the RAG knowledge base had been **completely empty since Phase 1 shipped** — a Docker build bug, not a retrieval/reranking bug. Also found and fixed a second critical bug where one corrupted model pickle was silently blocking ALL trained models from loading app-wide. Session ended with full live verification via Playwright on the deployed site.

---

## Part A — RAG Phase 2 Features (continuing Part 138's reranker work)

### 1. Document upload progress UI
- `RagIngestButton.tsx` switched from `fetch` to `XMLHttpRequest` for real upload progress events
- New `IngestStatus` type: idle / uploading(%) / processing / ok / deleted / error
- `RagIngestBanner.tsx` (new): progress bar, "Indexing document…", success/error messages
- Banner moved from inside the scrollable messages `<div>` to above it — was invisible once a conversation scrolled past the top (user-reported bug, fixed same session)
- Upload button moved from the empty-state welcome screen (disappeared after first message) into the always-visible header — second user-reported placement bug, fixed

### 2. Document management (delete uploads)
- Backend: `routers/rag/ingest.py` — `index_chunks()` gained `uploaded: bool` param, tags chunk metadata + tracks `state.uploaded_sources: set[str]`; `delete_source()` helper removes a source's chunks from ChromaDB + rebuilds BM25; `GET /rag/uploads` lists uploads; `DELETE /rag/uploads/{source}` removes one (404 if not a tracked upload — KB docs protected)
- `RagState` (`__init__.py`) gained `uploaded_sources: set[str]`
- Frontend: `RagUploadsPanel.tsx` (new) — popover listing uploads with delete buttons, click-outside-to-close
- Duplicate-upload detection: re-uploading the same filename now returns 409 instead of silently double-indexing (`ingest.py`)

### 3. Stopword filtering (BM25 contamination fix)
- `routers/rag/text.py` (new): `tokenize()` strips ~150 common English stopwords before BM25 scoring
- Root problem this fixed: a large generic uploaded PDF could out-rank short on-topic KB chunks purely via shared filler words ("the", "is", "and"); `bm25_retrieve` previously used raw `.lower().split()`

### 4. Query expansion
- `routers/rag/llm.py` (new): extracted the 4 provider streaming generators (groq/openai, claude, gemini, cohere) out of `query.py` into a shared module + `complete()` non-streaming wrapper
- `routers/rag/expand.py` (new): `expand_query()` asks the LLM for 2 alternate phrasings before retrieval (best-effort, falls back to original query on failure)
- `retrieve.py`: `multi_query_retrieve()` runs `hybrid_retrieve` per variant, RRF-merges across all variants; final reranking still scores against the **original** query, not variants
- `query.py` shrank 283 → 180 lines after extracting stream helpers

### 5. Unrelated fix: `/api/ai-tools` Cohere support + gpt-4o-mini default bug
- User's Feature Engineering "AI Suggest" / Feature Selection "AI Suggest Methods" buttons were 404ing with `gpt-4o-mini does not exist`
- Root cause: `route.ts`'s generic OpenAI-compat branch defaulted **every** provider's model to `"gpt-4o-mini"` when unspecified — `useFEAISuggest`/`useFSAISuggest` request `provider: "groq"` with no model, so `gpt-4o-mini` got sent to Groq's endpoint
- Fixed: added `DEFAULT_MODELS` map (one default per provider) instead of one hardcoded fallback
- Added full Cohere support to `route.ts` (`callCohere()` — Cohere's v2/chat API isn't OpenAI-compatible, had no handler before)
- Switched both AI Suggest hooks to `provider: "cohere"` (uses existing `COHERE_API_KEY` Vercel env var, per user's explicit request)

---

## Part B — Critical Root-Cause Debugging Chain

### Trigger
User reported: asked "which columns need normalization?" → got 2 sources from an irrelevant previously-uploaded `Claude_Code_Documentation_03062026.pdf` PDF, both at 0% confidence — confirming a real contamination bug. Initial hypothesis was reranker/relevance-floor miscalibration.

### Investigation path
1. Added debug logging (`RERANK DEBUG` in `rerank.py`) + fixed that `logging.basicConfig()` was never called anywhere — `uvicorn` only configures its own loggers, so every `logger.info()` across `routers/` (including pre-existing RAG init logs) was silently dropped and never reached HF Space logs. Added to `app.py`.
2. First real log line revealed the actual root cause: `KB dir 'data/knowledge_base' not found — starting with empty index` / `RAG initialized — 0 chunks in corpus, 0 in ChromaDB`. **The entire 13-doc knowledge base had never been indexed, since Phase 1.**
3. Found why: `Dockerfile` never had `COPY data/ data/` (only `app.py`, `routers/`, `shared/`, `frontend/`, `models/`, `schemas/` were copied into the image) — the KB markdown files existed in the HF Space git repo but never reached the running container.
4. Found a second blocker: `.dockerignore` excludes `*.md` globally — even with the COPY fix, Docker's build context wouldn't see the KB files at all. Added `!data/knowledge_base/*.md` exception.
5. After rebuild, hit a third bug: `PermissionError: [Errno 13] Permission denied: 'data/chroma_db'` — `COPY data/ data/` ran before `USER appuser`, so the copied directory was root-owned; `appuser` couldn't create `chroma_db` inside it. Fixed with `COPY --chown=appuser:appuser data/ data/`.
6. After that rebuild: KB finally indexed successfully — `98 chunks in corpus, 98 in ChromaDB`, `/rag/health` returned `initialized: true`.

### Second major bug found in the same debugging pass
- User noticed the ML-Unified app's model sidebar (Titanic/Iris/Diabetes/Insurance classifiers) had gone empty
- Investigation confirmed via `/models` returning `[]` and Space logs showing: `ERROR: _load() failed: Can't get attribute 'FeatureEngineeringTransformer' on <module 'app' from '/app/app.py'>` — a stale pickle (`80-cereals_fe.pkl`) failing to unpickle due to a module-path mismatch from an old code layout
- Root cause: `_load()` in `routers/core/shared.py` had **zero per-model error handling** — one bad file anywhere in the alphabetically-sorted loop crashed the entire function, meaning `diabetes`/`insurance`/`iris`/`titanic` (sorting after `80-cereals`) never got a chance to load even though they were fine
- This had been a latent bug for a long time — the container apparently hadn't restarted in a long while, so it only surfaced when today's Dockerfile changes forced the first real restart
- Fixed: wrapped each model's load in `_load()` in its own try/except — one broken pickle now gets skipped with a warning instead of taking down everything

### Cleanup: stale test models
- Once `_load()` stopped crashing, 6 leftover test/training-run artifacts appeared in the sidebar: `debug-test`, `ensemble-run`, `my-automl-model`, `optuna-run`, `shap-run`, `titanic-model` — plus 2 more found via direct repo inspection: `80-cereals` (the broken one) and `ce`
- Attempted deletion via the existing `DELETE /models/{id}` endpoint — got 500 errors. Root cause: same root-owned-directory permission issue (`models/`/`schemas/` were never `chown`'d either) blocked `os.remove()` even though `MODELS.pop()` succeeded in memory
- Fixed `Dockerfile` to `chown` `models/` and `schemas/` directories too
- Hardened `delete_model()` in `monitoring.py`: added `_BUILTIN_IDS` guard (previously `titanic`/`iris`/`diabetes`/`insurance` had **zero** protection against accidental deletion via this endpoint!) and wrapped file removal in try/except so a permission failure degrades gracefully instead of a 500
- Permanently deleted all 35 files for the 8 stale model IDs directly from HF Space storage via the Hub API (bypassing the broken endpoint since the fix hadn't deployed yet)

### Relevance floor recalibration
- Real debug data showed a genuinely correct match (`feature_engineering.md` for "is it bad if some of my numbers are super skewed?") scoring only **2.8%** absolute sigmoid confidence, while all noise scored 0.000 — confirming the fixed 30% absolute floor (set in Part 138) was rejecting correct answers
- Switched `rerank.py` from absolute floor to **relative threshold**: top match must clear a tiny 1% sanity floor, additional chunks kept only if ≥30% of the top match's score
- Added `display_score` (relative to top match, top=100%) sent alongside the raw `score` — UI badge now shows the relative percentage (intuitive) while raw absolute confidence is available via tooltip + expanded detail view ("Raw model confidence: X%") for users who want to actually assess true confidence rather than relative ranking

---

## Live Verification (Playwright, end of session)

Two real spot checks against the deployed site (https://ml-portfolio-rho.vercel.app):

1. **AutoML page** — "why might XGBoost outperform Random Forest on this dataset?" → 7 relevant sources (`xgboost_guide.md`, `ensemble_methods.md`, `lightgbm_guide.md`, `optuna_tuning.md`, `sklearn_algorithms.md`, `ml_best_practices.md`, `catboost_guide.md`), confidence 64-98% raw, well-grounded markdown-formatted answer
2. **Ensemble page** — "how does stacking pick a meta-learner?" → detailed accurate answer (OOF predictions, meta-learner regularization, LogisticRegression/Ridge/Lasso recommendations) matching actual `ensemble_methods.md` content, correct page-specific accent label

Both confirmed the full pipeline — KB indexing, hybrid retrieval, query expansion, reranking, relative confidence scoring — working correctly end-to-end for the first time this session, after multiple infra layers were fixed.

---

## Commits

### ML-Unified
| Hash | Description |
|------|-------------|
| 5ec97bc | feat(rag): Phase 2 step 1-2 — cross-encoder reranking |
| ade15ce | fix(rag): reject duplicate uploads |
| 64df6cd | debug(rag): log pre-filter rerank scores; fix logging not configured |
| 0628d72 | feat(rag): stopword filtering, strict 30% relevance floor, document delete |
| 06631f4 | feat(rag): Phase 2 — query expansion before retrieval |
| 85765d0 | fix(rag): KB markdown files never reached the Docker image |
| c0a7eef | fix(rag): chown data/ to appuser |
| bcb4698 | fix(backend): one bad model pickle was blocking ALL models from loading |
| ad72964 | fix(backend): chown models/+schemas/; harden delete_model endpoint |
| a13dfc9 | fix(rag): calibrate relevance filtering — relative threshold, not absolute floor |

### ml-portfolio
| Hash | Description |
|------|-------------|
| 920c342 | feat(rag): real upload progress bar + indexing/success/error banner |
| 088a75f | fix(rag): upload button always available |
| 30e52a0 | fix(rag): hide sources panel by default |
| 1d82273 | feat(rag): document upload UI |
| 66f744d | feat(rag): manage/delete uploaded documents; new confidence tier bands |
| e9eb284 | fix(ai-tools): add Cohere support; fix gpt-4o-mini default leaking |
| 8136eb8 | fix(rag): upload progress banner always visible |
| a6b837e | fix(rag): render display_score instead of raw absolute score |
| f9aa920 | feat(rag): expose raw absolute confidence alongside relative display score |
| 3e6b3e7 | feat(chat): replace Together AI with Cohere in ToolsAIChat provider selector |
| 9851b7b | fix(chat): Cohere — remove deprecated Command R+, keep command-a-03-2025 only |

---

## Part C — Post-Verification Fixes

### 1. Cohere in ToolsAIChat provider selector
- User requested replacing "Together AI" with "Cohere" in the chat panel's provider pill selector
- `toolsAiProviders.ts`: swapped `together` entry for `cohere` (id, label, color, models, envKeyNote)
- Initial commit included `command-a-03-2025` + `command-r-plus` — user corrected that `command-r-plus` is deprecated; updated to single model `command-a-03-2025` ("Command A 03-2025")
- `envKeyNote` set to "Default key provided" since `COHERE_API_KEY` already in Vercel env — works out of the box like Gemini
- No backend changes needed — `callCohere()` and `resolveKey` for cohere were already wired into `/api/ai-tools/route.ts` earlier this session

### 2. E402 lint fix in app.py
- CI lint job (`Lint ml-api`) failed with `E402 Module level import not at top of file` — 16 errors
- Root cause: `logging.basicConfig(...)` call was inserted between stdlib imports (lines 3-6) and third-party/local imports (lines 13-33) in `app.py`; flake8 E402 flags every module-level import appearing after a non-import statement
- Fix: moved `logging.basicConfig()` to **after** all imports (keeping same functional behavior — Python's logging config is applied at module load regardless of where in module-level code it appears)
- Uploaded fixed `app.py` to HF Space

| Hash | Description |
|------|-------------|
| bb53ee9 | fix(lint): move logging.basicConfig() after imports — fixes E402 |

---

## Playwright Spot Check (end of session, before Part C)
- AutoML page: "why might XGBoost outperform Random Forest?" → 7 sources (xgboost_guide.md, ensemble_methods.md, lightgbm_guide.md, optuna_tuning.md, sklearn_algorithms.md, ml_best_practices.md, catboost_guide.md), confidence 64-98% raw, grounded markdown answer ✅
- Ensemble page: "how does stacking pick a meta-learner?" → detailed accurate answer from ensemble_methods.md, Sources (3) toggle ✅
- Both confirmed full pipeline working end-to-end: KB indexing, hybrid retrieval, query expansion, reranking, relative confidence scoring

---

## Key Lessons / Architecture Notes
- **CLAUDE.md updated**: Rule 2 changed from "always use subagents for 2+ files" to "be deliberate — only for genuinely independent/parallel work; do 1-2 file tasks directly"
- The entire "wrong source" debugging saga traced back to **infrastructure**, not RAG logic — Docker COPY/`.dockerignore`/file-ownership bugs. When RAG behavior looks fundamentally broken, check `/rag/health` chunk count before assuming the algorithm is wrong.
- `data/`, `models/`, `schemas/` in the Dockerfile all needed `--chown=appuser:appuser` — any future new directory added needs the same treatment if the app will ever write into it at runtime.
- `_BUILTIN_IDS` existed as a constant but was never enforced in the delete endpoint — safety gap now closed.
- Container hadn't restarted in a long time — several latent bugs (stale pickle, permission issues, empty KB) only surfaced when a restart was finally forced by Dockerfile changes.
- `logging.basicConfig()` must go **after** all imports to avoid E402; Python executes it at module load time regardless of position within module-level code.
