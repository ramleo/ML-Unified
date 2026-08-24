# Conversation – 2026-06-02 00:55 (Part 7): Screenshot Comparison + Pending Fixes

---

## What Happened This Session

The user shared two screenshots for comparison and identified 4 issues to fix. Session ended with a break — fixes are **pending**.

---

## Screenshot Comparison

**Screenshot 1 — Current live site (Temp-Insurance):**
- Title: "Temp Insurance" (raw filename)
- Algorithm: XGBoost, MAE ±691, Est. Error ±912
- Form empty — no prediction yet
- Field order: Age → Annual Income → Number of Dependents → Health Score → Previous Claims → Vehicle Age → Credit Score → Insurance Duration
- No tooltip visible (CI section hidden since no prediction)
- Form cards in light theme but page background still dark

**Screenshot 2 — Reference/target design:**
- Title: "Insurance Premium Predictor"
- Algorithm: Gradient Boosting, MAE ±668, Est. Error ±875
- Form filled, prediction 1703.85 showing
- "ESTIMATED PREMIUM" badge + "LIKELY PREMIUM RANGE (?)" CI bar
- Field order: Annual Income → Previous Claims → Credit Score → Insurance Duration → Health Score → Age → Number of Dependents → Vehicle Age

---

## Pending Fixes (4 tasks, ~20 min total)

| # | Fix | Est. Time |
|---|---|---|
| 1 | Update project title to "Insurance Premium Predictor" | ~2 min |
| 2 | Add missing tooltip to CI section | ~3 min |
| 3 | Fix dark hero/background in light theme — form is light but outer background still dark | ~5 min |
| 4 | Fix "Feature Inputs" / "Prediction Result" header text — still white/hard to see in light mode | ~5 min |

**All changes must go into:**
- `Temp-Insurance/index.html`
- `ML-Pipeline-Auto/auto_pipeline.py` template
- `ML-Pipeline-Auto/bootstrap.py` (re-embed after every auto_pipeline.py change)
- Push both repos to GitHub after committing

---

## Status

User took a break. Resume from the 4 pending fixes above when back.
