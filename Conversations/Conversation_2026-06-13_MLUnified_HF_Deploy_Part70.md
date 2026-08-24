# Conversation — 2026-06-13 — ML-Unified — AutoML Fixes Part 70

---

## Session Summary

Three AutoML fixes this session: (1) F1 score as hero metric instead of Accuracy; (2) Animated step-by-step progress bar for preprocessing; (3) High-cardinality column drop UI + correct feature selection order.

---

## Fix 1 — F1 as Hero Metric (not Accuracy)

### Problem
AutoML winner card showed "82.0% ACCURACY" even though F1 was already the primary metric in the `/train` endpoint. The hero card in `_renderAutoMLReport()` displays `selection_metric` from `/automl/preprocess`, which was still "Accuracy" for non-imbalanced classification.

### Root Cause
In `app.py` line 1172-1173 (AutoML CV scoring):
```python
# OLD (wrong)
sel_metric = "f1_macro" if is_imbal else "accuracy"
sel_label  = "F1-macro" if is_imbal else "Accuracy"
```
The CV winner selection used accuracy scoring, so the hero score (e.g. 82.0%) WAS accuracy. The `/train` endpoint separately returned F1 but the hero card never used it.

### Fix
```python
# NEW (correct)
sel_metric = "f1_macro" if is_imbal else "f1_weighted"
sel_label  = "F1-macro" if is_imbal else "F1 (weighted)"
```
Now CV scoring uses `f1_weighted` for balanced classification. The hero card label becomes "F1 (weighted)" and the score is the actual F1 value.

**Commit:** `754904d` (GitHub) / `017027f` (HF)

---

## Fix 2 — Animated Preprocessing Progress Bar

### Problem
When user clicked "Apply Preprocessing", the button just showed "Preprocessing…" text with no feedback on what was happening.

### Fix
Added a 5-stage animated progress bar below the action buttons. HTML added in Step 1.5:
```html
<div id="amlPrepProgress" style="display:none;margin-top:1rem">
  <div style="...">
    <span id="amlPrepProgLabel">Analyzing data…</span>
    <span id="amlPrepProgPct">0%</span>
  </div>
  <div style="height:5px;...">
    <div id="amlPrepProgBar" style="width:0%;background:var(--active-accent);transition:width 0.5s ease"></div>
  </div>
  <div id="amlPrepStepDots"></div>
</div>
```

JS stages (timed with setTimeout):
| Delay | % | Label |
|-------|---|-------|
| 0ms | 10% | Analyzing data… |
| 600ms | 30% | Handling missing values… |
| 1300ms | 55% | Encoding categorical columns… |
| 2100ms | 72% | Treating outliers & skewness… |
| 3000ms | 85% | Running feature selection… |

- Step pills turn purple as each stage is reached
- On success: bar turns green, all pills green, label "Done!", hides after 1.2s
- On error: bar turns red, label "Failed", hides after 2s, error shown below
- `timers.forEach(clearTimeout)` called on both success and error paths

**Commit:** `754904d` (GitHub) / `017027f` (HF)

---

## Fix 3 — High-Cardinality Column Drop UI + Correct Feature Selection Order

### Problem 1 — OHE Explosion
Titanic with `Name` column (891 unique values) + one-hot encoding → 12 columns exploded to 1178 columns. Feature selection top_k=10 then picked 10 OHE dummy columns (e.g. `Name_Mr. John Smith`) instead of 10 real features.

### User's Clarification (3 points)
1. **top_k runs AFTER encoding** — encoding may expand columns, that's correct, then top_k trims them
2. **High-cardinality columns** (>20 unique) should be shown to user BEFORE preprocessing — let user decide per column: keep or drop
3. **Multiple encoding methods already exist** — the fix is point 2, not capping OHE

### Wrong Intermediate Fix (reverted)
I incorrectly moved feature selection to run BEFORE encoding (temp-ordinal approach). User corrected this. Also incorrectly added `OHE_CARD_LIMIT = 20` cap — reverted.

### Correct Fix

**Frontend — Step 1.5 high-cardinality section:**
- Detects all columns (excluding target) with `nunique > 20`
- Shows them in a yellow warning box when user clicks "Yes, preprocess"
- Each column listed with checkbox (pre-checked = will be DROPPED)
- User unchecks any column they want to KEEP
- Shows unique value count next to each column name

```javascript
const highCardCols = a.columns.filter(c =>
  c.name !== effectiveTarget && (c.nunique || 0) > 20
);
```

