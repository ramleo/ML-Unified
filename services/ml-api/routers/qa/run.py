"""
Testwright (QA Automation) — Run stage.

POST /qa/run/execute        — dispatch a Playwright test to the isolated GitHub
                              Actions runner; returns a correlation id.
GET  /qa/run/status/{id}    — poll the run: pending -> queued/in_progress ->
                              completed (with pass/fail, summary, screenshot).

Execution happens on ephemeral GitHub runners (see github_runner.py), never in
this Space.
"""

import logging
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request

from routers.qa import config, github_runner
from routers.qa.deps import record_call, limiter, LLM_LIMIT
from routers.qa.models import RunRequest, RunAccepted, RunStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/run")


def _assert_allowed(base_url: str) -> None:
    """Own-site allowlist (SSRF guard). base_url is optional; when given, its
    host must be on the allowlist."""
    if not base_url.strip():
        return
    host = (urlparse(base_url.strip()).hostname or "").lower()
    if host not in config.RUN_ALLOWED_HOSTS:
        raise HTTPException(
            status_code=403,
            detail=f'Base URL host "{host}" is not allowed. Testwright runs against our own site only.',
        )


@router.post("/execute", response_model=RunAccepted)
@limiter.limit(LLM_LIMIT)
def execute(request: Request, req: RunRequest):
    _assert_allowed(req.base_url)
    record_call(config.RUN_FEATURE, pool=config.RUN_BUDGET_POOL, daily_cap_env=config.RUN_DAILY_CAP_ENV)
    correlation_id = uuid.uuid4().hex
    try:
        github_runner.dispatch(req.code, req.base_url, req.test_name, correlation_id)
    except Exception as exc:
        logger.error("qa/run: dispatch failed: %s", exc)
        raise HTTPException(status_code=502, detail="Could not start the test run.")
    return RunAccepted(correlation_id=correlation_id, status="queued")


@router.get("/status/{correlation_id}", response_model=RunStatus)
def status(correlation_id: str):
    try:
        run = github_runner.find_run(correlation_id)
    except Exception as exc:
        logger.error("qa/run: status lookup failed: %s", exc)
        return RunStatus(status="error", detail="Could not read run status.")

    if not run:
        # Dispatched but the run has not appeared in the API yet.
        return RunStatus(status="pending")

    gh_status = run.get("status") or "pending"
    run_url = run.get("html_url")
    if gh_status != "completed":
        return RunStatus(status=gh_status, run_url=run_url)

    # The workflow always ends "success" (a failing TEST must not fail the run,
    # or GitHub emails the owner on every failing user test). So pass/fail is
    # read from results.json, not from the run conclusion. A missing results.json
    # means the run never produced results — a real execution/infra error.
    conclusion = run.get("conclusion")
    result = RunStatus(status="completed", conclusion=conclusion, run_url=run_url)
    try:
        art = github_runner.fetch_artifacts(run.get("id"))
    except Exception as exc:
        logger.warning("qa/run: artifact fetch failed: %s", exc)
        art = None

    summary = art.get("summary") if art else None
    if not summary:
        result.status = "error"
        result.detail = "The run produced no results (execution error)."
        return result

    ran = (summary.get("expected", 0) + summary.get("unexpected", 0) + summary.get("flaky", 0)) > 0
    if not ran:
        result.status = "error"
        result.detail = "No tests ran — check the test defines a test()."
        return result

    result.passed = summary.get("unexpected", 0) == 0
    result.summary = summary
    result.screenshot_base64 = art.get("screenshotBase64")
    return result
