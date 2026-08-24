# Conversation — Part 159
**Date:** 2026-07-05  
**Topics:** Housekeeping · TC-P8 Complete · Drift Data Versioning  
**Commits:** `a22f6a4` `18008d9` `10858f6` `63f4d91` (ML-Unified) · `8715672` (ml-portfolio)

---

## Summary

Housekeeping session: file moves, memory updates, enterprise RAG discussion, TC-P8 completed (90 TCs), then drift data versioning (item #23) implemented with batch-over-batch comparison, compare-to-training toggle, and SHA-256 dedup.

---

## Work Done

### 1. File Housekeeping

- `Testing_Complete_Guide.md` deleted — duplicate of `Conversations/testcases/TC-P3.md`
- `Conversations/testcases.md` moved to `Conversations/testcases/testcases.md` — index now lives alongside the files it references
- `CLAUDE.md`, `RAG_Implementation_Roadmap.md`, `.claude/settings.json` committed to git (were untracked) — commit `a22f6a4`

### 2. Memory Updates

- `reference_testcases.md` created — path to test case index and TC files
- MEMORY.md updated with testcases reference entry
- `RAG_Implementation_Roadmap.md` updated with two new sections: "What is Enterprise-Grade RAG?" and "Is Our RAG Enterprise-Grade?"

### 3. Enterprise-Grade RAG Discussion

**What enterprise-grade means:** hybrid retrieval, distributed vector store, multi-tenancy, observability, guardrails, auth+governance, eval CI, SLA.

**Our RAG:** retrieval architecture qualifies (hybrid BM25+dense, reranking, CRAG, semantic cache, tiered retrieval, LangGraph, confidence scoring). Infrastructure gaps: ChromaDB in-process, no RAGAS in CI, no guardrails, no auth scoping, HF Space free tier, logical-only tenant isolation.

Verdict: retrieval quality = enterprise-grade; deployment/ops = not yet.

### 4. TC-P8 Completed (90 TCs)

Round 4 — two passes, inline (no subagents):

| Area | TCs |
|------|-----|
| RAG pipeline backend (query SSE, ingest, CRAG, cache, tiered retrieval, edge cases) | 28 |
| Chat AI frontend (badge, sources, web override, How I Searched, latency) | 15 |
| Drift detection (scores, history, labels, percentile shift, correlation, LLM explain) | 12 |
| AutoML Pipeline / Pipeline Builder (context wiring, downloads, SHAP+Optuna) | 12 |
| Feature Engineering (datetime, ratio/diff, binning, polynomial, presets) | 9 |
| Ensemble (SVG medals, accent color, leaderboard names, CV scores) | 4 |
| SHAP, Optuna, AutoML wizard, KB quality | 10 |

Total across all TC files: **~1,020 TCs**. testcases.md index updated.

### 5. Pending.md Review

- Item #23 (drift versioning): kept pending → now completed this session
- Item #28 (GPU toggle): still pending
- MLOps items (#39–44): still pending
- "How I Searched": confirmed complete (user clarified)

### 6. Drift Data Versioning (Item #23)

**Design:**
- V1 = training baseline (always from fitted sklearn pipeline, never stored in versions file)
- V2+ = uploaded batches, each compared against previous by default
- `compare_to_training=true` → always compare against V1
- Duplicate upload (same SHA-256 hash as previous version) → silently skips version creation, still returns drift results

**Backend changes (`18008d9`, `10858f6`, `63f4d91`):**

`_state.py`:
- `_versions` dict + `_VERSIONS_FILE = data/drift_versions.json`
- `load_all()` loads versions on startup
- `save_version(model_id, label, stats, file_hash)` — appends new version
- `get_versions()`, `get_previous_version_stats()`, `get_previous_version_hash()`

`_baseline.py`:
- `extract_batch_stats(schema, rows)` — computes mean/std per numeric column from batch rows
- `baseline_from_version_stats(version_stats)` — converts stored stats to baseline format for `compute_drift`

`__init__.py` (drift router):
- Upload endpoint: SHA-256 hash check → skip version if duplicate (no error, results still returned)
- `compare_to_training` query param (bool, default False)
- Response includes `version_num`, `compared_against`, `compared_against_v`
- `GET /drift/{model_id}/versions` — returns all versions including V1 as virtual entry

**Frontend changes (`8715672`):**

`driftTypes.ts`:
- `DriftVersion` type added
- `DriftResult` extended with `version_num?`, `compared_against?`, `compared_against_v?`

`DriftRunner.tsx`:
- `compareToTraining` state + pill toggle switch
- `versions` state; fetched on model change and after each upload
- Preview: "will compare vs [previous batch label]" shown before upload
- After results: version badge "V3 compared against V2 · Batch 1"
- Upload URL includes `compare_to_training=true` param when toggle active

**Key decision:** duplicate = same SHA-256 bytes. Different file (even one row changed) = new version. No content-similarity check (would give false negatives on genuinely different files with similar stats).

---

## Files Changed

| File | Repo | Change |
|------|------|--------|
| `routers/drift/_state.py` | ML-Unified | versions store + persistence |
| `routers/drift/_baseline.py` | ML-Unified | batch stats extraction |
| `routers/drift/__init__.py` | ML-Unified | versioning logic + hash dedup + versions endpoint |
| `src/app/tools/drift/driftTypes.ts` | ml-portfolio | DriftVersion type + DriftResult fields |
| `src/app/tools/drift/DriftRunner.tsx` | ml-portfolio | toggle + version badge |
| `Conversations/testcases/TC-P8.md` | docs | 90 TCs written |
| `Conversations/testcases/testcases.md` | docs | moved + updated |
| `RAG_Implementation_Roadmap.md` | docs | enterprise RAG sections added |
| `Conversations/pending.md` | docs | #23 marked done |
| `memory/reference_testcases.md` | memory | new reference entry |

---

## Real-World Project Ideas (Resume / Portfolio)

Discussed at end of session — user looking for end-to-end AI/ML project beyond ML-Unified to add to resume.

### Context
ML-Unified already covers: AutoML, drift detection, RAG, SHAP, Optuna, Feature Engineering, Ensemble. Gap: agentic AI, LLM fine-tuning, time series, document intelligence.

### What's Hiring in 2026
- RAG architecture appears in 65% of applied LLM job listings
- LLM fine-tuning (LoRA/QLoRA) in most LLM engineer JDs
- MLOps/Kubernetes/Docker in 75%+ of senior ML posts
- Text-to-SQL / NL-to-data in analytics/BI roles
- Domain specialisation now screened at JD level (generalists filtered out)

### Shortlisted Projects

| Project | Why Valuable | Complexity |
|---------|-------------|------------|
| **Text-to-SQL Agent** | NL → SQL → results; LLM + tool use + DB; shows up in 40%+ of AI engineer JDs | Medium |
| **LLM Fine-tuning Pipeline** | LoRA/QLoRA on domain dataset, eval, serve; required by most LLM engineer roles | High |
| **Document Intelligence** | Extract structured data from PDFs/invoices/contracts (vision+LLM); massive enterprise demand | Medium |
| **Time Series Forecasting** | Prophet/ARIMA/LSTM for real domain (sales/energy/finance); evergreen, classic | Medium |
| **Multimodal RAG** | PDFs with figures/tables → image+text chunking → cited answers; bleeding edge | High |

### Recommendation
**Text-to-SQL Agent** — most demonstrable, builds on existing RAG infrastructure, covers NL query → schema grounding → SQL generation → self-correction loop → result display. Decision deferred to next session.

### Sources
- [Most In-Demand ML Roles 2026](https://www.acceler8talent.com/resources/blog/the-most-in-demand-machine-learning-roles-in-2026--managing-the-ai-talent-frontier/)
- [Top AI Engineering Skills 2026](https://www.secondtalent.com/resources/most-in-demand-ai-engineering-skills-and-salary-ranges/)
- [AI/ML Engineering Jobs 2026 Analysis](https://axialsearch.com/insights/ai-ml-engineering-jobs/)
- [ML Projects for Resume](https://www.projectpro.io/article/machine-learning-projects-for-resume/466)
- [33 ML Projects 2026 — DataCamp](https://www.datacamp.com/blog/machine-learning-projects-for-all-levels)
- [21 AI Project Ideas — InterviewQuery](https://www.interviewquery.com/p/ai-project-ideas)

---

## Pending After This Session

| Item | Notes |
|------|-------|
| #28 GPU toggle | Not started |
| #39 Model versioning + rollback | Not started |
| #40 Drift alerting | Email/Slack on drift threshold breach |
| #41 LLM feature suggestions after EDA | RAG-powered |
| #42 Automated retraining pipeline | Not started |
| #43 Time series forecasting | Prophet/ARIMA/LSTM |
| #45 E2E Playwright in CI | Suite exists locally, not wired to CI |
| #47 Dockerize ml-eda + ml-vision | ml-api Dockerfile done |
| #50 Batch predictions (vision) | Not started |
