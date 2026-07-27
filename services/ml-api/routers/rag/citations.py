"""Citation formatting shared by rag/query.py — system-prompt injection labels,
the SSE 'source' doc payload, and post-hoc "was this chunk actually used"
detection. Split out of query.py to stay under the project's file-length
limit and to de-duplicate the doc-payload construction that previously
appeared twice (cached-hit path and live path)."""
from __future__ import annotations

import json
import re

from routers.rag.pii import redact_pii
from routers.rag.entities import decode_entities
from routers.rag.mm_objects import decode_objects


def _decode_bbox(raw) -> list[float] | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


_VISUAL_CHUNK_TYPES = {"video", "figure", "image"}


def _has_multiple_visual_chunks_per_source(chunks: list[dict]) -> bool:
    counts: dict[str, int] = {}
    for c in chunks:
        if c.get("chunk_type") in _VISUAL_CHUNK_TYPES:
            src = c.get("source", "")
            counts[src] = counts.get(src, 0) + 1
    return any(n >= 2 for n in counts.values())


_ANSWER_LENGTH_INSTRUCTIONS = {
    "concise": "Answer in 1-3 sentences — the shortest answer that fully addresses the "
               "question, no preamble, no extra context beyond what was asked.",
    "detailed": "Answer thoroughly — include relevant context, explain reasoning where "
                "useful, and cover related details from the source rather than the bare "
                "minimum, while staying grounded in the retrieved content.",
}


def build_system_prompt(tool_context: str, chunks: list[dict], restrict_to_uploads: bool = False,
                        answer_length: str = "normal", redact: bool = False) -> str:
    parts: list[str] = []
    if tool_context:
        parts.append(tool_context.strip())

    length_instruction = _ANSWER_LENGTH_INSTRUCTIONS.get(answer_length)
    if length_instruction:
        parts.append(length_instruction)

    if restrict_to_uploads:
        parts.append(
            "Answer ONLY using the retrieved content below, from the document the "
            "user uploaded. Do not use outside/general knowledge to fill gaps. If "
            "the retrieved content doesn't contain the answer, say plainly that "
            "the uploaded document doesn't cover it — do not guess or answer from "
            "what you generally know about the topic."
        )

    if chunks:
        parts.append(
            "Use the following retrieved knowledge to answer the user's question. "
            "The [source, page, type] labels below are for your reference only — "
            "the interface already shows citations separately, so do NOT repeat, "
            "quote, or append any [source...] label in your answer text. Write a "
            "plain, direct answer with no bracketed references at all."
        )
        if _has_multiple_visual_chunks_per_source(chunks):
            # Observed live: a video's two independently-captioned frames
            # described the same speaker with different wording/focus (one
            # mentioned the pocket square, the other the gray hair/beard) —
            # the model, reading only text, concluded there were "two men."
            # Each caption is generated in isolation with no cross-frame
            # identity link, so this caveat is needed whenever a source
            # contributes 2+ visual chunks — never assumed away by chunk
            # count alone, since a real multi-subject video is possible too.
            parts.append(
                "Note: multiple video-frame, figure, or image chunks below from the "
                "SAME source are very likely different moments/angles of the SAME "
                "subject(s), captioned independently — their wording can differ "
                "(what's mentioned, level of detail) without meaning they show "
                "different people or objects. Do not conclude there are multiple "
                "distinct people/items just because two descriptions read "
                "differently — only do so if they are clearly incompatible."
            )
        parts.append("---")
        for c in chunks:
            src = c.get("source", "unknown")
            text = redact_pii(c.get("text", "")) if redact else c.get("text", "")
            chunk_type = c.get("chunk_type")
            page = c.get("page")
            label = src
            if chunk_type and chunk_type != "text":
                label += f", page {page}, {chunk_type}" if page else f", {chunk_type}"
            elif page:
                label += f", page {page}"
            # Detected objects (MMRAG-07 follow-up) — the bounding-box overlay
            # is a frontend-only visual, invisible to the model; without this,
            # a "where is X" question gets answered from caption prose alone,
            # which rarely describes position. Counts, not a flat repeated
            # list, so "person (×3)" reads as one fact, not noise.
            objects = decode_objects(c.get("objects"))
            if objects:
                counts: dict[str, int] = {}
                for o in objects:
                    counts[o["label"]] = counts.get(o["label"], 0) + 1
                obj_desc = ", ".join(f"{lbl} (×{n})" if n > 1 else lbl for lbl, n in counts.items())
                label += f" — contains: {obj_desc}"
            parts.append(f"[{label}]\n{text}")
            if c.get("number_mismatch"):
                # The figure's AI caption and its OCR pass cited different
                # numbers for the same visual — a real sign one of the two
                # misread a value, not a generic hedge added to every figure.
                parts.append(
                    "(Note: the description above and a separate OCR reading of "
                    "this same figure disagree on at least one number — if your "
                    "answer relies on a number from this source, say it's "
                    "uncertain and should be verified against the original.)"
                )
            parts.append("---")
    elif restrict_to_uploads:
        parts.append("No relevant content was retrieved from the uploaded document for this question.")

    return "\n\n".join(parts) if parts else "You are a helpful AI assistant."


def build_source_doc(chunk: dict, redact: bool = False) -> dict:
    """The SSE 'source' event's 'doc' payload — includes multimodal fields
    (chunk_type/page/bbox) additively; None for chunks that lack them.
    redact=True (shared-link viewers only) also masks PII in the citation
    text itself, not just what's sent to the LLM — a screenshot of the
    citation card would otherwise still show the real value."""
    return {
        "text": redact_pii(chunk["text"]) if redact else chunk["text"],
        "source": chunk.get("source", ""),
        "score": round(chunk.get("score", 0.0), 4),
        "display_score": round(chunk.get("display_score", chunk.get("score", 0.0)), 4),
        "chunk_type": chunk.get("chunk_type"),
        "page": chunk.get("page"),
        "bbox": _decode_bbox(chunk.get("bbox")),
        "objects": decode_objects(chunk.get("objects")) or None,
        "number_mismatch": chunk.get("number_mismatch") or None,
        "pii_types": chunk.get("pii_types") or None,
        "blurry": chunk.get("blurry") or None,
        "entities": decode_entities(chunk.get("entities")) or None,
    }


# The citation list shows every chunk sent to the LLM as context — in
# restrict_to_uploads mode that can include chunks the model never actually
# drew from (observed live: a video frame's appearance description sitting
# next to a quote that came entirely from a different, transcript chunk).
# Rerank score is NOT a usable proxy for "was this used" — the transcript in
# that exact case scored LOWER than the unused frames. Instead, measure
# whether the chunk's own words actually appear in the generated answer:
# what fraction of the answer's 4-word phrases are found verbatim in this
# chunk. A real quote/close paraphrase scores high; unrelated context scores
# near zero, regardless of what the reranker thought of it beforehand.
_CITATION_OVERLAP_THRESHOLD = 0.2


def _ngrams(text: str, n: int = 4) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def likely_used_indices(chunks: list[dict], answer: str) -> list[int]:
    """Indices into `chunks` whose text substantially overlaps the generated
    answer — the citations that actually appear to back the answer, as
    opposed to context that was merely available."""
    answer_ngrams = _ngrams(answer)
    if not answer_ngrams:
        return []
    used = []
    for i, c in enumerate(chunks):
        chunk_ngrams = _ngrams(c.get("text", ""))
        if not chunk_ngrams:
            continue
        overlap = len(answer_ngrams & chunk_ngrams) / len(answer_ngrams)
        if overlap >= _CITATION_OVERLAP_THRESHOLD:
            used.append(i)
    return used
