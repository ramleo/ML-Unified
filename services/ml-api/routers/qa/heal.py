"""
Testwright (QA Automation) — Heal (self-healing locators).

Given a failed run, re-resolve the broken locator(s) from the page's ARIA
snapshot at the moment of failure and return a corrected test. This is locator
repair only — a genuine bug (a correctly-failing assertion) will still fail on
the re-run, which is the honest outcome.
"""

import logging
import re

from fastapi import APIRouter, Request

from routers.qa import config, github_runner
from routers.qa.deps import complete, resolve_key, limiter, LLM_LIMIT
from routers.qa.prompts import HEAL_SYSTEM
from routers.qa.author import _strip_fences, _looks_like_test
from routers.qa.models import HealGroupRequest, HealGroupResponse, HealGroup

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/heal")

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_LOCATOR_RE = re.compile(r"(getBy\w+\([^\n)]*\)|locator\([^\n)]*\))")


def _signature(error: str) -> tuple[str, str]:
    """A stable key + human label for a failure, so tests that broke on the same
    thing group together. Prefers the failing locator; falls back to the first
    meaningful error line."""
    e = _ANSI.sub("", error or "")
    m = _LOCATOR_RE.search(e)
    if m:
        sig = re.sub(r"\s+", " ", m.group(1)).strip()
        return sig, sig
    for line in e.splitlines():
        s = line.strip()
        if s and not s.startswith(("Call log", "- ", "at ", "expect(")):
            return s[:120], s[:120]
    return "unknown", "Unknown failure"


@router.post("/group", response_model=HealGroupResponse)
@limiter.limit(LLM_LIMIT)
def group(request: Request, req: HealGroupRequest):
    """Group failed runs by root cause — '1 issue, N tests'."""
    buckets: dict[str, dict] = {}
    order: list[str] = []
    for cid in req.correlation_ids[:50]:
        error = ""
        try:
            run = github_runner.find_run(cid)
            ctx = github_runner.fetch_failure_context(run.get("id")) if run else None
            error = (ctx or {}).get("error", "") or ""
        except Exception as exc:
            logger.warning("qa/heal group: context fetch failed for %s: %s", cid, exc)
        sig, cause = _signature(error)
        if sig not in buckets:
            buckets[sig] = {"signature": sig, "cause": cause, "correlation_ids": []}
            order.append(sig)
        buckets[sig]["correlation_ids"].append(cid)
    return HealGroupResponse(groups=[HealGroup(**buckets[s]) for s in order])


def heal_test(code: str, error: str, snapshot: str) -> tuple[str, str] | None:
    """Return (healed_code, provider) or None if no provider produced a usable
    corrected test."""
    error = _ANSI.sub("", error or "")[: config.MAX_ERROR_CHARS]
    snapshot = (snapshot or "")[: config.MAX_SNAPSHOT_CHARS]
    user = (
        f"Original test:\n{code.strip()}\n\n"
        f"Failure error:\n{error or '(none captured)'}\n\n"
        f"Accessibility snapshot of the page at failure:\n{snapshot or '(none captured)'}"
    )
    for provider, model in config.GEN_CANDIDATES:
        key = resolve_key(provider)
        if not key:
            continue
        try:
            raw = complete(provider, model, key,
                           [{"role": "user", "content": user}], system=HEAL_SYSTEM)
        except Exception as exc:
            logger.warning("qa/heal: %s failed: %s", provider, exc)
            continue
        fixed = _strip_fences(raw)
        if _looks_like_test(fixed):
            return fixed, provider
        logger.warning("qa/heal: %s returned non-test output", provider)
    logger.error("qa/heal: every candidate failed")
    return None
