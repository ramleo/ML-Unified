"""
QA Test Author — plain-English test steps -> runnable Playwright TypeScript.

Phase 1 of the AI Test-Automation tool (see docs/QA_AUTOMATION_AND_LOGGING_PLAN.md):
generation ONLY, no execution. The user describes what to test in plain English
and this returns a complete, runnable Playwright test file using resilient
role/text/accessible-name locators. Nothing is run here — the risk (SSRF,
arbitrary-URL execution) lives in the execution half, which is a later phase.

Same fixed-server-key + free-provider pattern as routers/siem_triage.py and
routers/ai_code_detector.py: cohere leads because it is free and reliable,
mistral is the second opinion. Gemini is deliberately absent — it is the only
paid key and this endpoint is public.
"""

import logging
import re

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from security.rate_limit import limiter, LLM_LIMIT
from security.budget import check_and_record_call
from routers.rag.llm import complete
from routers.rag.query_helpers import _resolve_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa-test-author")

_MAX_INSTRUCTIONS = 4000
_MAX_BASE_URL = 300
_MAX_NAME = 120

# Same cascade as the other public LLM endpoints: free + reliable first.
_GEN_CANDIDATES = [
    ("cohere", "command-a-03-2025"),
    ("mistral", "mistral-small-latest"),
]

_GEN_SYSTEM = (
    "You are an expert QA automation engineer. You are given a plain-English "
    "description of a browser test scenario. Produce ONE complete, runnable "
    "Playwright test file written in TypeScript, and NOTHING else.\n\n"
    "Rules:\n"
    "1. Start with `import { test, expect } from '@playwright/test';`.\n"
    "2. If a base URL is provided, define `const BASE_URL = '<url>';` near the "
    "top and navigate with `page.goto(BASE_URL + '<path>')`. If none is given, "
    "define `const BASE_URL = 'http://localhost:3000';` as a placeholder.\n"
    "3. Prefer RESILIENT locators — `getByRole('button', { name: ... })`, "
    "`getByLabel(...)`, `getByText(...)`, `getByPlaceholder(...)`, "
    "`getByTestId(...)`. AVOID brittle CSS/XPath selectors and positional "
    "`.nth(...)` indices. A short comment on each locator should say why it is "
    "resilient (e.g. matches the accessible name, not the DOM position).\n"
    "4. Every scenario MUST end in at least one real assertion using `expect` "
    "(`toBeVisible`, `toHaveURL`, `toHaveText`, `toHaveCount`, etc.).\n"
    "5. Wrap the scenario(s) in `test.describe(...)` with clear `test(...)` "
    "titles taken from the user's description.\n"
    "6. Output raw TypeScript ONLY — no markdown code fences, no explanation "
    "before or after the code."
)


class GenerateRequest(BaseModel):
    instructions: str = Field(..., min_length=1, max_length=_MAX_INSTRUCTIONS)
    base_url: str = Field("", max_length=_MAX_BASE_URL)
    test_name: str = Field("", max_length=_MAX_NAME)


class GenerateResponse(BaseModel):
    code: str
    provider: str | None = None


def _strip_fences(raw: str) -> str:
    """Models often wrap the file in a ```typescript fence despite being told
    not to. Pull the fenced block out if present, else return the trimmed text."""
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

    for provider, model in _GEN_CANDIDATES:
        key = _resolve_key(provider, None)
        if not key:
            continue
        try:
            raw = complete(
                provider, model, key,
                [{"role": "user", "content": user_msg}],
                system=_GEN_SYSTEM,
            )
        except Exception as exc:
            logger.warning("qa-test-author: %s failed: %s", provider, exc)
            continue
        code = _strip_fences(raw)
        if _looks_like_test(code):
            return code, provider
        logger.warning("qa-test-author: %s returned non-test output", provider)
    logger.error("qa-test-author: every candidate failed (%s)",
                 ", ".join(p for p, _ in _GEN_CANDIDATES))
    return None


@router.post("/generate", response_model=GenerateResponse)
@limiter.limit(LLM_LIMIT)
def generate(request: Request, req: GenerateRequest):
    check_and_record_call(
        "qa-test-author", pool="qa_test_author",
        daily_cap_env="QA_TEST_AUTHOR_DAILY_CAP",
    )
    result = generate_test(req.instructions, req.base_url, req.test_name)
    if result is None:
        return GenerateResponse(code="", provider=None)
    code, provider = result
    return GenerateResponse(code=code, provider=provider)
