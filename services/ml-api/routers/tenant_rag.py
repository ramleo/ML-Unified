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

# Providers a tenant bot may use (must match the frontend allowlist in
# src/lib/tenant/config.ts). Each maps to its env key + a safe default model.
_KEYS = {"cohere": "COHERE_API_KEY", "groq": "GROQ_API_KEY",
         "mistral": "MISTRAL_API_KEY", "gemini": "GEMINI_API_KEY"}
_DEFAULT_MODEL = {"cohere": "command-a-03-2025", "groq": "openai/gpt-oss-20b",
                  "mistral": "mistral-small-latest", "gemini": "gemini-3.6-flash"}
_GROUNDING = (
    "Answer the user's question using ONLY the context provided below. If the answer "
    "is not in the context, say you don't have that information. Do not use outside "
    "knowledge."
)
_DEFAULT_PERSONA = "You are a helpful support assistant."


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
    system_prompt: str = ""
    provider: str = "cohere"
    model: str = ""


class AnswerResponse(BaseModel):
    answer: str
    provider: str


@router.post("/answer", response_model=AnswerResponse)
def answer(req: AnswerRequest, x_internal_token: str | None = Header(default=None)) -> AnswerResponse:
    _require_internal(x_internal_token)
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="no question")

    provider = (req.provider or "cohere").lower()
    if provider not in _KEYS:
        provider = "cohere"
    model = (req.model or "").strip() or _DEFAULT_MODEL[provider]
    key = os.environ.get(_KEYS[provider], "")
    if not key:
        raise HTTPException(status_code=503, detail=f"no key configured for {provider}")

    # The owner's persona sets the bot's voice; grounding is always enforced on top.
    persona = (req.system_prompt or "").strip() or _DEFAULT_PERSONA
    system = f"{persona}\n\n{_GROUNDING}"
    context_block = "\n\n".join(
        f"[{i + 1}] {c.strip()}" for i, c in enumerate(req.contexts) if c and c.strip()
    )
    user = (
        (f"Context:\n{context_block}\n\n" if context_block
         else "Context: (the knowledge base has no relevant information)\n\n")
        + f"Question: {question}\n\nAnswer:"
    )

    from routers.rag.llm import complete
    out = complete(provider, model, key, [{"role": "user", "content": user}],
                   system=system, tool="tenant-chat").strip()
    if not out:
        raise HTTPException(status_code=502, detail="generation failed")
    return AnswerResponse(answer=out, provider=provider)