Generated HTML (per column):
```html
<label style="...">
  <input type="checkbox" class="aml-drop-col" value="${c.name}" checked style="accent-color:#f87171">
  <span>${c.name}</span>
  <span style="margin-left:auto">${c.nunique} unique values</span>
</label>
```

**Frontend — `_applyAutoMLPreprocessing()`:**
```javascript
const dropCols = [...document.querySelectorAll('.aml-drop-col:checked')].map(el => el.value);
const options = {
  drop_columns: dropCols,
  // ... rest of options
};
```

**Backend — `app.py` preprocess function:**
```python
# 0. Drop user-selected high-cardinality / ID columns
drop_cols = [c for c in (options.get("drop_columns") or []) if c in df_feat.columns]
if drop_cols:
    df_feat = df_feat.drop(columns=drop_cols)
```

**Feature selection order — correct (restored):**
1. Missing value imputation
2. Outlier treatment
3. Skewness treatment
4. Categorical encoding (OHE/ordinal/frequency/target) — may expand columns
5. Standardize
6. **Feature selection (top_k)** — trims the fully-encoded feature set

Feature selection code (step 7, after standardize):
```python
fs = options.get("feature_selection", {})
fs_method = (fs.get("method") or "none").lower()
top_k = max(1, int(fs.get("top_k") or 10))
features_before = len(df_feat.columns)

if fs_method != "none":
    try:
        num_X = df_feat.select_dtypes(include="number").fillna(0)
        non_num_cols = df_feat.select_dtypes(exclude="number").columns.tolist()
        k = min(top_k, len(num_X.columns))
        y_fs = target_series.reindex(df_feat.index) if target_series is not None else None

        if fs_method == "variance" and len(num_X.columns) > k:
            keep = num_X.var().nlargest(k).index.tolist()
            df_feat = df_feat[keep + non_num_cols]

        elif fs_method == "correlation" and len(num_X.columns) > 1:
            # drop correlated pairs, then enforce top_k by variance
            ...

        elif fs_method == "rfe" and y_fs is not None and len(num_X.columns) > k:
            rfe = RFE(estimator, n_features_to_select=k)
            ...

        elif fs_method == "kbest" and y_fs is not None and len(num_X.columns) > k:
            sel = SelectKBest(score_fn, k=k)
            ...
    except Exception:
        pass

features_after = len(df_feat.columns)
```

**Commit:** `dd6d1b5` (GitHub) / `8bfb478` (HF)

---

## All Commits This Session

| Hash | Description | Where |
|------|-------------|-------|
| `754904d` | fix(automl): show F1 score as hero metric + animated preprocessing progress bar | GitHub |
| HF `017027f` | fix(automl): F1 as hero metric + animated preprocessing progress bar | HF |
| `dd6d1b5` | fix(automl): high-cardinality column drop UI + correct feature selection order | GitHub |
| HF `8bfb478` | fix(automl): high-cardinality drop UI + correct feature selection order | HF |

---

## Pending / Next Steps

| Item | Status |
|------|--------|
| F1 as hero metric | Done — `754904d` |
| Animated preprocessing progress bar | Done — `754904d` |
| High-cardinality column drop UI | Done — `dd6d1b5` |
| Feature selection correct order (after encoding) | Done — `dd6d1b5` |
| Feature Engineering step (binning, ratio, diff, group agg) | Not started — discussed in Part 69 |
| AutoML Phase 3: Drift detection with data versioning | Not started |
| AutoML Phase 4: RAG-enhanced AI explanation | Not started |
| Model versioning + rollback | Not started |
| Drift alerting (email/Slack) | Not started |
| LLM-assisted feature suggestions | Not started |
| Automated retraining pipeline | Not started |
| Time series forecasting | Not started |
| #21 Batch predictions | Deferred |
| #5 Proxy page | Deferred |
| #22 Dockerize full app | Do last |
| Render deploy | Blocked until July 1, 2026 pipeline reset |

---

## HF Space Notes

- **HF Space URL**: https://huggingface.co/spaces/wram1708/ml-unified
- **HF push workflow**: `rsync -a --exclude='models/*.pkl' ... services/ml-api/ /tmp/hf-space/ && cd /tmp/hf-space && git add -A && git commit && git pull --rebase && git push`
- **HF token**: `<REDACTED_HF_TOKEN>` (Write access)
- **Render reset**: July 1, 2026 — all GitHub commits auto-deploy then
