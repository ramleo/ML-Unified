# Conversation — 2026-06-16 — ML-Unified — Part 87

---

## Session Summary

Discussed VS Code tab layout issue, microservices architecture, and created microservices reference document. No code changes this session.

---

## Topics Covered

### 1. VS Code File Opening in Wrong Pane
**Problem:** When opening a file it moves to right pane alongside Claude conversation instead of left pane.
**Finding:** `workbench.editor.openSideBySideDirection: "left"` is not a valid value — only `"right"` or `"down"` accepted.
**Actual fix:** One-time manual layout setup — split editor with `Cmd+\`, drag Claude panel to far right (secondary side bar), files will then open in left group by default. VS Code remembers layout.
**User's current setting:** `claudeCode.preferredLocation: "panel"` — Claude is in bottom panel, not right side bar.

---

### 2. Microservices Discussion
**Question:** Where can microservices be used in ML Unified?

**Answer:** Not practical in current HF Space setup (single container). Makes sense when moving to proper cloud (AWS/GCP/Azure).

**9 candidate services identified:**
1. Training Service — async job queue, unblocks concurrent users
2. Inference/Prediction Service — lightweight, scales horizontally
3. SHAP/Explainability Service — heavy compute, on-demand
4. AutoML Service — parallel trials across workers (4× speedup)
5. LLM Explanation Service — external API calls, key vault isolation
6. Model Storage/Persistence Service — S3/GCS/HF XET adapter
7. Feature Engineering Service — shared between train and predict
8. Clustering/Unsupervised Service — different workload, independently deployable
9. Monitoring/Drift Service — scheduled background job

**Priority for cloud migration:** Training → Inference → AutoML → SHAP → Storage → LLM → FE → Clustering → Monitoring

**Full reference document:** [Microservices_Architecture_Notes.md](Microservices_Architecture_Notes.md)

---

## No Commits This Session

---

## Pending Items

| Priority | Item | Status |
|----------|------|--------|
| Next | Phase 9: Ensemble / stacking | Not started |
| Low | Phase 10: Pipeline export | Not started |
| Low | Phase 11: Encoding per-column | Not started |
| Low | Phase 12: GPU toggle | Not started |
| Low | Phase 13: SMOTE | Not started |
| User action | Retrain 80 Cereals model | Pending |
| Future | Microservices migration (when off HF Space) | Reference doc created |

---

## Process Reminders

- Playwright: maximize window on open, close browser after deploy confirmation
- Always screenshot UI changes before deploying
- Always commit ID + push to GitHub + upload to HF after every change
