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

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from routers.rag import get_rag_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/tenant", tags=["tenant-rag"])

_INTERNAL_TOKEN = os.environ.get("TENANT_INTERNAL_TOKEN", "")

# Providers a tenant bot may use (must match the frontend allowlist in
# src/lib/tenant/config.ts). Each maps to its env key + a safe default model.
_KEYS = {"cohere": "COHERE_API_KEY", "groq": "GROQ_API_KEY",
         "mistral": "MISTRAL_API_KEY", "gemini": "GEMINI_API_KEY"}
_DEFAULT_MODEL = {"cohere": "command-a-03-2025", "groq": "openai/gpt-oss-20b",
                  "mistral": "mistral-small-latest", "gemini": "gemini-3.6-flash"}
# If the chosen provider returns nothing (down / rate-limited), fall back through these
# so the bot stays up — mirrors the main RAG's provider cascade.
_FALLBACK_ORDER = ["cohere", "groq", "gemini", "mistral"]
_GROUNDING_KB = (
    "Answer using ONLY the context below (the bot's knowledge base, plus any web "
    "results). If the knowledge base doesn't contain the answer but web results are "
    "provided, answer from the web and make clear the information came from a web search, "
    "citing the URLs under a 'Sources:' line. If neither has it, say you don't have that "
    "information. Never use outside knowledge."
)
_GROUNDING_WEB_ONLY = (
    "This bot has NO document knowledge base. Answer ONLY from the web results below, "
    "citing their URLs under a 'Sources:' line. Do NOT mention or imply that a knowledge "
    "base was searched. If no web results are provided, say you don't have that "
    "information. Never use outside knowledge."
)
_DEFAULT_PERSONA = "You are a helpful support assistant."


def _apply_date_templates(s: str) -> str:
    """Substitute {{CURRENT_DATE}} / {{CURRENT_MONTH_YEAR}} / {{CURRENT_FY}} so a bot's
    persona can reference 'today' without the owner hand-typing it. FY is the Indian
    financial year (Apr–Mar), matching how these placeholders are typically used."""
    now = datetime.now(timezone.utc)
    fy_start = now.year if now.month >= 4 else now.year - 1
    reps = {
        "{{CURRENT_DATE}}": now.strftime("%d %B %Y"),
        "{{CURRENT_MONTH_YEAR}}": now.strftime("%B %Y"),
        "{{CURRENT_FY}}": f"{fy_start}-{(fy_start + 1) % 100:02d}",
    }
    for k, v in reps.items():
        s = s.replace(k, v)
    return s


def _generate(provider: str, model: str, messages: list[dict], system: str, tool: str) -> tuple[str, str]:
    """Generate with the chosen provider, falling back to other providers if it returns
    nothing (down / rate-limited). Returns (text, provider_used)."""
    from routers.rag.llm import complete
    order = [provider] + [p for p in _FALLBACK_ORDER if p != provider]
    for p in order:
        key = os.environ.get(_KEYS.get(p, ""), "")
        if not key:
            continue
        m = model if p == provider else _DEFAULT_MODEL[p]
        out = complete(p, m, key, messages, system=system, tool=tool).strip()
        if out:
            return out, p
    return "", provider


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
    web_search: bool = False
    has_kb: bool = False


class AnswerResponse(BaseModel):
    answer: str
    provider: str
    web_used: bool = False
    sources: list[str] = []


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

    # Knowledge-base context (retrieved by the frontend) + optional live web results.
    contexts: list[tuple[str, str]] = [("", c.strip()) for c in req.contexts if c and c.strip()]
    web_used = False
    web_sources: list[str] = []
    if req.web_search:
        try:
            from routers.rag.crag import web_search_fallback
            for w in web_search_fallback(question):
                url = (w.get("source", "") or "").replace("web:", "")
                text = (w.get("text", "") or "").strip()
                if text:
                    contexts.append((url, text))
                    if url:
                        web_sources.append(url)
            web_used = bool(web_sources)
        except Exception as exc:  # web search must never break the answer
            logger.warning("tenant web search failed: %s", exc)

    # Nothing to answer from → refuse deterministically (no LLM call = no hallucination).
    # Wording depends on whether a KB exists at all, so the bot never claims it searched
    # a knowledge base that was never attached.
    if not contexts:
        if req.has_kb:
            msg = ("I couldn't find that in the knowledge base"
                   + (", and a web search returned nothing relevant." if req.web_search
                      else ". (Web search is turned off for this bot.)"))
        else:
            msg = ("I couldn't find anything on the web for that." if req.web_search
                   else "I don't have the information to answer that.")
        return AnswerResponse(answer=msg, provider=provider, web_used=web_used, sources=web_sources)

    # The owner's persona sets the bot's voice; grounding is always enforced on top,
    # and reflects whether this bot actually has a knowledge base.
    persona = _apply_date_templates((req.system_prompt or "").strip() or _DEFAULT_PERSONA)
    system = f"{persona}\n\n{_GROUNDING_KB if req.has_kb else _GROUNDING_WEB_ONLY}"
    context_block = "\n\n".join(
        f"[{i + 1}]{(' ' + url) if url else ''}\n{text}" for i, (url, text) in enumerate(contexts)
    )
    user = f"Context:\n{context_block}\n\nQuestion: {question}\n\nAnswer:"

    from routers.rag.llm import complete
    out, used = _generate(provider, model, [{"role": "user", "content": user}], system, "tenant-chat")
    if not out:
        raise HTTPException(
            status_code=502,
            detail=f"all providers returned no output (tried {provider}/{model} first) — likely rate limits; retry shortly or switch the model in Configure",
        )
    return AnswerResponse(answer=out, provider=used, web_used=web_used, sources=web_sources)


