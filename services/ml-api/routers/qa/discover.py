"""
Testwright (QA Automation) — Discover stage.

Point at an own-site URL: an "explore" run on the isolated runner renders the
page and dumps its ARIA snapshot; the LLM then proposes candidate test cases
from that snapshot. Reuses the qa-run workflow (the explore spec writes
aria.txt, which the workflow uploads).
"""

import json
import logging
import re
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request

from routers.qa import config, github_runner
from routers.qa.deps import complete, resolve_key, record_call, limiter, LLM_LIMIT
from routers.qa.prompts import DISCOVER_SYSTEM
from routers.qa.models import DiscoverStart, DiscoverStatus, RunAccepted

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discover")


def _assert_allowed(url: str) -> None:
    host = (urlparse(url.strip()).hostname or "").lower()
    if host not in config.RUN_ALLOWED_HOSTS:
        raise HTTPException(
            status_code=403,
            detail=f'URL host "{host}" is not allowed. Discover runs against our own site only.',
        )


def build_explore_spec(url: str) -> str:
    """A Playwright test that navigates the URL and writes the page's ARIA
    snapshot to aria.txt (uploaded by the workflow)."""
    safe = url.replace("\\", "\\\\").replace("'", "\\'")
    return (
        "import { test } from '@playwright/test';\n"
        "import fs from 'fs';\n\n"
        "test('explore', async ({ page }) => {\n"
        f"  await page.goto('{safe}', {{ waitUntil: 'domcontentloaded' }});\n"
        "  await page.waitForTimeout(1500);\n"
        "  const snapshot = await page.locator('body').ariaSnapshot();\n"
        "  fs.writeFileSync('aria.txt', snapshot);\n"
        "});\n"
    )


def _strip_fences(raw: str) -> str:
    if not raw:
        return ""
    fence = re.search(r"```(?:json)?\s*\n(.*?)```", raw, re.DOTALL)
    return (fence.group(1) if fence else raw).strip()


def propose_tests(snapshot: str) -> list[dict]:
    """Ask the LLM for candidate test cases from the ARIA snapshot. Returns a
    list of {title, steps}; empty on failure."""
    snap = (snapshot or "")[: config.MAX_SNAPSHOT_CHARS]
    if not snap.strip():
        return []
    user = f"Accessibility snapshot of the page:\n{snap}"
    for provider, model in config.GEN_CANDIDATES:
        key = resolve_key(provider)
        if not key:
            continue
        try:
            raw = complete(provider, model, key,
                           [{"role": "user", "content": user}], system=DISCOVER_SYSTEM)
        except Exception as exc:
            logger.warning("qa/discover: %s failed: %s", provider, exc)
            continue
        parsed = _parse_proposals(_strip_fences(raw))
        if parsed:
            return parsed
        logger.warning("qa/discover: %s returned unparseable proposals", provider)
    return []


def _parse_proposals(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data[: config.MAX_PROPOSALS]:
        if isinstance(item, dict) and item.get("title") and item.get("steps"):
            out.append({
                "title": str(item["title"])[:160],
                "steps": str(item["steps"])[:800],
            })
    return out


@router.post("/start", response_model=RunAccepted)
@limiter.limit(LLM_LIMIT)
def start(request: Request, req: DiscoverStart):
    """Dispatch an explore run that renders the URL and captures its snapshot."""
    _assert_allowed(req.url)
    record_call(config.DISCOVER_FEATURE, pool=config.DISCOVER_BUDGET_POOL,
                daily_cap_env=config.DISCOVER_DAILY_CAP_ENV)
    correlation_id = uuid.uuid4().hex
    spec = build_explore_spec(req.url.strip())
    try:
        github_runner.dispatch(spec, req.url.strip(), "explore", correlation_id)
    except Exception as exc:
        logger.error("qa/discover: dispatch failed: %s", exc)
        raise HTTPException(status_code=502, detail="Could not start discovery.")
    return RunAccepted(correlation_id=correlation_id, status="queued")


@router.get("/status/{correlation_id}", response_model=DiscoverStatus)
def status(correlation_id: str):
    try:
        run = github_runner.find_run(correlation_id)
    except Exception as exc:
        logger.error("qa/discover: status lookup failed: %s", exc)
        return DiscoverStatus(status="error", detail="Could not read discovery status.")
    if not run:
        return DiscoverStatus(status="pending", correlation_id=correlation_id)

    gh_status = run.get("status") or "pending"
    run_url = run.get("html_url")
    if gh_status != "completed":
        return DiscoverStatus(status=gh_status, correlation_id=correlation_id, run_url=run_url)

    snapshot = None
    try:
        snapshot = github_runner.fetch_text_artifact(run.get("id"), "aria.txt")
    except Exception as exc:
        logger.warning("qa/discover: snapshot fetch failed: %s", exc)
    if not snapshot:
        return DiscoverStatus(status="error", correlation_id=correlation_id, run_url=run_url,
                              detail="Could not capture the page. Check the URL is reachable.")
    proposals = propose_tests(snapshot)
    if not proposals:
        return DiscoverStatus(status="error", correlation_id=correlation_id, run_url=run_url,
                              detail="No test cases could be proposed from this page.")
    return DiscoverStatus(status="completed", correlation_id=correlation_id,
                          run_url=run_url, proposals=proposals)
