"""
Testwright (QA Automation) — Author stage.

POST /qa/author/generate — plain-English test steps -> a runnable Playwright
TypeScript test with resilient locators. Generation ONLY, no execution.

The deterministic locator/code post-processors live in routers/qa/locators.py and
run on every generated test (and are reused by Heal).
"""

import json
import logging
import re

from fastapi import APIRouter, Request

from routers.qa import config
from routers.qa.deps import complete, select_candidates, record_call, limiter, LLM_LIMIT
from routers.rag.call_log import record_call as _log_outcome
from routers.qa.locators import (
    strip_hard_waits, shorten_long_names, href_link_locators,
    disambiguate_locators, first_on_href_locators, strip_junk_locators,
    sanitize_option_punctuation,
)
from routers.qa.validate import looks_syntactically_valid
from routers.qa.action_gate import drop_ungrounded_actions, repair_ungrounded_names
from routers.qa.models import (
    GenerateRequest, GenerateResponse,
    AssertRequest, AssertResponse, AssertSuggestion,
)
from routers.qa.prompts import AUTHOR_SYSTEM, AUTHOR_GROUNDING, ASSERTIONS_SYSTEM

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


_HEDGE_RE = re.compile(
    r"placeholder selector|actual selector|in a real test|you would need|"
    r"replace with the|// *TODO|the actual (?:selector|name|value) from",
    re.IGNORECASE,
)


def _has_hedge(code: str) -> bool:
    """True when the model admitted it was guessing — e.g. a `// Placeholder selector`
    or `in a real test you would need the actual selector` hedge. Such code ships a
    guaranteed-failing guess, so we reject it and let the cascade try another model
    rather than hand the user a test that cannot pass."""
    return bool(_HEDGE_RE.search(code))


def _log_reject(provider: str, model: str, reason: str, head: str = "") -> None:
    """Surface an IN-BAND authoring failure in the Activity Log.

    The provider returned HTTP 200, so the plain call log records it as "ok" — but
    the output was unusable (prose, a hedge, or code that failed validation) and we
    fell through to the next model. Without this row the dashboard shows a green
    "ok" and the real reason lives only in the Space's throwaway text buffer, which
    is exactly the "200-with-a-broken-payload" gap. We log a separate content-free
    row (status=error, http=422) so the operator sees WHY authoring fell through.
    Content is generated test code only, never a user prompt or document; truncated.
    Fire-and-forget — never raises, no-ops when the log token is unset."""
    try:
        _log_outcome(provider, model, "error", http_status=422,
                     error_code="output_rejected",
                     error_message=reason + (f" | head={head[:160]}" if head else ""),
                     operation="qa-author")
    except Exception:
        pass


def _postprocess(code: str, ctx: str) -> str:
    """The deterministic reliability net (more reliable than prompt-nudging). Always
    drop hard sleeps, append `.first()` to raw href locators, and remove wildcard/
    placeholder-name steps; when we have live page context, also href-ground link
    locators and force exact/.first() on provably-ambiguous names. Order matters:
    ground links while names are still exact, shorten long names, disambiguate, then
    the always-on syntactic nets last."""
    # Repair a `{ name. 'x' }` mis-punctuation first, so the name-based transforms
    # below (which all require a well-formed `name:`) still see and fix the locator.
    code = sanitize_option_punctuation(code)
    code = strip_hard_waits(code)
    if ctx:
        code = href_link_locators(code, ctx)
    code = shorten_long_names(code)
    if ctx:
        code = disambiguate_locators(code, ctx)
    code = first_on_href_locators(code)
    code = strip_junk_locators(code)
    if ctx:
        # Repair a MISREAD getByRole name (e.g. 'PDF for print (AA)' -> the real
        # 'A4') to the unique close match in the captured context — BEFORE the gate,
        # so a merely-mistyped interaction is fixed instead of dropped, and a mistyped
        # assertion targets the real element instead of failing.
        code = repair_ungrounded_names(code, ctx)
        # Last: drop any test that INTERACTS with a non-interactive / absent element
        # (grounded a real string but invented its role). Runs last so href/exact
        # rewrites have already resolved link locators the gate would otherwise judge.
        code = drop_ungrounded_actions(code, ctx)
    return code


