# Conversation — 2026-06-04 | ML Unified Render Deploy Verification & DBSCAN Fix (Part 14)

**Project:** ML-Unified  
**Date:** 2026-06-04  
**Branch:** main  
**Commits this session:** `66bef20`

---

## Summary

This session verified the live Render deployment at https://ml-unified.onrender.com and diagnosed + fixed a persistent DBSCAN 0-cluster bug that survived the previous session's StandardScaler fix.

---

## Session Flow

### 1. Initial Verification

User asked to confirm the Render deployment was live and showing the `cf1e001` fixes (DBSCAN StandardScaler + PCA n_components label).

Used Playwright to:
- Navigate to https://ml-unified.onrender.com — app loaded correctly
- Screenshot home page (Diabetes Risk Predictor panel)
- Screenshot DBSCAN panel — controls present (EPS, MIN_SAMPLES, 2D/3D, Run DBSCAN)
- Screenshot PCA panel — showed **DIMENSIONS** label (n_components fix confirmed)

### 2. User Reports Commit Wasn't Deployed

User noted the previous deployment hadn't picked up commit `cf1e001` and manually triggered a re-deploy on Render.

Re-screenshotted both panels after re-deploy — visually identical (label fix visible), but the StandardScaler fix is backend-only and not visually verifiable without running DBSCAN on actual data.

### 3. User Shows 0-Cluster Result (Screenshot)

User shared a screenshot showing DBSCAN returning:
> "0 clusters found — try increasing eps or decreasing min_samples"

...despite the scatter plot displaying a 3D PCA visualization with data points spread across Component 1/2/3 axes.

### 4. Root Cause Diagnosis

Inspected `app.py`. Found the real bug:

**The StandardScaler was correctly applied** (line 240, inside a `ColumnTransformer` pipeline on `X_prep`). However, DBSCAN was being run on `X_prep` — the full high-dimensional scaled feature matrix.

**Root cause: curse of dimensionality.**  
When a dataset has many columns (e.g. 8+ numeric features), pairwise Euclidean distances in that space are uniformly large. The default `eps=0.5` finds no neighbours, producing 0 clusters regardless of scaling.

The PCA visualization at the bottom of the route was computed *after* clustering — so the scatter plot showed nicely spread PCA components, but DBSCAN never saw that compact space.

Also found a second stale DBSCAN at line 422 (in the `/train` route) with hardcoded `eps=0.5, min_samples=5` ignoring user params — separate issue, not the active bug.

### 5. Fix Applied

**File:** `app.py`, `/unsupervised` endpoint, DBSCAN branch (lines 265–272 → expanded)

**Change:** Compute PCA reduction *before* running DBSCAN, then run DBSCAN on `coords_db` (the same 2D/3D space used for visualization). Return early like t-SNE/PCA to skip the redundant second PCA pass at the bottom of the route.

```python
elif algorithm == "DBSCAN":
    # Run on PCA-reduced space — full high-dimensional distances make eps=0.5 useless
    n_comp_db = min(max(2, n_dims), X_prep.shape[1])
    pca_db    = PCA(n_components=n_comp_db)
    coords_db = pca_db.fit_transform(X_prep)
    eps_val   = max(0.01, eps)
    db        = DBSCAN(eps=eps_val, min_samples=min_samples)
    cluster_ids = db.fit_predict(coords_db).tolist()
    n_found  = len(set(c for c in cluster_ids if c >= 0))
    n_noise  = cluster_ids.count(-1)
    sil = silhouette_score(coords_db, cluster_ids) if n_found > 1 and len(set(cluster_ids)) > 1 else 0.0
    stats.update({"n_clusters": n_found, "n_noise": n_noise, "silhouette": round(sil, 3)})
    # ... build plot_data from coords_db and return early
```

**Commit:** `66bef20` — *Fix DBSCAN 0-cluster bug: run on PCA-reduced space, not full feature space*  
**Pushed to:** `origin/main` → triggers Render auto-deploy

### 6. Live Test Attempt

After push, used Playwright to:
- Navigate to the live site
- Click DBSCAN panel
- Inject `test_clusters.csv` (24 rows, 3 numeric columns with 3 obvious clusters centred at ~(1,1,1), ~(5,5,5), ~(9,1,9)) via JavaScript `DataTransfer` + `dispatchEvent('change')`
- File loaded: `test_clusters.csv (0.3 KB)` confirmed in UI
- "Run DBSCAN" button became active

Session ended before clicking Run DBSCAN — result not yet confirmed.

---

## Files Changed

| File | Change |
|------|--------|
| `app.py` | DBSCAN branch in `/unsupervised`: run on PCA-reduced coords instead of full X_prep; return early with plot_data |

## Test CSV Created

`/Users/wrks/Downloads/Claude-documentation/Projects/ML-Unified/test_clusters.csv`  
24 rows × 3 numeric columns, 3 tight clusters at (1,1,1), (5,5,5), (9,1,9).

---

## Key Technical Notes

- **eps=0.5 in PCA space is sensible** — after StandardScaler + PCA, component values are roughly in [-3, 3], so 0.5 is ~1/6 of the range. Reasonable default.
- **eps=0.5 in full feature space is not** — with 8 features each scaled to std=1, expected nearest-neighbour distance grows as √n_features ≈ 2.8 for 8 features. All points appear far apart.
- The visualization and clustering now use the **same space**, so what the user sees in the scatter plot matches what DBSCAN actually computed.

---

## Next Steps

- Confirm "Run DBSCAN" returns 3 clusters on `test_clusters.csv` on the live deploy
- Optionally: surface an "estimated eps" hint in the UI based on k-NN distances