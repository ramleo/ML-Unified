"""Build the golden documents as real PDFs, at run time.

Two reasons these are generated rather than committed as fixture files.

The first is the cache. `routers/document/_cache.py` keys on the bytes of
the uploaded file, so posting a committed fixture would be served from
cache on every run after the first — the eval would stay green for weeks
while the provider cascade rotted underneath it, which is the exact
failure this whole phase exists to catch. Each build stamps a unique
reference line into the document, so the bytes differ every run and the
cache is never hit. Nothing asserts on that line.

The second is that a PDF built by pymupdf is a digital PDF with a real
text layer, which is the path most users take. The scanned/OCR path needs
a vision model and is deliberately out of scope here.
"""
from __future__ import annotations

import pymupdf

_MARGIN = 56
_LINE = 16


def build_pdf(lines: list[str], run_id: str) -> bytes:
    """One page, one line of text per entry, plus the cache-busting stamp."""
    doc = pymupdf.open()
    page = doc.new_page()
    y = _MARGIN

    for line in lines:
        if not line:
            y += _LINE // 2
            continue
        size = 15 if line.isupper() and len(line) < 40 else 10
        page.insert_text((_MARGIN, y), line, fontsize=size,
                         fontname="hebo" if size == 15 else "helv")
        y += _LINE if size == 15 else _LINE - 4

    # The stamp. Placed at the foot, phrased as an ordinary internal
    # reference so it reads as part of the document rather than as test
    # scaffolding a model might comment on. Never asserted against.
    page.insert_text((_MARGIN, 780), f"Internal file reference: {run_id}",
                     fontsize=7, fontname="helv")

    out = doc.tobytes()
    doc.close()
    return out
