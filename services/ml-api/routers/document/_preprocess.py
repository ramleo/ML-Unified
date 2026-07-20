"""Pre-processing helpers for Document Intelligence:
- complexity_tier: route simple docs to a fast/cheap model, complex to the cascade
- multicolumn_pdf_text: column-aware reading order for multi-column PDFs
- correct_image_orientation: EXIF auto-rotate + small-angle deskew for images
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# ── Complexity routing ────────────────────────────────────────────────────────

_SIMPLE_MAX_CHARS = 3500


def complexity_tier(text: str, pages: int, processing_mode: str) -> str:
    """"simple" → short single-page digital doc a small fast model handles well.
    "complex" → multi-page, long, scanned/image, or table-heavy documents."""
    if processing_mode not in ("digital", "docx"):
        return "complex"
    if pages > 1 or len(text) > _SIMPLE_MAX_CHARS:
        return "complex"
    if "## DOCUMENT TABLES" in text or text.count("|") > 20:
        return "complex"
    return "simple"


# ── Multi-column reading order ────────────────────────────────────────────────

def _page_column_text(page) -> tuple[str, bool]:
    """Text for one page in reading order. Returns (text, was_multicolumn).

    Blocks whose right edge stays in the left 55% of the page form the left
    column; blocks starting past 45% form the right column; the rest span the
    full width. A page is multi-column when both columns have ≥3 blocks that
    overlap vertically ≥25% of the page height.
    """
    blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
    if len(blocks) < 6:
        return "\n".join(b[4].strip() for b in sorted(blocks, key=lambda b: (b[1], b[0]))), False

    W, H = page.rect.width, page.rect.height
    left = [b for b in blocks if b[2] <= W * 0.55]
    right = [b for b in blocks if b[0] >= W * 0.45 and b[2] > W * 0.55]
    span = [b for b in blocks if b not in left and b not in right]

    if len(left) >= 3 and len(right) >= 3:
        overlap = (min(max(b[3] for b in left), max(b[3] for b in right))
                   - max(min(b[1] for b in left), min(b[1] for b in right)))
        if overlap >= 0.25 * H:
            col_top = min(min(b[1] for b in left), min(b[1] for b in right))
            col_bot = max(max(b[3] for b in left), max(b[3] for b in right))
            top = [b for b in span if b[3] <= col_top + 5]
            bottom = [b for b in span if b[1] >= col_bot - 5]
            mid = [b for b in span if b not in top and b not in bottom]
            ordered = (sorted(top, key=lambda b: b[1])
                       + sorted(left + mid, key=lambda b: b[1])
                       + sorted(right, key=lambda b: b[1])
                       + sorted(bottom, key=lambda b: b[1]))
            return "\n".join(b[4].strip() for b in ordered), True

    return "\n".join(b[4].strip() for b in sorted(blocks, key=lambda b: (b[1], b[0]))), False


def multicolumn_pdf_text(doc) -> str:
    """Column-aware plain text for a PDF, or "" when no page is multi-column
    (caller then keeps the default pymupdf4llm markdown path, which is better
    for everything except interleaved multi-column layouts)."""
    try:
        pages_text: list[str] = []
        any_multi = False
        for page in doc:
            txt, multi = _page_column_text(page)
            pages_text.append(txt)
            any_multi = any_multi or multi
        return "\n\n".join(pages_text) if any_multi else ""
    except Exception as exc:
        logger.warning("multicolumn text failed: %s", exc)
        return ""


# ── Image orientation / skew ──────────────────────────────────────────────────

def _detect_skew(img) -> float:
    """Skew angle in degrees via projection profile: the rotation that makes
    horizontal ink-density rows sharpest is the correction angle."""
    import numpy as np
    from PIL import Image

    g = img.convert("L")
    g.thumbnail((800, 800))
    a = np.asarray(g, dtype=np.float32)
    binary = ((a < a.mean() * 0.85) * 255).astype("uint8")
    bimg = Image.fromarray(binary)
    best_angle, best_score = 0.0, -1.0
    for half_deg in range(-10, 11):  # −5° … +5° in 0.5° steps
        angle = half_deg / 2
        rows = np.asarray(bimg.rotate(angle, fillcolor=0), dtype=np.float32).sum(axis=1)
        score = float(((rows[1:] - rows[:-1]) ** 2).sum())
        if score > best_score:
            best_score, best_angle = score, angle
    return best_angle


def correct_image_orientation(img):
    """EXIF auto-rotate (phone photos) then deskew if tilt ≥ 0.75°."""
    from PIL import ImageOps

    try:
        img = ImageOps.exif_transpose(img) or img
    except Exception as exc:
        logger.warning("EXIF transpose failed: %s", exc)
    try:
        angle = _detect_skew(img)
        if 0.75 <= abs(angle) <= 5:
            img = img.rotate(angle, expand=True, fillcolor="white")
            logger.info("Deskewed image by %.1f°", angle)
    except Exception as exc:
        logger.warning("Deskew failed: %s", exc)
    return img
