"""Document extraction — digital PDF via PyMuPDF4LLM, images via Pillow."""
from __future__ import annotations

import base64
import io
import logging
from typing import Any

logger = logging.getLogger(__name__)

_TEXT_THRESHOLD = 50  # min chars to count as "has text layer"


def extract_document(file_bytes: bytes, filename: str) -> dict[str, Any]:
    """
    Returns:
        text           — extracted text (markdown for digital PDFs, raw for fallback)
        page_images    — list of base64-encoded PNG strings (first 2 pages)
        processing_mode — "digital" | "scanned" | "image" | "error"
        pages          — page count
    """
    fname = (filename or "").lower()
    if fname.endswith(".pdf") or file_bytes[:4] == b"%PDF":
        return _extract_pdf(file_bytes)
    return _extract_image(file_bytes)


def _extract_pdf(file_bytes: bytes) -> dict[str, Any]:
    try:
        import fitz  # pymupdf
    except ImportError:
        logger.error("pymupdf not installed — cannot extract PDF")
        return {"text": "", "page_images": [], "processing_mode": "error", "pages": 0}

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = len(doc)
    page_images = _render_pages(doc)

    # 1. Try pymupdf4llm for high-quality markdown
    try:
        import pymupdf4llm
        doc2 = fitz.open(stream=file_bytes, filetype="pdf")
        md = pymupdf4llm.to_markdown(doc2)
        doc2.close()
        if len(md.strip()) > _TEXT_THRESHOLD:
            doc.close()
            return {"text": md, "page_images": page_images, "processing_mode": "digital", "pages": pages}
    except Exception as exc:
        logger.warning("pymupdf4llm failed, falling back to plain text: %s", exc)

    # 2. Fallback: plain text extraction
    text_parts = [page.get_text() for page in doc]
    doc.close()
    text = "\n".join(text_parts)

    if len(text.strip()) > _TEXT_THRESHOLD:
        return {"text": text, "page_images": page_images, "processing_mode": "digital", "pages": pages}

    # 3. No text found — mark as scanned (Gemini Vision will handle it)
    return {"text": "", "page_images": page_images, "processing_mode": "scanned", "pages": pages}


def _extract_image(file_bytes: bytes) -> dict[str, Any]:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(file_bytes))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return {"text": "", "page_images": [b64], "processing_mode": "image", "pages": 1}
    except Exception as exc:
        logger.error("Image extraction failed: %s", exc)
        return {"text": "", "page_images": [], "processing_mode": "error", "pages": 0}


def _render_pages(doc, max_pages: int = 5) -> list[str]:
    """Render first N pages of an open fitz.Document to base64 PNG strings."""
    images: list[str] = []
    try:
        import fitz
        mat = fitz.Matrix(1.2, 1.2)
        for i in range(min(max_pages, len(doc))):
            try:
                pix = doc[i].get_pixmap(matrix=mat)
                b64 = base64.b64encode(pix.tobytes("png")).decode()
                images.append(b64)
            except Exception:
                pass
    except Exception as exc:
        logger.warning("Page render failed: %s", exc)
    return images


def extract_tables_markdown(file_bytes: bytes, max_pages: int = 5) -> str:
    """Extract tables from a PDF as markdown using pymupdf find_tables().
    Returns empty string if no tables found or extraction fails."""
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        parts: list[str] = []
        for page_num in range(min(max_pages, len(doc))):
            page = doc[page_num]
            tabs = page.find_tables()
            for tab in tabs:
                rows = tab.extract()
                if not rows:
                    continue
                lines: list[str] = []
                for j, row in enumerate(rows):
                    cells = [str(c or "").strip().replace("|", " ") for c in row]
                    lines.append("| " + " | ".join(cells) + " |")
                    if j == 0:
                        lines.append("|" + "|".join(["---"] * len(row)) + "|")
                parts.append(f"\n### Table (Page {page_num + 1})\n" + "\n".join(lines))
        doc.close()
        return "\n".join(parts)
    except Exception as exc:
        logger.warning("Table extraction failed: %s", exc)
        return ""


