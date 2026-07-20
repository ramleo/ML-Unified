"""Citation formatting shared by rag/query.py — system-prompt injection labels
and the SSE 'source' doc payload. Split out of query.py to stay under the
project's file-length limit and to de-duplicate the doc-payload construction
that previously appeared twice (cached-hit path and live path)."""
from __future__ import annotations


def build_system_prompt(tool_context: str, chunks: list[dict], restrict_to_uploads: bool = False) -> str:
    parts: list[str] = []
    if tool_context:
        parts.append(tool_context.strip())

    if restrict_to_uploads:
        parts.append(
            "Answer ONLY using the retrieved content below, from the document the "
            "user uploaded. Do not use outside/general knowledge to fill gaps. If "
            "the retrieved content doesn't contain the answer, say plainly that "
            "the uploaded document doesn't cover it — do not guess or answer from "
            "what you generally know about the topic."
        )

    if chunks:
        parts.append("Use the following retrieved knowledge to answer the user's question:")
        parts.append("---")
        for c in chunks:
            src = c.get("source", "unknown")
            text = c.get("text", "")
            chunk_type = c.get("chunk_type")
            page = c.get("page")
            label = src
            if chunk_type and chunk_type != "text":
                label += f", page {page}, {chunk_type}" if page else f", {chunk_type}"
            elif page:
                label += f", page {page}"
            parts.append(f"[{label}]\n{text}")
            parts.append("---")
    elif restrict_to_uploads:
        parts.append("No relevant content was retrieved from the uploaded document for this question.")

    return "\n\n".join(parts) if parts else "You are a helpful AI assistant."


def build_source_doc(chunk: dict) -> dict:
    """The SSE 'source' event's 'doc' payload — includes multimodal fields
    (chunk_type/page/bbox) additively; None for chunks that lack them."""
    return {
        "text": chunk["text"],
        "source": chunk.get("source", ""),
        "score": round(chunk.get("score", 0.0), 4),
        "display_score": round(chunk.get("display_score", chunk.get("score", 0.0)), 4),
        "chunk_type": chunk.get("chunk_type"),
        "page": chunk.get("page"),
        "bbox": chunk.get("bbox"),
    }
