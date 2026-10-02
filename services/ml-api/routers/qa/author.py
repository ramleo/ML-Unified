"""
Testwright (QA Automation) — Author stage.

POST /qa/author/generate — plain-English test steps -> a runnable Playwright
TypeScript test with resilient locators. Generation ONLY, no execution.
"""

import json
import logging
import re
from collections import Counter

from fastapi import APIRouter, Request

from routers.qa import config
from routers.qa.deps import complete, resolve_key, record_call, limiter, LLM_LIMIT
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


# A whole-statement hard sleep, e.g. `await page.waitForTimeout(500);`. Matched only
# as a standalone line, so an inline/embedded use is left alone (conservative).
_HARD_WAIT_LINE = re.compile(
    r"^[ \t]*(?:await\s+)?page\.waitForTimeout\s*\([^)]*\)\s*;?[ \t]*(?://.*)?$"
)


def _strip_hard_waits(code: str) -> str:
    """Remove hard-coded `page.waitForTimeout(...)` sleeps — the #1 cause of flaky
    tests. Playwright's auto-waiting and web-first assertions make fixed sleeps
    unnecessary, and a deterministic strip is more reliable than asking the model
    not to emit them (same lesson as locator disambiguation). Only whole standalone
    statements are removed; nothing else is touched."""
    lines = code.split("\n")
    kept = [ln for ln in lines if not _HARD_WAIT_LINE.match(ln)]
    return "\n".join(kept)


# Accessible names in the page context: ARIA-snapshot role lines (e.g. `link "X"`)
# carry one entry PER element (so nav+footer duplicates are counted), plus the
# link map's left-hand side (`X -> /href`).
_CTX_ROLE_NAME = re.compile(
    r'(?:link|button|heading|tab|menuitem|checkbox|option|textbox|searchbox|radio)'
    r'\s+"([^"\n]{1,120})"'
)
# A full getByRole call whose options object has ONLY a name (no `exact`/extra),
# so we can either add `exact: true` inside it or append `.first()` after it.
_GETBYROLE_NAME = re.compile(
    r"getByRole\(\s*(['\"])(\w+)\1\s*,\s*\{\s*name:\s*(['\"])(.*?)\3\s*\}\s*\)"
)


_LONG_NAME = 60
_RE_SPECIAL = re.compile(r"[.*+?^${}()|[\]\\/]")


def _shorten_long_names(code: str) -> str:
    """A `getByRole` whose `name` is a whole sentence (a card's full paragraph text)
    is brittle and usually resolves to nothing. Replace an over-long exact name with
    a short `^prefix` regex + `.first()`, which matches the same element far more
    robustly. Short, normal names are left untouched."""
    def repl(m: "re.Match") -> str:
        name = m.group(4)
        if len(name) <= _LONG_NAME:
            return m.group(0)
        prefix = ""
        for w in name.split():
            if prefix and len(prefix) + 1 + len(w) > 40:
                break
            prefix = w if not prefix else prefix + " " + w
            if len(prefix.split()) >= 5:
                break
        if not prefix:
            prefix = name[:40]
        esc = _RE_SPECIAL.sub(lambda x: "\\" + x.group(0), prefix)
        q, role = m.group(1), m.group(2)
        return f"getByRole({q}{role}{q}, {{ name: /^{esc}/i }}).first()"
    return _GETBYROLE_NAME.sub(repl, code)


def _page_name_counts(page_context: str) -> Counter:
    """How many page elements carry each accessible name (lower-cased). The ARIA
    snapshot lists every element, so true duplicates (nav + footer) are counted;
    link-map names not role-tagged are added once."""
    counts: Counter = Counter()
    for m in _CTX_ROLE_NAME.finditer(page_context):
        counts[m.group(1).lower()] += 1
    for line in page_context.splitlines():
        if " -> " in line:
            nm = line.split(" -> ", 1)[0].strip().lower()
            if nm and nm not in counts:
                counts[nm] += 1
    return counts


def _disambiguate_locators(code: str, page_context: str) -> str:
    """Playwright strict mode needs a locator to match exactly one element. A
    name-only `getByRole` can match several: by case-insensitive SUBSTRING (e.g.
    'Tools' is inside 'Browse the tools') or because the SAME name repeats (a nav
    link also in the footer). Grounded in the real page, fix both — `exact: true`
    when a unique name is being over-matched by substring, `.first()` when the
    name genuinely repeats. Already-unique locators are left untouched."""
    counts = _page_name_counts(page_context)
    if not counts:
        return code
    items = list(counts.items())

    def repl(m: "re.Match") -> str:
        x = m.group(4).lower()
        if not x:
            return m.group(0)
        equals = sum(c for n, c in items if n == x)
        contains = sum(c for n, c in items if x in n)
        if equals >= 2:
            # Same name on >1 element — exact can't disambiguate; take the first.
            return m.group(0) + ".first()"
        if contains >= 2 and equals == 1:
            # Unique name over-matched by substring — pin it exact.
            q, nq = m.group(1), m.group(3)
            return f"getByRole({q}{m.group(2)}{q}, {{ name: {nq}{m.group(4)}{nq}, exact: true }})"
        return m.group(0)

    return _GETBYROLE_NAME.sub(repl, code)


def generate_test(instructions: str, base_url: str, test_name: str,
                  page_context: str = "") -> tuple[str, str] | None:
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

    for provider, model in config.GEN_CANDIDATES:
        key = resolve_key(provider)
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
        if _looks_like_test(code):
            # Deterministic reliability net (more reliable than prompt-nudging):
            # always drop hard sleeps, and — when we have page context to ground it
            # in — force `exact: true`/`.first()` on provably-ambiguous name locators
            # so a grounded test can't fail strict mode on a name the model forgot
            # to disambiguate.
            code = _strip_hard_waits(code)
            code = _shorten_long_names(code)
            if ctx:
                code = _disambiguate_locators(code, ctx)
            return code, provider
        logger.warning("qa/author: %s returned non-test output", provider)
    logger.error("qa/author: every candidate failed (%s)",
                 ", ".join(p for p, _ in config.GEN_CANDIDATES))
    return None


@router.post("/generate", response_model=GenerateResponse)
@limiter.limit(LLM_LIMIT)
def generate(request: Request, req: GenerateRequest):
    record_call(config.FEATURE, pool=config.BUDGET_POOL, daily_cap_env=config.DAILY_CAP_ENV)
    result = generate_test(req.instructions, req.base_url, req.test_name, req.page_context)
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
