# Conversation — 2026-06-11 — ML-Unified — Clean & Export UI Fixes — Part 63

---

## Session Summary

Two UI fixes to the Clean & Export panel header. Commits `8c2b116`.

---

## Fix 1 — Filename Not Visible in Clean & Export Header

**Symptom:** The dataset filename (e.g. "Titanic-Dataset.csv") was rendered as faint small text (`0.7rem`, `color: var(--text3)`) pushed to the far right of the header — barely visible against the dark background.

**Fix (`services/ml-api/frontend/index.html` — `_buildCleanOptions`):**

- Moved filename below the panel title (stacked layout instead of inline)
- Styled as `0.75rem`, `font-weight: 600`, `color: #22d3ee` (cyan), with `opacity: 0.9`
- Long filenames truncate with ellipsis; full name shown on hover via `title` attribute
- Max width `340px` to prevent overflow

---

## Fix 2 — Replace Emoji with SVGs in Header

**Symptom:** Panel title used 🧹 emoji and filename used 📄 emoji. User requested SVG icons instead for consistency with the rest of the UI (all icons in the project use stroke-based SVGs).

**Fix:**

- **🧹 → broom SVG**: A clean stroke path forming a broom shape, `16×16`, `stroke-width: 1.8`, inline with the "Clean & Export" title text
- **📄 → file SVG**: A document/file icon with folded corner, `11×11`, `stroke-width: 2`, inline with the filename. `flex-shrink: 0` prevents the icon from being squished when the filename is long

Both SVGs use `stroke="currentColor"` so they inherit the parent text colour automatically.

---

## Commit Log

| Hash | Description | Pushed |
|------|-------------|--------|
| `8c2b116` | fix(clean): replace emoji with SVGs in Clean & Export header, show filename prominently | Yes |
| `0bf7a89` | fix(clean): split imputation by type, progress bar on submit, add ml-eda to CI | Yes |
| `429544b` | test(e2e): add Playwright E2E suite — 13 tests across inference, drift, home, clean | Yes |
| `437a12f` | fix(clean): left-anchor outlier/missing bars with normalization | Yes |

---

## Pending

| # | Item | Status |
|---|------|--------|
| **Action** | Add `RENDER_EDA_DEPLOY_HOOK_URL` to GitHub Secrets | Still needed — prevents future manual redeploys of ml-eda |
| **#22** | Dockerize full app | Not started |
| **#21** | Batch predict | Deferred |
| **#5** | Proxy page | Deferred |
