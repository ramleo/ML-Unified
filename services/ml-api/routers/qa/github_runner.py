"""
Testwright (QA Automation) — GitHub Actions execution backend.

The Run stage does not run a browser in this Space. It dispatches the isolated
`qa-run` workflow in the public `ramleo/ml-qa-runner` repo (a fresh, ephemeral
GitHub-hosted runner per test), then reads the run's pass/fail conclusion and
downloads its artifacts through GitHub's authenticated API.

The GitHub token lives only here, read from the GH_QA_TOKEN env/secret — it never
reaches the browser and is never logged. This module is the one place that talks
to GitHub; swapping execution backends later means replacing just this file.
"""

import base64
import io
import json
import logging
import os
import zipfile

import httpx

from routers.qa import config

logger = logging.getLogger(__name__)

GH_API = "https://api.github.com"


def _headers() -> dict:
    token = os.environ.get(config.RUN_TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(f"{config.RUN_TOKEN_ENV} is not configured")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _runs_base() -> str:
    return f"{GH_API}/repos/{config.RUN_OWNER}/{config.RUN_REPO}"


def dispatch(code: str, base_url: str, test_name: str, correlation_id: str) -> None:
    """Fire the workflow. GitHub returns 204 and NO run id, so the run is found
    afterwards by its correlation id (embedded in run-name)."""
    url = f"{_runs_base()}/actions/workflows/{config.RUN_WORKFLOW_FILE}/dispatches"
    payload = {
        "ref": config.RUN_REF,
        "inputs": {
            "code": code,
            "base_url": base_url or "",
            "test_name": test_name or "",
            "correlation_id": correlation_id,
        },
    }
    with httpx.Client(timeout=20) as client:
        r = client.post(url, headers=_headers(), json=payload)
        r.raise_for_status()


def find_run(correlation_id: str) -> dict | None:
    """Locate the dispatched run by its correlation id (carried in the run name /
    display title). Returns the raw run object or None if not materialised yet."""
    url = (
        f"{_runs_base()}/actions/workflows/{config.RUN_WORKFLOW_FILE}/runs"
        "?event=workflow_dispatch&per_page=40"
    )
    with httpx.Client(timeout=20) as client:
        r = client.get(url, headers=_headers())
        r.raise_for_status()
        for run in r.json().get("workflow_runs", []):
            hay = f"{run.get('name', '')} {run.get('display_title', '')}"
            if correlation_id in hay:
                return run
    return None


def _download_zip(archive_url: str) -> bytes | None:
    """Follow GitHub's artifact redirect by hand so the Authorization header is
    not forwarded to the (signed) storage URL."""
    with httpx.Client(timeout=60) as client:
        r = client.get(archive_url, headers=_headers(), follow_redirects=False)
        if r.status_code in (301, 302, 307, 308):
            loc = r.headers.get("location")
            if not loc:
                return None
            r2 = client.get(loc)  # no auth header — signed URL
            r2.raise_for_status()
            return r2.content
        if r.status_code == 200:
            return r.content
        r.raise_for_status()
    return None


def fetch_artifacts(run_id: int) -> dict | None:
    """Download the run's artifact zip and pull out the results summary and the
    first (failure) screenshot as base64."""
    url = f"{_runs_base()}/actions/runs/{run_id}/artifacts"
    with httpx.Client(timeout=20) as client:
        r = client.get(url, headers=_headers())
        r.raise_for_status()
        arts = r.json().get("artifacts", [])
    if not arts:
        return None
    art = next((a for a in arts if a.get("name") == "qa-artifacts"), arts[0])
    zip_bytes = _download_zip(art["archive_download_url"])
    if not zip_bytes:
        return None
    return _parse_zip(zip_bytes)


def _parse_zip(zip_bytes: bytes) -> dict:
    out: dict = {"summary": None, "screenshotBase64": None}
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception as exc:
        logger.warning("qa/run: bad artifact zip: %s", exc)
        return out
    for name in zf.namelist():
        if name.endswith("results.json"):
            try:
                stats = json.loads(zf.read(name)).get("stats", {})
                out["summary"] = {
                    "expected": stats.get("expected", 0),
                    "unexpected": stats.get("unexpected", 0),
                    "flaky": stats.get("flaky", 0),
                    "skipped": stats.get("skipped", 0),
                }
            except Exception:
                pass
            break
    for name in zf.namelist():
        if name.endswith(".png"):
            data = zf.read(name)
            if len(data) <= config.MAX_SCREENSHOT_BYTES:
                out["screenshotBase64"] = base64.b64encode(data).decode()
            break
    return out
