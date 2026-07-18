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

    Falls back to substring search when the LLM reformatted/combined values:
    splits on common delimiters and tries each chunk longest-first.
    """
    import re
    val = str(value).strip()
    if not val or len(val) < 3:
        return None

    # Build candidate strings: full value first, then split by common delimiters
    chunks = re.split(r"[,|;\n]+", val)
    candidates = [val[:80]] + sorted(
        (c.strip() for c in chunks if len(c.strip()) >= 3),
        key=len, reverse=True,
    )
    # Deduplicate while preserving order
    seen: set[str] = set()
    candidates = [c for c in candidates if not (c in seen or seen.add(c))]  # type: ignore[func-returns-value]

    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        if page_idx >= len(doc):
            doc.close()
            return None
        page = doc[page_idx]
        rect_w, rect_h = page.rect.width, page.rect.height
        for candidate in candidates:
            rects = page.search_for(candidate)
            if rects and rect_w > 0 and rect_h > 0:
                r = rects[0]
                doc.close()
                return [
                    round(r.x0 / rect_w, 4),
                    round(r.y0 / rect_h, 4),
                    round((r.x1 - r.x0) / rect_w, 4),
                    round((r.y1 - r.y0) / rect_h, 4),
                ]
        doc.close()
    except Exception as exc:
        logger.debug("bbox search failed for '%s': %s", val[:30], exc)
    return None
