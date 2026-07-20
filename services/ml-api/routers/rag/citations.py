"""Citation formatting shared by rag/query.py — system-prompt injection labels
and the SSE 'source' doc payload. Split out of query.py to stay under the
project's file-length limit and to de-duplicate the doc-payload construction
that previously appeared twice (cached-hit path and live path)."""
from __future__ import annotations


def build_system_prompt(tool_context: str, chunks: list[dict]) -> str:
    parts: list[str] = []
    if tool_context:
        parts.append(tool_context.strip())

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
