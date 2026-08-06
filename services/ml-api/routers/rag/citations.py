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
    """True when a source contributes 2+ visual chunks from DIFFERENT
    pages/frames — genuinely ambiguous whether they show the same subject
    (see the caveat this gates, below). Keyed on (source, page), not just
    source: MMRAG-13 region-level captioning can put 2+ figure chunks on
    the SAME page (e.g. a chart and an unrelated logo) — those are
    deliberately distinct regions by construction, not an ambiguous "is
    this the same subject captioned twice" case, so they shouldn't trigger
    this caveat the way two different video frames or PDF pages would."""
    pages_by_source: dict[str, set] = {}
    for c in chunks:
        if c.get("chunk_type") in _VISUAL_CHUNK_TYPES:
            src = c.get("source", "")
            pages_by_source.setdefault(src, set()).add(c.get("page"))
    return any(len(pages) >= 2 for pages in pages_by_source.values())


_ANSWER_LENGTH_INSTRUCTIONS = {
    "concise": "Answer in 1-3 sentences — the shortest answer that fully addresses the "
               "question, no preamble, no extra context beyond what was asked.",
    "detailed": "Answer thoroughly — include relevant context, explain reasoning where "
                "useful, and cover related details from the source rather than the bare "
                "minimum, while staying grounded in the retrieved content.",
}


def build_system_prompt(tool_context: str, chunks: list[dict], restrict_to_uploads: bool = False,
                        answer_length: str = "normal", redact: bool = False,
                        verification_note: str = "") -> str:
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

    if verification_note:
        parts.append(verification_note)

    if chunks:
        parts.append(
            "Use the following retrieved knowledge to answer the user's question. "
            "The [source, page, type] labels below are for your reference only — "
            "the interface already shows citations separately, so do NOT repeat, "
            "quote, or append any [source...] label in your answer text. Write a "
            "plain, direct answer with no bracketed references at all."
        )
        # MMRAG-12: without this, a non-English question risks getting an
        # English answer just because the context happened to be in English
        # (captions/transcripts are usually English by default). Most models
        # already mirror the question's language on their own (observed live
        # via Groq's llama-3.3-70b), but this makes it explicit rather than
        # relying on that being consistent across providers. Deliberately NOT
        # hardcoded to assume the retrieved knowledge is in English — a
        # broadened/low-floor retrieval pass (query.py's self-correction
        # retry) can pull in a non-English chunk, and a false "it's all
        # English" premise in the prompt was observed to drag the answer
        # itself into that chunk's language instead of the question's.
        parts.append(
            "Answer in the same language the user's question is written in, "
            "regardless of what language the retrieved knowledge below happens "
            "to be in — translate the relevant facts into the question's "
            "language, don't just copy the source language."
        )
        # Observed live: "what is career timeline?" was read as "define the
        # general concept of a career timeline" and correctly declined since
        # the document doesn't define that term — but the document DOES have
        # a section literally titled "Career Timeline", and a rephrased "what
        # is shown under career timeline?" got the real answer. A "what
        # is <X>" question whose <X> matches a heading/label in the chunks
        # below is asking what that section contains, not for a dictionary
        # definition of <X> as a standalone concept.
        parts.append(
            "If the question asks \"what is <X>\" (or similar) and <X> matches a "
            "section heading, label, or title appearing in the retrieved content "
            "below, treat it as asking what that section contains — answer with "
            "its contents, don't decline on the grounds that <X> isn't defined as "
            "a general concept."
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
            # Detected-object descriptions are baked into `text` itself at
            # ingest time (see mm_objects.describe_objects) — not injected
            # here — so the same sentence backs both the LLM's answer AND
            # groundedness/citation-overlap scoring, which only ever read
            # chunk["text"]. Earlier versions appended it to a local,
            # prompt-only variable here; that worked for the chat answer but
            # left the score checks blind to it (real bug, fixed).
            chunk_block = f"[{label}]\n{text}"
            parts.append(chunk_block)
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
        # Seconds into the source video (MMRAG-09) — only present on
        # frame-captioned "video" chunks; absent (None) for everything else,
        # including audio-transcript chunks, which the frontend instead
        # locates by matching this citation's text against the transcript's
        # own timestamped segments (a chunk here spans many spoken words, so
        # no single timestamp would represent it as precisely).
        "timestamp_s": chunk.get("timestamp_s"),
        "bbox": _decode_bbox(chunk.get("bbox")),
        "objects": decode_objects(chunk.get("objects")) or None,
        "signatures": decode_objects(chunk.get("signatures")) or None,
        "tampering": decode_objects(chunk.get("tampering")) or None,
        "number_mismatch": chunk.get("number_mismatch") or None,
        "pii_types": chunk.get("pii_types") or None,
        "blurry": chunk.get("blurry") or None,
        "entities": decode_entities(chunk.get("entities")) or None,
        # "Why was this cited" trace (MMRAG-08) — retrieval_trace has
        # per-signal {score, rank} for whichever of dense/BM25 actually
        # surfaced this chunk (absent if only one ran, e.g. no BM25 corpus
        # yet); hybrid_score is the RRF-fused score BEFORE reranking;
        # rerank_score is the cross-encoder's verdict (same value "score"
        # above already carries, repeated here so the trace panel doesn't
        # need to know that "score" means something different post-rerank
        # than pre-rerank). type_boost is 1.0 (omitted) unless a
        # restrict_to_uploads query's wording matched this chunk's type.
        "retrieval_trace": chunk.get("retrieval_trace") or None,
        "hybrid_score": round(chunk["hybrid_score"], 5) if "hybrid_score" in chunk else None,
        "rerank_score": round(chunk["rerank_score"], 4) if "rerank_score" in chunk else None,
        "type_boost": chunk["type_boost"] if chunk.get("type_boost", 1.0) != 1.0 else None,
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
