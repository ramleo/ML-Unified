"""FastAPI router for Document Intelligence — POST /document/analyze, GET /document/types."""
from __future__ import annotations

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator

_executor = ThreadPoolExecutor(max_workers=2)

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ._schema import DOC_TYPES
from ._extract import extract_document, search_bbox_in_doc, extract_tables_markdown
from . import _cache
from . import _llm as _llm_state
from ._llm import classify_document, extract_fields_from_text
from ._vision import (extract_fields_from_image, extract_visual_sections,
                      locate_fields_from_ocr, mistral_ocr_pages)
from ._validate import validate_and_correct

router = APIRouter(prefix="/document", tags=["document"])
logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _stream(file_bytes: bytes, filename: str, doc_type_hint: str,
                  provider: str = "auto", custom_fields: str = "") -> AsyncGenerator[str, None]:
    known_types = list(DOC_TYPES.keys())

    # ── Cache: same file + settings analyzed before → replay instantly ────────
    cache_key = _cache.make_key(file_bytes, doc_type_hint, provider + "|" + custom_fields)
    cached = _cache.get(cache_key)
    if cached:
        done_evt = cached["done"]
        for step in ("extract", "classify", "analyze", "validate"):
            evt: dict = {"step": step, "status": "done"}
            if step == "classify":
                evt.update({"doc_type": done_evt["doc_type"],
                            "doc_type_label": done_evt["doc_type_label"],
                            "classification_confidence": done_evt["classification_confidence"]})
            if step == "analyze":
                evt["provider"] = f'{cached["provider"]} (cached)' if cached["provider"] else ""
            yield _sse(evt)
        for field in cached["fields"]:
            yield _sse({"field": field})
            await asyncio.sleep(0.03)
        cached_provider = f'{cached["provider"]} (cached)' if cached["provider"] else ""
        yield _sse({**done_evt, "provider": cached_provider, "cached": True})
        return

    # ── Step 1: Extract ───────────────────────────────────────────────────────
    yield _sse({"step": "extract", "label": "Extracting content", "status": "running"})
    await asyncio.sleep(0)

    extracted = extract_document(file_bytes, filename)
    text = extracted["text"]
    page_images = extracted["page_images"]
    processing_mode = extracted["processing_mode"]
    pages = extracted["pages"]

    # Append structured table markdown so LLM sees clean table data for
    # invoices, bank statements, purchase orders, etc.
    if processing_mode == "digital" and file_bytes[:4] == b"%PDF":
        table_md = extract_tables_markdown(file_bytes)
        if table_md:
            text = text + "\n\n## DOCUMENT TABLES\n" + table_md

    if processing_mode == "error":
        yield _sse({"error": "Failed to process file. Ensure it is a valid PDF, PNG, or JPG."})
        return

    # OCR-first for scanned/image docs: convert pages to markdown so classify
    # and extraction use the same high-quality text path as digital PDFs.
    # ocr_meta keeps per-block pixel bboxes for field location later.
    ocr_meta: list[dict] = []
    if not text.strip() and page_images:
        loop = asyncio.get_event_loop()
        ocr_md, ocr_meta = await loop.run_in_executor(
            _executor, lambda: mistral_ocr_pages(page_images)
        )
        if ocr_md.strip():
            text = ocr_md

    yield _sse({"step": "extract", "status": "done"})

    # ── Step 2: Classify ──────────────────────────────────────────────────────
    yield _sse({"step": "classify", "label": "Identifying document type", "status": "running"})
    await asyncio.sleep(0)

    if doc_type_hint and doc_type_hint != "auto" and doc_type_hint in DOC_TYPES:
        doc_type, class_confidence = doc_type_hint, 1.0
    elif text.strip():
        try:
            doc_type, class_confidence = classify_document(
                text[:600], known_types,
                {k: v["description"] for k, v in DOC_TYPES.items()},
            )
        except Exception as exc:
            logger.error("Classification failed: %s", exc)
            doc_type, class_confidence = "invoice", 0.5
    else:
        # Scanned / image with no text — default; user can override via sidebar
        doc_type, class_confidence = "invoice", 0.4

    yield _sse({
        "step": "classify", "status": "done",
        "doc_type": doc_type,
        "doc_type_label": DOC_TYPES[doc_type]["label"],
        "classification_confidence": round(class_confidence, 3),
    })

    # ── Step 3: Analyze ───────────────────────────────────────────────────────
    yield _sse({"step": "analyze", "label": "Extracting fields with AI", "status": "running"})
    await asyncio.sleep(0)

    schema_fields = list(DOC_TYPES[doc_type]["fields"])
    # User-requested extra fields: "GST Number, HSN Code" → schema entries
    for cf in custom_fields.split(","):
        cf = cf.strip()
        if cf:
            name = "".join(c if c.isalnum() else "_" for c in cf.lower()).strip("_")
            if name and name not in {f["name"] for f in schema_fields}:
                schema_fields.append({"name": name, "label": cf, "field_type": "text"})
    fields: list[dict] = []
    served_by = ""

    try:
        loop = asyncio.get_event_loop()
        if text.strip():
            fields = await loop.run_in_executor(
                _executor, lambda: extract_fields_from_text(text, doc_type, schema_fields, provider)
            )
            # Capture attribution for the MAIN extraction now — the visual
            # sections pass and validation below also run the cascades and
            # would overwrite last_provider.
            if fields:
                served_by = _llm_state.last_provider
            if page_images:
                schema_names = {f["name"] for f in schema_fields}
                found_names = {f["name"] for f in fields if f.get("value")}
                missing_names = schema_names - found_names
                yield _sse({"step": "analyze", "label": "Analyzing visual content", "status": "running"})
                visual_fields = await loop.run_in_executor(
                    _executor,
                    lambda: extract_visual_sections(page_images, found_names, missing_names),
                )
                existing_all = {f["name"] for f in fields}
                for vf in visual_fields:
                    if vf["name"] not in existing_all:
                        fields.append(vf)
                    else:
                        for f in fields:
                            if f["name"] == vf["name"] and not f.get("value"):
                                f.update(vf)
        elif page_images:
            fields = await loop.run_in_executor(
                _executor,
                lambda: extract_fields_from_image(page_images[0], doc_type, schema_fields),
            )
            if fields:
                served_by = _llm_state.last_provider
    except Exception as exc:
        logger.error("Field extraction failed: %s", exc)

    # Text path (incl. OCR-first) produced nothing → one-shot vision fallback
    if not fields and page_images:
        try:
            fields = await loop.run_in_executor(
                _executor,
                lambda: extract_fields_from_image(page_images[0], doc_type, schema_fields),
            )
            if fields:
                served_by = _llm_state.last_provider
        except Exception as exc:
            logger.error("Vision fallback failed: %s", exc)

    yield _sse({"step": "analyze", "status": "done", "provider": served_by})

    if not fields:
        yield _sse({"warning": "No fields extracted — AI providers may be temporarily unavailable. Please try again in a few minutes."})

    # ── Step 4: Self-correction loop ──────────────────────────────────────────
    yield _sse({"step": "validate", "label": "Checking field consistency", "status": "running"})
    await asyncio.sleep(0)

    try:
        fields = await loop.run_in_executor(
            _executor, lambda: validate_and_correct(fields, doc_type)
        )
    except Exception as exc:
        logger.error("Validation pass failed: %s", exc)

    # ── Step 4b: bbox lookup for digital PDFs ────────────────────────────────
    yield _sse({"step": "validate", "label": "Locating fields in document", "status": "running"})
    await asyncio.sleep(0)

    is_pdf = file_bytes[:4] == b"%PDF"
    if processing_mode == "digital" and is_pdf:
        for field in fields:
            if field.get("value") and field.get("bbox") is None:
                found = search_bbox_in_doc(file_bytes, field["value"])
                if found:
                    field["bbox"], field["page"] = found
    elif ocr_meta:
        locate_fields_from_ocr(fields, ocr_meta)

    yield _sse({"step": "validate", "status": "done"})

    # ── Stream fields one-by-one ──────────────────────────────────────────────
    for field in fields:
        yield _sse({"field": field})
        await asyncio.sleep(0.07)  # stagger for frontend animation

    # ── Done ──────────────────────────────────────────────────────────────────
    done_evt = {
        "done": True,
        "doc_type": doc_type,
        "doc_type_label": DOC_TYPES[doc_type]["label"],
        "processing_mode": processing_mode,
        "pages": pages,
        "page_images": page_images,
        "field_count": len(fields),
        "classification_confidence": round(class_confidence, 3),
        "provider": served_by,
        "doc_text": text[:14000],  # context for the chat-with-document feature
    }
    yield _sse(done_evt)

    # Only cache successful runs — failures should retry on next upload
    if fields:
        _cache.put(cache_key, {"fields": fields, "provider": served_by, "done": done_evt})


