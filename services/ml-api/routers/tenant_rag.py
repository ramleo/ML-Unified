"""Q3 M1 — stateless tenant-RAG compute for the chatbot builder.

The multi-tenant control plane lives in the frontend (it holds the Supabase
service-role key and owns the pgvector store). The Space stays a stateless
compute node — exactly the Q1/Q2 boundary — exposing two internal operations the
frontend orchestrates:

  POST /internal/tenant/embed   {texts:[...]}              -> {embeddings:[[...]]}
  POST /internal/tenant/answer  {question, contexts:[...]} -> {answer, provider}

Both are gated by a shared secret (`TENANT_INTERNAL_TOKEN`, header
`x-internal-token`) — these are frontend→Space calls, never public. Fail-closed:
if the token is unset the endpoints reject everything.

Embeddings reuse the RAG all-MiniLM-L6-v2 model already loaded on the Space
(384-dim) — no new model, no new dependency. Answering reuses the Cohere key the
rest of the platform uses (free, reliable), with a plain non-streaming call.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from routers.rag import get_rag_state

router = APIRouter(prefix="/internal/tenant", tags=["tenant-rag"])

_INTERNAL_TOKEN = os.environ.get("TENANT_INTERNAL_TOKEN", "")
_COHERE_MODEL = "command-a-03-2025"


def _require_internal(token: str | None) -> None:
    """Fail-closed shared-secret check for frontend→Space calls."""
    if not _INTERNAL_TOKEN or token != _INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


class EmbedRequest(BaseModel):
    texts: list[str]


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    dim: int


@router.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest, x_internal_token: str | None = Header(default=None)) -> EmbedResponse:
    _require_internal(x_internal_token)
    texts = [t for t in (req.texts or []) if t and t.strip()]
    if not texts:
        raise HTTPException(status_code=400, detail="no texts")
    try:
        state = get_rag_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="embedding model warming up")
    if state.embedding_fn is None:
        raise HTTPException(status_code=503, detail="embedding model unavailable")
    vectors = state.embedding_fn(texts)
    out = [list(map(float, v)) for v in vectors]
    return EmbedResponse(embeddings=out, dim=len(out[0]) if out else 0)


class AnswerRequest(BaseModel):
    question: str
    contexts: list[str] = []


class AnswerResponse(BaseModel):
    answer: str
    provider: str


def _answer_cohere(prompt: str) -> str:
    import httpx

    key = os.environ.get("COHERE_API_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="no generation key configured")
    r = httpx.post(
        "https://api.cohere.com/v2/chat",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": _COHERE_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        },
        timeout=30.0,
    )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"generation failed ({r.status_code})")
    data = r.json()
    parts = data.get("message", {}).get("content", [])
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    return text.strip()


@router.post("/answer", response_model=AnswerResponse)
def answer(req: AnswerRequest, x_internal_token: str | None = Header(default=None)) -> AnswerResponse:
    _require_internal(x_internal_token)
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="no question")

    context_block = "\n\n".join(
        f"[{i + 1}] {c.strip()}" for i, c in enumerate(req.contexts) if c and c.strip()
    )
    if context_block:
        prompt = (
            "You are a helpful assistant answering ONLY from the context below. "
            "If the answer is not in the context, say you don't know. Do not use "
            "outside knowledge.\n\n"
            f"Context:\n{context_block}\n\n"
            f"Question: {question}\n\nAnswer:"
        )
    else:
        prompt = (
            "You are a helpful assistant. The knowledge base has no relevant "
            "information for this question, so say you don't have that information.\n\n"
            f"Question: {question}\n\nAnswer:"
        )

    return AnswerResponse(answer=_answer_cohere(prompt), provider="cohere")
