"""Standalone image ingestion for multimodal RAG — one thorough caption +
OCR pass per upload, same 'image' chunk_type/retrieval path a PDF's
figures use. Split out of mm_ingest.py to stay under the project's
file-length limit.
"""
from __future__ import annotations

from routers.document._vision import _vision_cascade_raw, mistral_ocr_pages
from routers.rag.mm_caption import clean_ocr_text, extract_caption

_OCR_TEXT_CAP = 2000


def _image_prompt(terse: bool = False) -> str:
    if terse:
        # Fallback for reasoning models that exhaust their token budget
        # thinking before answering a more demanding ask — short and direct
        # leaves it little room to ramble before the JSON is due.
        return (
            "In 2-3 short sentences, describe this image and transcribe any "
            'visible text or numbers exactly. Return JSON only: {"caption": "..."}.'
        )
    return (
        "Describe this image for someone who cannot see it: main subject, "
        "setting, colors, and any visible text/numbers (transcribe exactly). "
        "Be factual, 3-4 sentences. "
        'Return JSON only: {"caption": "<your description>"}.'
    )


def looks_like_image(file_bytes: bytes, content_type: str = "") -> bool:
    if content_type.startswith("image/"):
        return True
    sigs = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF",  # PNG, JPEG, GIF, WEBP(RIFF)
            b"BM", b"II*\x00", b"MM\x00*")                    # BMP, TIFF (little/big-endian)
    if any(file_bytes.startswith(s) for s in sigs):
        return True
    # Last resort: let PIL make the call — covers real image files whose exact
    # header a fixed signature list doesn't anticipate (e.g. unusual PNG/TIFF
    # variants exported by some invoice/office tools).
    try:
        from PIL import Image
        import io
        Image.open(io.BytesIO(file_bytes)).verify()
        return True
    except Exception:
        return False


def build_image_chunk(file_bytes: bytes, source: str) -> tuple[list[dict], list[str], dict]:
    """A standalone image upload — one 'image' chunk_type, described thoroughly
    (not the terser 'figure on a document page' framing used for PDF pages)."""
    from PIL import Image
    import io, base64

    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()

    caption = extract_caption(_vision_cascade_raw(b64, _image_prompt()), 800)
    if not caption:
        # First attempt likely got cut off mid-reasoning before reaching the
        # JSON — one bounded retry with a terser ask that leaves less room
        # for a reasoning model to exhaust its token budget before answering.
        caption = extract_caption(_vision_cascade_raw(b64, _image_prompt(terse=True)), 400)

    ocr_md, _ = mistral_ocr_pages([b64])
    ocr_text = clean_ocr_text(ocr_md)[:_OCR_TEXT_CAP]
    if ocr_text:
        caption = f"{caption}\n\nExact text from image (OCR):\n{ocr_text}" if caption else ocr_text

    summary = {"text": 0, "table": 0, "figure": 0, "image": 1 if caption else 0}
    if not caption:
        return [], [b64], summary

    # No embedded "[Image: source]" prefix — citations.py's build_system_prompt
    # already labels this chunk with source/page/type when building the LLM's
    # context, so baking it into the stored text would only be redundant
    # noise in the citation UI's raw-text preview.
    chunk = {"text": caption, "source": source, "chunk_index": 0,
             "chunk_type": "image", "page": 1}
    return [chunk], [b64], summary
