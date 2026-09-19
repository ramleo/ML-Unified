"""
Testwright (QA Automation) — Heal (self-healing locators).

Given a failed run, re-resolve the broken locator(s) from the page's ARIA
snapshot at the moment of failure and return a corrected test. This is locator
repair only — a genuine bug (a correctly-failing assertion) will still fail on
the re-run, which is the honest outcome.
"""

import logging
import re

from routers.qa import config
from routers.qa.deps import complete, resolve_key
from routers.qa.prompts import HEAL_SYSTEM
from routers.qa.author import _strip_fences, _looks_like_test

logger = logging.getLogger(__name__)

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


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