class SuggestRequest(BaseModel):
    chunks: list[str] = []
    persona: str = ""


class SuggestResponse(BaseModel):
    questions: list[str]


_SUGGEST_SYSTEM = (
    "You generate short example questions a visitor might ask a help assistant, based "
    "ONLY on the content provided. Output 4 to 5 distinct questions, one per line, with "
    "no numbering, bullets, quotes, or preamble."
)
_SUGGEST_SYSTEM_PERSONA = (
    "Based ONLY on the assistant description below, generate short example questions a "
    "visitor would ask this assistant. Output 4 to 5 distinct questions, one per line, "
    "with no numbering, bullets, quotes, or preamble."
)


def _clean_question(line: str) -> str:
    s = line.strip().lstrip("-*•").strip()
    while s[:2].rstrip(".").isdigit() and "." in s[:3]:  # "1." / "12."
        s = s.split(".", 1)[1].strip()
    return s.strip(' "\'')


@router.post("/suggest", response_model=SuggestResponse)
def suggest(req: SuggestRequest, x_internal_token: str | None = Header(default=None)) -> SuggestResponse:
    """Generate starter questions from a sample of a tenant's knowledge base, for the
    chat's suggestion chips + typeahead. Kept cheap: free provider, small input."""
    _require_internal(x_internal_token)
    content = "\n\n".join(c.strip() for c in req.chunks if c and c.strip())[:4000]
    persona = (req.persona or "").strip()[:4000]
    if content:
        system, user = _SUGGEST_SYSTEM, content
    elif persona:  # no KB → base the starters on the bot's persona/domain
        system, user = _SUGGEST_SYSTEM_PERSONA, persona
    else:
        return SuggestResponse(questions=[])
    out, _ = _generate("cohere", _DEFAULT_MODEL["cohere"], [{"role": "user", "content": user}], system, "tenant-suggest")
    questions = [_clean_question(ln) for ln in (out or "").splitlines() if ln.strip()]
    questions = [q for q in questions if len(q) > 5][:5]
    return SuggestResponse(questions=questions)


class CompleteRequest(BaseModel):
    prefix: str = ""
    persona: str = ""


class CompleteResponse(BaseModel):
    completion: str


_COMPLETE_SYSTEM = (
    "You autocomplete the user's partial question for a help assistant. Return ONLY the "
    "text that continues after the given prefix to form one natural, complete question — "
    "do NOT repeat the prefix, no quotes, no preface, at most ~12 words. If there is no "
    "sensible completion, return nothing."
)


@router.post("/complete", response_model=CompleteResponse)
def complete_text(req: CompleteRequest, x_internal_token: str | None = Header(default=None)) -> CompleteResponse:
    """Inline ghost-text completion of a partial question (Gmail-style). Cheap + short;
    the frontend debounces calls and the toggle is off by default."""
    _require_internal(x_internal_token)
    prefix = (req.prefix or "").strip()
    if len(prefix) < 3:
        return CompleteResponse(completion="")
    persona = (req.persona or "").strip()[:1000]
    user = (f"Assistant domain: {persona}\n\n" if persona else "") + f"Prefix: {prefix}"
    out, _ = _generate("cohere", _DEFAULT_MODEL["cohere"], [{"role": "user", "content": user}], _COMPLETE_SYSTEM, "tenant-complete")
    out = out.strip().strip('"\'')
    if out.lower().startswith(prefix.lower()):  # strip accidental prefix echo
        out = out[len(prefix):]
    return CompleteResponse(completion=out[:120])
