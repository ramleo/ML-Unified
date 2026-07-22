"""Standalone CSV ingestion for multimodal RAG — reuses the 'table'
chunk_type/retrieval path a PDF's embedded tables already flow through.
Split out of mm_ingest.py to stay under the project's file-length limit.
"""
from __future__ import annotations

MAX_CSV_ROWS = 500   # bounds cost/latency the same way MAX_PAGES bounds PDFs
_CSV_CHUNK_ROWS = 50  # rows per chunk — keeps each chunk's embedding focused


def looks_like_csv(filename: str, content_type: str) -> bool:
    return filename.lower().endswith(".csv") or content_type in ("text/csv", "application/csv")


def _rows_to_markdown(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(c).replace("|", " ") for c in row) + " |")
    return "\n".join(lines)


def build_csv_chunks(file_bytes: bytes, source: str) -> tuple[list[dict], list[str], dict]:
    """A standalone CSV upload — same 'table' chunk_type as a PDF's embedded
    tables, so it flows through the identical retrieval/citation path.
    No page_images (there's nothing to render as a thumbnail)."""
    import io
    import pandas as pd

    df = pd.read_csv(io.BytesIO(file_bytes))
    df = df.head(MAX_CSV_ROWS)
    header = [str(c) for c in df.columns]

    chunks: list[dict] = []
    for i in range(0, len(df), _CSV_CHUNK_ROWS):
        rows = df.iloc[i:i + _CSV_CHUNK_ROWS].astype(str).values.tolist()
        md = _rows_to_markdown(header, rows)
        chunks.append({"text": md, "source": source, "chunk_index": len(chunks),
                       "chunk_type": "table", "page": len(chunks) + 1})

    return chunks, [], {"text": 0, "table": len(chunks), "figure": 0}