def search_bbox_in_doc(file_bytes: bytes, value: str, page_idx: int = 0) -> list[float] | None:
    """
    Search for `value` text in a PDF page and return normalized
    [left, top, width, height] in [0, 1] range, or None if not found.

    Strategy:
    - JSON array (line items)  → layout-aware table detection via find_tables()
    - JSON object              → union bbox of all string values extracted from JSON
    - Scalar                   → tiered substring search (full → chunks → words)
    """
    import re
    import json as _json

    val = str(value).strip()
    if not val or len(val) < 3:
        return None

    stripped = val.strip()

    def _is_numeric_noise(s: str) -> bool:
        """True for formatted amounts/prices and very short digit strings.
        Pure long-digit strings (account numbers, IDs) return False so they ARE searched."""
        core = s.lstrip("-$€£¥").replace(",", "")
        if not core.replace(".", "").isdigit():
            return False  # non-numeric chars present → not a number
        # Formatted number (has decimal or comma) or too short to be unique → noise
        return "." in core or "," in s or len(s) <= 4

    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        if page_idx >= len(doc):
            doc.close()
            return None
        page = doc[page_idx]
        rect_w, rect_h = page.rect.width, page.rect.height

        def _norm(r: object) -> list[float]:
            return [round(r.x0 / rect_w, 4), round(r.y0 / rect_h, 4),  # type: ignore[attr-defined]
                    round((r.x1 - r.x0) / rect_w, 4), round((r.y1 - r.y0) / rect_h, 4)]  # type: ignore[attr-defined]

        # ── JSON array → layout-aware table detection ─────────────────────────
        # Line-item arrays map to a table in the PDF; find_tables() returns the
        # full row+column region including headers, which value-search cannot.
        if stripped[0] == "[":
            try:
                tables = list(page.find_tables())
                if tables:
                    best = max(tables, key=lambda t: sum(len(r) for r in (t.extract() or [])))
                    r = best.bbox
                    doc.close()
                    return [round(r.x0 / rect_w, 4), round(r.y0 / rect_h, 4),
                            round((r.x1 - r.x0) / rect_w, 4), round((r.y1 - r.y0) / rect_h, 4)]
            except Exception as exc:
                logger.debug("find_tables for array field failed: %s", exc)
            # Fall through to Tier 4 value-search if table detection fails

        # ── Tier 4: JSON object/array → union bbox of all string values ───────
        tier4: list[str] = []
        if stripped[0] in ("{", "["):
            try:
                parsed = _json.loads(stripped)
                items = parsed if isinstance(parsed, list) else [parsed]
                for item in items:
                    if isinstance(item, dict):
                        for v in item.values():
                            s = str(v).strip()
                            if len(s) >= 3 and not _is_numeric_noise(s):
                                tier4.append(s)
            except Exception:
                pass

        # ── Scalar candidate tiers ─────────────────────────────────────────────
        chunks = re.split(r"[,|;\n]+", val)
        tier2 = sorted((c.strip() for c in chunks if len(c.strip()) >= 3), key=len, reverse=True)
        tier3: list[str] = []
        tier5: list[str] = []
        for chunk in chunks:
            words = re.split(r"\s+", re.sub(r"[^\w\s$]", " ", chunk.strip()))
            words = [w for w in words if w]
            if len(words) >= 2:
                tier3.append(" ".join(words[:2]))
            if len(words) >= 3:
                tier3.append(" ".join(words[:3]))
            for w in words:
                if len(w) >= 4:
                    tier5.append(w)
        scalar_candidates = [val[:80]] + tier2 + tier3 + tier5
        seen: set[str] = set()
        scalar_candidates = [c for c in scalar_candidates if not (c in seen or seen.add(c))]  # type: ignore[func-returns-value]

        # Union bbox of all Tier 4 matches
        if tier4:
            all_rects = []
            for t in tier4:
                all_rects.extend(page.search_for(t))
            if all_rects:
                x0 = min(r.x0 for r in all_rects)
                y0 = min(r.y0 for r in all_rects)
                x1 = max(r.x1 for r in all_rects)
                y1 = max(r.y1 for r in all_rects)
                doc.close()
                return [round(x0 / rect_w, 4), round(y0 / rect_h, 4),
                        round((x1 - x0) / rect_w, 4), round((y1 - y0) / rect_h, 4)]

        # Scalar: first match wins
        for candidate in scalar_candidates:
            rects = page.search_for(candidate)
            if rects and rect_w > 0 and rect_h > 0:
                doc.close()
                return _norm(rects[0])
        doc.close()
    except Exception as exc:
        logger.debug("bbox search failed for '%s': %s", val[:30], exc)
    return None
