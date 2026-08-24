# Conversation — 2026-06-11 — ML-Unified — Part 58

---

## Session Summary

Visual polish on Clean & Export panel — removed row backgrounds, improved bar spacing. Honest professional assessment of the panel. Explanation of `_scAddDropCol` consistency fix.

---

## Work Done

### Commit `fa3b05f` — Remove row backgrounds + increase bar spacing

**Problem:** Three visual issues preventing "blended" look:
1. Drop-column rows had `background:rgba(248,113,113,0.06);border:1px solid rgba(248,113,113,0.14)` — visible red-tinted boxes
2. Bar row containers had `gap:0.15rem` — too tight, bars formed dense block instead of breathing
3. Dynamically added drop-column rows (via `_scAddDropCol`) used old red-box style, inconsistent with template rows

**Fix:**
- Drop-column rows: removed background/border entirely. Now use same transparent `.shap-feat-name` layout as bar rows (name in red, reason as dim text)
- Bar containers (outlier, imputation, skew): `gap` increased `0.15rem → 0.5rem`
- `_scAddDropCol()`: updated dynamically created rows to match transparent style

---

## Honest Professional Assessment

**What looks good:**
- Typography, font sizes/weights
- Color coding (yellow outliers, red drop cols, purple skew)
- Transparent card blending with ambient background
- `.shap-header` title bar matches Feature Impact style
- Section label hierarchy
- "0 found" badge, checkbox alignment

**What looks unprofessional — identified but NOT yet fixed:**

> **Center-anchored bars for purely positive metrics**

The SHAP Feature Impact bars are center-anchored because SHAP values can be positive OR negative (bar extends right for positive, left for negative). This is semantically correct there.

For **outlier %** (always 0–100%, never negative), center-anchoring wastes the entire left 50% of every bar row as dead space. "calories 18.2%" shows a bar starting at the midpoint going right — 50% of the bar column is empty.

**Correct pattern for purely positive metrics:** left-anchored bar, fills left-to-right proportionally.

- Outlier % → should be left-anchored
- Missing % → should be left-anchored
- Skew → center-anchor IS correct (can be + or −)

**This fix is pending.**

---

## Explanation: `_scAddDropCol()` Consistency

When user clicks "Add" on the dropdown, `_scAddDropCol()` creates a new HTML row dynamically and appends it to `#sc-dropcol-list`. Before the fix, this function used the old style (`background:rgba(248,113,113,0.06);border:...`). After the template rows were already updated to be transparent, manually-added rows still looked visually different. Fix: `_scAddDropCol()` now creates rows with the same transparent grid layout as template rows — `.shap-feat-name` in red, reason as dim text, `padding:0.25rem 0`, no background.

---

## Commit Log (this session)

| Hash | Description |
|------|-------------|
| `fa3b05f` | feat(clean): remove row backgrounds and increase bar spacing for seamless blend |

---

## Pending Items

| # | Item | Notes |
|---|------|-------|
| **FIX** | Left-anchor outlier/missing bars | Center-anchor only correct for skew (bidirectional) |
| #20 | Playwright E2E tests | Not started |
| #22 | Dockerize full app | Not started |
| #21 | Batch predict | Deferred |
| #5  | Proxy page | Deferred |