@router.post("/analyze")
async def analyze_document(
    file: UploadFile = File(...),
    doc_type: str = Form(default="auto"),
    provider: str = Form(default="auto"),
    custom_fields: str = Form(default=""),
):
    """Analyze a document and stream extracted fields as SSE events.
    provider: "auto" (cascade) | "groq" | "mistral" | "gemini" | "cohere"
    custom_fields: comma-separated extra field names to extract
    """
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    return StreamingResponse(
        _stream(file_bytes, file.filename or "document", doc_type, provider, custom_fields),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat")
async def chat_with_document(payload: dict):
    """Answer a free-form question about an analyzed document.
    payload: {question, doc_text, fields?, history?: [{role, content}]}
    """
    question = str(payload.get("question", "")).strip()
    doc_text = str(payload.get("doc_text", ""))[:14000]
    if not question or not doc_text.strip():
        raise HTTPException(status_code=400, detail="question and doc_text are required")

    fields = payload.get("fields") or []
    history = payload.get("history") or []
    field_summary = "\n".join(
        f'- {f.get("label", f.get("name"))}: {str(f.get("value"))[:200]}'
        for f in fields[:30] if isinstance(f, dict)
    )

    system = ("You answer questions about a specific document. Use ONLY the document "
              "content and extracted fields provided. If the answer is not in the "
              "document, say so plainly. Be concise. Respond with valid JSON.")
    prompt = (
        f"DOCUMENT CONTENT:\n{doc_text}\n\n"
        f"EXTRACTED FIELDS:\n{field_summary}\n\n"
        f"QUESTION: {question}\n\n"
        'Return JSON: {"answer": "<your concise answer>"}'
    )
    messages = [{"role": m.get("role", "user"), "content": str(m.get("content", ""))[:1000]}
                for m in history[-6:] if m.get("content")]
    messages.append({"role": "user", "content": prompt})

    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(
        _executor, lambda: _llm_state._cascade(messages, system)
    )
    answer = _llm_state._parse_json(raw).get("answer", "")
    if isinstance(answer, (dict, list)):
        # Model sometimes structures the answer — flatten to readable text
        answer = json.dumps(answer, ensure_ascii=False)
    answer = str(answer).strip()
    if not answer:
        raise HTTPException(status_code=503, detail="AI providers unavailable — try again shortly")
    return {"answer": answer, "provider": _llm_state.last_provider}



@router.get("/types")
def get_document_types():
    """Return supported document types and their field schemas."""
    return {
        "types": [
            {
                "id": k,
                "label": v["label"],
                "description": v["description"],
                "fields": v["fields"],
            }
            for k, v in DOC_TYPES.items()
        ]
    }
