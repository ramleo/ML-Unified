# Conversation — 2026-06-11 — ML-Unified — Part 55

---

## Session Summary

Cleaned up pending list, confirmed completed items, discussed and planned #11 Cleaned CSV Download feature. Not yet implemented.

---

## Items Confirmed Done (this session)

| Item | Notes |
|------|-------|
| #14 Side-by-side vision results | `.ip-before-after` layout present in all 3 vision panels |
| #16 Vision ambient themes | `setAmbientTheme()` implemented per panel |
| #12 EDA microservice extraction | `services/ml-eda/` is a full standalone FastAPI service |
| ML_EDA_URL on Render | Verified set by user |

---

## Untracked Refactor Files — Deleted

Draft refactor files (`routers/config.py`, `inference.py`, `monitoring.py`, `shared/`) deleted. Decision: deferred until `app.py` exceeds ~1500 lines. See memory: `project_refactor_plan.md`.

---

## .gitignore Updated

Added local artifacts to `.gitignore` (commit `cd290ce`):
- `.playwright-mcp/`, `Conversations/`, `conversation.md`, `*.png`, `test_clusters.csv`

---

## Revised Pending List

**Active:**

| # | Item |
|---|------|
| #20 | Playwright E2E tests |
| #22 | Dockerize full app |
| #11 | Cleaned CSV download — **planned, not yet started** |

**Deferred:**

| # | Item |
|---|------|
| #21 | Batch predict — Object Detection + Segmentation |
| #5  | Proxy page |

---

## #11 Cleaned CSV Download — Full Design (agreed, not yet built)

### Where: added to `ml-eda` service (not a separate microservice)

### Backend — new `POST /eda/clean` endpoint in `ml-eda/routers/eda.py`

**Input:** CSV file + config JSON
**Output:** Cleaned CSV (file download) + summary JSON

```
config: {
  dedup: true,
  drop_id_cols: [col1, col2],         # user-confirmed list
  imputation: {
    method: "none|mean|median|mode|constant|knn|mice|ffill|bfill|interpolate",
    constant_value: ...,
    knn_k: 5,
  },
  outliers: {
    enabled: false,
    method: "iqr|zscore|winsorize",
    threshold: 1.5
  },
  power_transform: false              # Yeo-Johnson on numeric cols
}

summary: { rows_before, rows_after, cols_dropped, missing_before, missing_after, outliers_removed }
```

### Dedup
- Always shown, default ON
- `df.drop_duplicates()`, show count removed

### Drop ID Cols
- Auto-detect: uniqueness ratio > 95% AND string/integer type
- Show checklist of detected columns — all checked by default
- User can uncheck any to keep; also manual add via dropdown
- All columns shown at once, one-time selection
- Summary: "Dropping 2 of 3 detected: PassengerId, Ticket. Keeping: Name."

### Imputation Options
| Method | Availability | Speed warning |
|--------|-------------|---------------|
| None | Always | — |
| Mean / Median / Mode / Constant | Always (sklearn SimpleImputer) | — |
| KNN (k=5) | Always (sklearn KNNImputer) | Slow on > 10k rows |
| IterativeImputer / MICE | Always (sklearn, experimental) | 30s+ on large datasets |
| ffill / bfill / interpolate | Always (pandas) | Show only if time-series detected |
| miceforest | Optional — greyed out if not installed | Heavy |
| fancyimpute | Optional — greyed out if not installed | Heavy |

- miceforest/fancyimpute: `try: import miceforest` at runtime — if fails, show disabled with tooltip "Not available on this server. Add to requirements.txt to enable."
- **Global warning** regardless of method: "Processing time depends on dataset size, missing values, and server load."

### Outlier Removal
- Toggle (default OFF)
- Method: IQR (default) / Z-score / Winsorize
- Threshold: IQR multiplier or z-score cutoff (user configurable)

### Power Transform
- Toggle (default OFF)
- Yeo-Johnson via `sklearn.preprocessing.PowerTransformer`
- Applied to numeric columns only

### Frontend — "Clean & Download" panel
- New `eda-section-card` added at bottom of EDA results
- Added to sticky nav as "Clean & Export"
- Sections: Dedup toggle → ID col checklist → Imputation selector → Outlier removal → Power transform → Before/after summary card → Download button
- No new dependencies needed

### New dependencies: None required
- miceforest/fancyimpute optional via try/import

---

## Sub-agent Plan (for next session)

User asked about using sub-agents to implement this feature to save tokens. Agreed to use:
1. Sub-agent builds backend `POST /eda/clean` endpoint
2. Sub-agent builds frontend Clean & Download panel
3. Main agent reviews and integrates
