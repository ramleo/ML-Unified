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


def _download_artifact_zip(run_id: int) -> bytes | None:
    """List the run's artifacts and download the qa-artifacts zip."""
    url = f"{_runs_base()}/actions/runs/{run_id}/artifacts"
    with httpx.Client(timeout=20) as client:
        r = client.get(url, headers=_headers())
        r.raise_for_status()
        arts = r.json().get("artifacts", [])
    if not arts:
        return None
    art = next((a for a in arts if a.get("name") == "qa-artifacts"), arts[0])
    return _download_zip(art["archive_download_url"])


def fetch_artifacts(run_id: int) -> dict | None:
    """Download the run's artifact zip and pull out the summary, step timeline,
    failure screenshot, and which heavy artifacts (video/trace) exist."""
    zip_bytes = _download_artifact_zip(run_id)
    if not zip_bytes:
        return None
    return _parse_zip(zip_bytes)


# Playwright JSON-reporter step categories worth showing as a timeline.
_TIMELINE_CATS = {"pw:api", "expect", "test.step"}
_MAX_STEPS = 60


def _collect_steps(steps: list, out: list) -> None:
    for st in steps or []:
        if len(out) >= _MAX_STEPS:
            return
        if st.get("category") in _TIMELINE_CATS:
            out.append({
                "title": (st.get("title") or "")[:200],
                "category": st.get("category"),
                "duration": st.get("duration", 0),
                "ok": "error" not in st,
            })
        _collect_steps(st.get("steps", []), out)


def _steps_from_results(data: dict) -> list:
    steps: list = []

    def walk(suite: dict) -> None:
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                for res in test.get("results", []):
                    _collect_steps(res.get("steps", []), steps)
        for child in suite.get("suites", []):
            walk(child)

    for suite in data.get("suites", []):
        walk(suite)
    return steps[:_MAX_STEPS]


def _parse_zip(zip_bytes: bytes) -> dict:
    out: dict = {"summary": None, "screenshotBase64": None, "steps": [],
                 "has_video": False, "has_trace": False}
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception as exc:
        logger.warning("qa/run: bad artifact zip: %s", exc)
        return out
    names = zf.namelist()
    out["has_video"] = any(n.endswith(".webm") for n in names)
    out["has_trace"] = any(n.endswith("trace.zip") for n in names)
    for name in names:
        if name.endswith("results.json"):
            try:
                data = json.loads(zf.read(name))
                stats = data.get("stats", {})
                out["summary"] = {
                    "expected": stats.get("expected", 0),
                    "unexpected": stats.get("unexpected", 0),
                    "flaky": stats.get("flaky", 0),
                    "skipped": stats.get("skipped", 0),
                }
                out["steps"] = _steps_from_results(data)
            except Exception:
                pass
            break
    for name in names:
        if name.endswith(".png"):
            data = zf.read(name)
            if len(data) <= config.MAX_SCREENSHOT_BYTES:
                out["screenshotBase64"] = base64.b64encode(data).decode()
            break
    return out


# kind -> (filename suffix, content type, inline?)
ARTIFACT_KINDS = {
    "video": (".webm", "video/webm", True),
    "trace": ("trace.zip", "application/zip", False),
}


def fetch_artifact_file(run_id: int, kind: str) -> tuple[bytes, str, bool] | None:
    """Extract one heavy artifact (video or trace) from the run's zip.
    Returns (bytes, content_type, inline) or None."""
    spec = ARTIFACT_KINDS.get(kind)
    if not spec:
        return None
    suffix, ctype, inline = spec
    zip_bytes = _download_artifact_zip(run_id)
    if not zip_bytes:
        return None
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception:
        return None
    member = next((n for n in zf.namelist() if n.endswith(suffix)), None)
    if not member:
        return None
    return zf.read(member), ctype, inline
