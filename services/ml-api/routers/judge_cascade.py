"""Shared LLM-judge cascade — the one place the fixed-server-key "second
opinion" provider order and the try-each-until-one-parses loop live.

Three public tools add an independent LLM opinion using a FIXED SERVER KEY (no
user API key): prompt-injection-check, ai-code-detector, siem-triage. Each one
had its own copy of the SAME provider list and the SAME
resolve-key / call / parse / fall-through loop. This is that loop, once. The
per-tool parts stay in each tool — how the user message is built, and how the
raw reply is parsed into a verdict (`parse`). Only the cascade mechanics are here.

NOTE: this is the JUDGE cascade (a fixed 3-provider second opinion). The
GENERATION cascades — document (`routers/document/_llm.py`), RAG
(`routers/rag/generation.py`), EDA suggest (`routers/eda/_suggest.py`), tenant
RAG (`routers/tenant_rag.py`) — are deliberately separate: they carry BYOK,
caller-pick-first, paid-provider-last, and streaming semantics this loop doesn't,
and `tests/test_provider_cascade.py` pins their order. Don't fold them in here.
"""
import logging
from typing import Callable, TypeVar

from routers.rag.llm import complete
from routers.rag.query_helpers import _resolve_key

logger = logging.getLogger(__name__)

T = TypeVar("T")

# The fixed-server-key judge providers, tried in order. Cohere leads (free,
# reliable); Mistral is the second opinion; Groq (openai/gpt-oss-120b) is a third
# free fallback on a SEPARATE rate-limit pool, so it still answers when Cohere
# and Mistral are both 429 (as free tiers often are under load). gpt-oss over
# Groq's Qwen models, which leak <think> and truncate JSON. Gemini is absent on
# purpose — it is the only paid key and these endpoints are public/unauthenticated.
JUDGE_CANDIDATES: list[tuple[str, str]] = [
    ("cohere", "command-a-03-2025"),
    ("mistral", "mistral-small-latest"),
    ("groq", "openai/gpt-oss-120b"),
]


def run_judge_cascade(
    content: str,
    system: str,
    tool: str,
    parse: Callable[[str], T | None],
    candidates: list[tuple[str, str]] | None = None,
) -> T | None:
    """Try each judge provider in order; return the first reply that `parse`
    turns into a non-None verdict, else None (every provider was unreachable /
    rate-limited, or returned output `parse` rejected).

    `complete()` swallows provider errors (e.g. HTTP 429) and returns "" rather
    than raising, so an empty raw means the provider was unavailable, NOT that it
    sent bad JSON — the two are logged distinctly so a silent degrade is visible.
    `tool` is both the telemetry tag passed to `complete()` and the log prefix.
    """
    order = candidates or JUDGE_CANDIDATES
    for provider, model in order:
        key = _resolve_key(provider, None)
        if not key:
            continue
        try:
            raw = complete(provider, model, key,
                           [{"role": "user", "content": content}],
                           system=system, tool=tool)
        except Exception as exc:
            logger.warning("%s judge: %s failed: %s", tool, provider, exc)
            continue
        verdict = parse(raw)
        if verdict is not None:
            return verdict
        if not raw or not raw.strip():
            logger.warning("%s judge: %s returned no output "
                           "(provider unavailable or rate-limited)", tool, provider)
        else:
            logger.warning("%s judge: %s returned unparseable output: %.200s",
                           tool, provider, raw)
    logger.error("%s judge: every candidate failed (%s)",
                 tool, ", ".join(p for p, _ in order))
    return None
