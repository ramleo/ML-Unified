"""
Testwright (QA Automation) — Author stage.

POST /qa/author/generate — plain-English test steps -> a runnable Playwright
TypeScript test with resilient locators. Generation ONLY, no execution.
"""

import json
import logging
import re

from fastapi import APIRouter, Request

from routers.qa import config
from routers.qa.deps import complete, resolve_key, record_call, limiter, LLM_LIMIT
from routers.qa.models import (
    GenerateRequest, GenerateResponse,
    AssertRequest, AssertResponse, AssertSuggestion,
)
from routers.qa.prompts import AUTHOR_SYSTEM, ASSERTIONS_SYSTEM

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/author")


def _strip_fences(raw: str) -> str:
    """Models sometimes wrap the file in a ```typescript fence despite the
    prompt. Pull the fenced block out if present, else return trimmed text."""
    if not raw:
        return ""
    fence = re.search(r"```(?:ts|typescript|javascript|js)?\s*\n(.*?)```", raw, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return raw.strip()


def _looks_like_test(code: str) -> bool:
    """Cheap sanity gate — a valid answer imports Playwright and defines a test.
    Guards against a provider returning prose or an apology instead of code."""
    return "@playwright/test" in code and "test(" in code


def generate_test(instructions: str, base_url: str, test_name: str) -> tuple[str, str] | None:
    user_parts = [f"Scenario to test:\n{instructions.strip()}"]
    if base_url.strip():
        user_parts.append(f"\nBase URL of the site under test: {base_url.strip()}")
    if test_name.strip():
        user_parts.append(f"\nUse this as the describe-block title: {test_name.strip()}")
    user_msg = "\n".join(user_parts)

    for provider, model in config.GEN_CANDIDATES:
        key = resolve_key(provider)
        if not key:
            continue
        try:
            raw = complete(
                provider, model, key,
                [{"role": "user", "content": user_msg}],
                system=AUTHOR_SYSTEM,
            )
        except Exception as exc:
            logger.warning("qa/author: %s failed: %s", provider, exc)
            continue
        code = _strip_fences(raw)
        if _looks_like_test(code):
            return code, provider
        logger.warning("qa/author: %s returned non-test output", provider)
    logger.error("qa/author: every candidate failed (%s)",
                 ", ".join(p for p, _ in config.GEN_CANDIDATES))
    return None


@router.post("/generate", response_model=GenerateResponse)
@limiter.limit(LLM_LIMIT)
def generate(request: Request, req: GenerateRequest):
    record_call(config.FEATURE, pool=config.BUDGET_POOL, daily_cap_env=config.DAILY_CAP_ENV)
    result = generate_test(req.instructions, req.base_url, req.test_name)
    if result is None:
        return GenerateResponse(code="", provider=None)
    code, provider = result
    return GenerateResponse(code=code, provider=provider)


def _parse_suggestions(raw: str) -> list[AssertSuggestion]:
    """Pull a JSON array of {title, code, why} out of a model reply, tolerating a
    stray code fence. Returns [] on anything malformed."""
    text = _strip_fences(raw)
    try:
        data = json.loads(text)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: list[AssertSuggestion] = []
    for item in data[: config.MAX_ASSERT_SUGGESTIONS]:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).strip()
        if not code:
            continue
        out.append(AssertSuggestion(
            title=str(item.get("title", "Assertion")).strip()[:120],
            code=code[:400],
            why=str(item.get("why", "")).strip()[:300],
        ))
    return out


def suggest_assertions(code: str) -> tuple[list[AssertSuggestion], str] | None:
    user_msg = f"Playwright test to review:\n{code.strip()}"
    for provider, model in config.GEN_CANDIDATES:
        key = resolve_key(provider)
        if not key:
            continue
        try:
            raw = complete(
                provider, model, key,
                [{"role": "user", "content": user_msg}],
                system=ASSERTIONS_SYSTEM,
            )
        except Exception as exc:
            logger.warning("qa/assertions: %s failed: %s", provider, exc)
            continue
        suggestions = _parse_suggestions(raw)
        if suggestions:
            return suggestions, provider
        logger.warning("qa/assertions: %s returned no usable suggestions", provider)
    return None


@router.post("/assertions", response_model=AssertResponse)
@limiter.limit(LLM_LIMIT)
def assertions(request: Request, req: AssertRequest):
    record_call(config.ASSERT_FEATURE, pool=config.ASSERT_BUDGET_POOL,
                daily_cap_env=config.ASSERT_DAILY_CAP_ENV)
    result = suggest_assertions(req.code)
    if result is None:
        return AssertResponse(suggestions=[], provider=None)
    suggestions, provider = result
    return AssertResponse(suggestions=suggestions, provider=provider)
