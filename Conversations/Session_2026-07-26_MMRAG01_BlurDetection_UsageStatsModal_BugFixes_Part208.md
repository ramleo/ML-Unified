# Session Part 208 — 2026-07-26

## Context
Continued from Part 207 (MMRAG Feature Backlog created — MMRAG-01 through
MMRAG-21). This session built the first backlog item, then fixed two real
bugs the user caught by actually using the feature.

## 1. MMRAG-01 — Blur/quality detection at upload

Built a NumPy/OpenCV-only sharpness heuristic that runs on every standalone
image upload and every captioned PDF figure page, no model/GPU needed.

- New file: `services/ml-api/routers/rag/blur.py` — `blur_score(png_b64) -> {"score": float, "blurry": bool}`.
- Wired into `mm_image.py` (standalone images) and `mm_pdf.py` (PDF figure
  pages) at caption time.
- Threaded the `blurry` flag through `ingest.py`'s `chunk_meta`,
  `retrieve.py`'s dense/BM25 hit dicts, and `citations.py`'s
  `build_source_doc` — so it shows up both in the ingest-time document
  summary AND in query-time chat citations.
- Frontend: new `blurry` prop on `RagSourceCard.tsx` — gray "Maybe blurry"
  badge with a warning-circle icon, next to the existing "Verify number"
  (red) and "Contains [PII type]" (amber) badges. User guide updated.
- Commits: `ec462ce` (backend), `2843485` (frontend badge).
- Verified live: heavily-blurred synthetic test image → `blurry: true`;
  sharp test image → not flagged. Playwright confirmed the badge renders
  correctly in the real UI with no console errors.

### First calibration attempt — FFT high-frequency-energy ratio
Initial design: fraction of an image's 2D FFT spectral energy sitting
outside a small low-frequency disc. Calibrated against synthetic grids,
UI screenshots, and text renders — looked solid (sharp ~0.6–0.9, blurred
~0.1–0.3), threshold set to 0.35.

## 2. Real bugs caught by the user actually using the feature

**Bug A — blur badge never showed on a real uploaded photo.**
User uploaded a genuinely blurry photo (`abstract-blur.png`) and the
"Maybe blurry" badge never appeared. Investigation (not guesswork — tested
against real photos: `grace_hopper.jpg`, sklearn's `china.jpg`/`flower.jpg`)
revealed the FFT-ratio metric was **non-monotonic**: pushing blur strength
higher on a real photo caused the score to drop correctly at first, then
climb back UP past a certain blur radius — meaning a heavily blurred photo
could score as "sharper" than a mildly blurred one. Root cause: extreme
blur concentrates almost all energy into a couple of near-DC bins while
FFT edge/padding effects reintroduce spurious high-frequency content at
that extreme.

**Fix:** replaced the algorithm with **variance of the Laplacian**
(`cv2.Laplacian(...).var()`, then `log1p` for scale, threshold 4.0) — the
classic, well-established no-reference blur metric. Verified monotonic
across the full blur range on real photos (unblurred through Gaussian
radius 40) with no inversion. Confirmed live against the user's actual
file: `abstract-blur.png` → `score: 1.43, blurry: true` (vs. `6.86` for a
sharp real photo). Commit: `a99271b`.

Also fixed stale tooltip/guide copy that still said "Fourier-based scan"
after the algorithm swap → changed to "edge-detail scan" (commit `e9f165f`,
ml-portfolio).

**Bug B — "Usage stats" destroyed the in-progress session.**
Clicking "Usage stats" navigated to `/tools/rag-analytics`, unmounting the
multimodal-rag page. Clicking Back (even after fixing its destination
from `/#capabilities` to `/tools/multimodal-rag`) still landed on a fresh
page — the uploaded document, chat, and summary panel were all gone,
because that state lived only in local React state with no persistence.

User explicitly rejected the first fix attempt (opening the link in a new
browser tab) — wanted same-tab behavior with the session preserved, not
just avoided. **Real fix:** extracted the analytics dashboard body into a
shared `AnalyticsContent.tsx` component, reused by both the standalone
`/tools/rag-analytics` route (kept for direct links/bookmarks) and a new
`MmRagUsageStatsModal.tsx` opened in-page from the "Usage stats" button —
no navigation at all, so the multimodal-rag page component never unmounts
and the session is never touched. Commit: `d99ddaf` (ml-portfolio).

Verified via Playwright: modal opens with URL staying at
`/tools/multimodal-rag`, closing it (Escape) left the document chip,
summary toggle, and "Maybe blurry" badge all fully intact — zero console
errors throughout.

User guide's "Usage stats" section also updated to describe it as an
in-page panel rather than a link to a separate dashboard page (commit
`1cd7971`, ml-portfolio).

## Commit summary
| Commit | Repo | What |
|---|---|---|
| `ec462ce` | ML-Unified | MMRAG-01 backend: blur.py + wiring through mm_image/mm_pdf/ingest/retrieve/citations |
| `2843485` | ml-portfolio | MMRAG-01 frontend: "Maybe blurry" badge on RagSourceCard + user guide |
| `e68c352` | ml-portfolio | rag-analytics Back button destination fix (superseded by modal fix) |
| `155bf3a` | ml-portfolio | Usage stats → new tab (rejected by user, superseded) |
| `a99271b` | ML-Unified | Blur algorithm fix: FFT ratio → variance-of-Laplacian (non-monotonicity bug) |
| `d99ddaf` | ml-portfolio | Usage stats → in-page modal (AnalyticsContent extraction + MmRagUsageStatsModal) |
| `e9f165f` | ml-portfolio | Stale "Fourier" copy fixed to "edge-detail scan" |
| `1cd7971` | ml-portfolio | User guide: usage stats section updated for modal behavior |

## Pending
- MMRAG-01 is fully done, deployed, and verified.
- Next backlog items (unstarted): MMRAG-02 (cross-document contradiction
  detector) or MMRAG-04 (answer groundedness scoring) — both Tier 1.
- Full backlog reference: `project_mmrag_feature_backlog.md` memory file /
  `Conversations/..._Part207.md`.