def generate_test(instructions: str, base_url: str, test_name: str,
                  page_context: str = "", provider: str | None = None,
                  model: str | None = None, user_key: str | None = None,
                  owner_token: str | None = None) -> tuple[str, str] | None:
    user_parts = [f"Scenario to test:\n{instructions.strip()}"]
    if base_url.strip():
        user_parts.append(f"\nBase URL of the site under test: {base_url.strip()}")
    if test_name.strip():
        user_parts.append(f"\nUse this as the describe-block title: {test_name.strip()}")

    # When Discover supplies real page context, feed it and switch to the grounded
    # prompt so locators and URLs come from the page, not from the model's guess.
    ctx = (page_context or "").strip()[: config.MAX_PAGE_CONTEXT]
    system = AUTHOR_SYSTEM
    if ctx:
        user_parts.append(
            "\nREAL PAGE CONTEXT (captured live from the page under test) — an "
            "ARIA snapshot and a link accessible-name -> href map. Ground every "
            "locator and URL in this; do not use anything absent from it:\n" + ctx
        )
        system = AUTHOR_SYSTEM + AUTHOR_GROUNDING
    user_msg = "\n".join(user_parts)

    candidates = select_candidates(provider, model, user_key, owner_token)
    for provider, model, key in candidates:
        if not key:
            continue
        try:
            raw = complete(
                provider, model, key,
                [{"role": "user", "content": user_msg}],
                system=system,
            )
        except Exception as exc:
            logger.warning("qa/author: %s failed: %s", provider, exc)
            continue
        code = _strip_fences(raw)
        if not _looks_like_test(code):
            logger.warning("qa/author: %s returned non-test output", provider)
            _log_reject(provider, model, "non-test output (prose/apology)", code)
            continue
        if _has_hedge(code):
            logger.warning("qa/author: %s returned hedge/placeholder code — rejecting", provider)
            _log_reject(provider, model, "hedge/placeholder code (model was guessing)", code)
            continue
        final = _postprocess(code, ctx)
        if "test(" not in final:
            # The grounded-action gate dropped every test (all interactions were
            # ungrounded). Let the next model try rather than return an empty file.
            logger.warning("qa/author: %s left no grounded test after gating", provider)
            _log_reject(provider, model, "no grounded test left after action-gating")
            continue
        if not looks_syntactically_valid(final):
            # A typo/brace slip would fail the whole spec with "No tests found" — let
            # the next provider try rather than ship code that cannot compile. Log a
            # content-free head of the rejected code so a recurring reject is diagnosable
            # (this is generated test code, never user data).
            logger.warning("qa/author: %s produced unparseable code — trying next | head=%r",
                           provider, final[:500])
            _log_reject(provider, model, "unparseable code (syntax/brace slip)", final)
            continue
        return final, provider
    logger.error("qa/author: every candidate failed (%s)",
                 ", ".join(p for p, _, _ in candidates))
    return None


@router.post("/generate", response_model=GenerateResponse)
@limiter.limit(LLM_LIMIT)
def generate(request: Request, req: GenerateRequest):
    record_call(config.FEATURE, pool=config.BUDGET_POOL, daily_cap_env=config.DAILY_CAP_ENV)
    result = generate_test(req.instructions, req.base_url, req.test_name, req.page_context,
                           provider=req.provider, model=req.model,
                           user_key=req.user_key, owner_token=req.owner_token)
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


def suggest_assertions(code: str, provider: str | None = None, model: str | None = None,
                       user_key: str | None = None, owner_token: str | None = None
                       ) -> tuple[list[AssertSuggestion], str] | None:
    user_msg = f"Playwright test to review:\n{code.strip()}"
    for provider, model, key in select_candidates(provider, model, user_key, owner_token):
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
    result = suggest_assertions(req.code, provider=req.provider, model=req.model,
                                user_key=req.user_key, owner_token=req.owner_token)
    if result is None:
        return AssertResponse(suggestions=[], provider=None)
    suggestions, provider = result
    return AssertResponse(suggestions=suggestions, provider=provider)
