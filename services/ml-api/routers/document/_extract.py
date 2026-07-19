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
    if fname.endswith(".docx") or _looks_like_docx(file_bytes):
        return _extract_docx(file_bytes)
    return _extract_image(file_bytes)


def _looks_like_docx(file_bytes: bytes) -> bool:
    if file_bytes[:2] != b"PK":
        return False
    try:
        import zipfile
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            return "word/document.xml" in z.namelist()
    except Exception:
        return False


def _extract_docx(file_bytes: bytes) -> dict[str, Any]:
    """Extract text + tables from a Word document. No page rendering — DOCX has
    no fixed layout, so the preview panel stays empty and bbox search is skipped."""
    try:
        import docx
        d = docx.Document(io.BytesIO(file_bytes))
        parts: list[str] = [p.text for p in d.paragraphs if p.text.strip()]
        for tbl in d.tables:
            lines: list[str] = []
            for i, row in enumerate(tbl.rows):
                cells = [c.text.strip().replace("|", " ") for c in row.cells]
                lines.append("| " + " | ".join(cells) + " |")
                if i == 0:
                    lines.append("|" + "|".join(["---"] * len(cells)) + "|")
            if lines:
                parts.append("\n".join(lines))
        text = "\n\n".join(parts)
        return {"text": text, "page_images": [], "processing_mode": "docx", "pages": 1}
    except Exception as exc:
        logger.error("DOCX extraction failed: %s", exc)
        return {"text": "", "page_images": [], "processing_mode": "error", "pages": 0}


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


def _tier4_keep(s: str) -> bool:
    """Keep a JSON value string as a Tier4 search candidate.
    Only exclude very short plain integers (qty like 2, 10, 100) — they match
    too many places and add no positional value. Everything else is kept:
    formatted amounts ($25.00) anchor the right side of the table, and long
    digit strings (account numbers, IDs) anchor their own location."""
    if len(s) < 3:
        return False
    core = s.lstrip("-$€£¥").replace(",", "").replace(".", "")
    return not (core.isdigit() and len(s) <= 4)


def build_bbox_candidates(value: str) -> tuple[bool, list[str], list[str]]:
    """Split a field value into (is_array, tier4_json_values, scalar_candidates)."""
    import re
    import json as _json

    val = str(value).strip()
    stripped = val
    tier4: list[str] = []
    if stripped[:1] in ("{", "["):
        try:
            parsed = _json.loads(stripped)
            items = parsed if isinstance(parsed, list) else [parsed]
            for item in items:
                if isinstance(item, dict):
                    for v in item.values():
                        s = str(v).strip()
                        if _tier4_keep(s):
                            tier4.append(s)
        except Exception:
            pass

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
    return stripped[:1] == "[", tier4, scalar_candidates


def _norm_box(page, x0, y0, x1, y1) -> list[float]:
    w, h = page.rect.width, page.rect.height
    return [round(x0 / w, 4), round(y0 / h, 4),
            round((x1 - x0) / w, 4), round((y1 - y0) / h, 4)]


def _table_bbox(page) -> list[float] | None:
    """Largest detected table on the page, if it spans ≥ 15% of page width.
    find_tables() works well for bordered PDFs; borderless text-aligned tables
    may return a uselessly narrow bbox — reject those."""
    try:
        tables = list(page.find_tables())
        if tables:
            best = max(tables, key=lambda t: sum(len(r) for r in (t.extract() or [])))
            r = best.bbox
            if page.rect.width > 0 and (r.x1 - r.x0) / page.rect.width >= 0.15:
                return _norm_box(page, r.x0, r.y0, r.x1, r.y1)
    except Exception as exc:
        logger.debug("find_tables failed: %s", exc)
    return None


def search_bbox_in_doc(file_bytes: bytes, value: str,
                       max_pages: int = 5) -> tuple[list[float], int] | None:
    """
    Search for `value` across PDF pages. Returns (normalized bbox, 1-based page
    number), or None.

    Strategy:
    - JSON object/array → the page with the most string-value hits wins; union
      bbox of the hits (arrays additionally prefer that page's detected table)
    - Scalar → tiered candidates (full → chunks → words); each candidate is
      tried across ALL pages before falling to a weaker candidate, so a strong
      match on page 3 beats a single-word match on page 1.
    """
    val = str(value).strip()
    if not val or len(val) < 3:
        return None
    is_array, tier4, scalar_candidates = build_bbox_candidates(val)

    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        try:
            n = min(max_pages, len(doc))

            # JSON values: pick the page where most of the values appear
            if tier4:
                best_idx, best_rects = -1, []
                for pi in range(n):
                    rects = []
                    for t in tier4:
                        rects.extend(doc[pi].search_for(t))
                    if len(rects) > len(best_rects):
                        best_idx, best_rects = pi, rects
                if best_rects:
                    page = doc[best_idx]
                    if is_array:
                        tb = _table_bbox(page)
                        if tb:
                            return tb, best_idx + 1
                    return _norm_box(
                        page,
                        min(r.x0 for r in best_rects), min(r.y0 for r in best_rects),
                        max(r.x1 for r in best_rects), max(r.y1 for r in best_rects),
                    ), best_idx + 1

            # Scalar: strongest candidate across all pages first
            for candidate in scalar_candidates:
                for pi in range(n):
                    rects = doc[pi].search_for(candidate)
                    if rects:
                        r = rects[0]
                        return _norm_box(doc[pi], r.x0, r.y0, r.x1, r.y1), pi + 1
        finally:
            doc.close()
    except Exception as exc:
        logger.debug("bbox search failed for '%s': %s", val[:30], exc)
    return None
