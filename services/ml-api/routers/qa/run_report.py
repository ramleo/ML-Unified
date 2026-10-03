"""
Testwright (QA Automation) — run report parsing.

Pure parsing of a completed run's artifact zip (Playwright's results.json +
steps.json + screenshot/video/trace) into the plain dicts the Run status serves.
Kept separate from github_runner.py (which owns the GitHub API calls) so each file
stays small and the report shape has one home. No network here — only bytes in,
dicts out.
"""

import base64
import io
import json
import logging
import re
import zipfile

from routers.qa import config

logger = logging.getLogger(__name__)

MAX_STEPS = 60
MAX_TESTS = 100

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def clean_error(msg: str) -> str:
    """Strip ANSI colour codes and clip a Playwright error message for display."""
    if not msg:
        return ""
    return _ANSI_RE.sub("", msg).strip()[: config.MAX_ERROR_CHARS]


def first_error(data: dict) -> str:
    """The first failing test's error message, walking the suite tree in order."""
    def walk(suite: dict) -> str:
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                for res in test.get("results", []):
                    msg = (res.get("error") or {}).get("message")
                    if msg:
                        return msg
        for child in suite.get("suites", []):
            r = walk(child)
            if r:
                return r
        return ""

    for suite in data.get("suites", []):
        r = walk(suite)
        if r:
            return r
    return ""


def count_tests(data: dict) -> int:
    """Number of DISTINCT test cases in the report (by spec title). `--repeat-each`
    repeats one spec, so distinct titles stays 1 for a true flakiness run, while a
    multi-test file yields >1. Lets us tell a repeated single test from a suite."""
    titles: set[str] = set()

    def walk(suite: dict) -> None:
        for spec in suite.get("specs", []):
            t = spec.get("title")
            if t:
                titles.add(t)
        for child in suite.get("suites", []):
            walk(child)

    for suite in data.get("suites", []):
        walk(suite)
    return len(titles)


def read_tests(data: dict) -> list:
    """Per-TEST-CASE results from results.json: one entry per spec with its title,
    outcome, duration and (if it failed) its own error. This is what lets the UI
    show WHICH tests failed and why, instead of a single count + first error."""
    out: list = []

    def walk(suite: dict) -> None:
        for spec in suite.get("specs", []):
            dur = 0
            err = ""
            kind = ""  # the non-passing result status (failed / timedOut / interrupted)
            for test in spec.get("tests", []):
                for res in test.get("results", []):
                    dur += res.get("duration", 0) or 0
                    rs = res.get("status")
                    if rs and rs not in ("passed", "skipped") and not kind:
                        kind = rs
                    if not err:
                        msg = (res.get("error") or {}).get("message")
                        if msg:
                            err = clean_error(msg)
            status = "passed" if spec.get("ok") else (kind or "failed")
            out.append({
                "title": (spec.get("title") or "")[:200],
                "status": status,
                "duration": dur,
                "error": (err[:600] or None) if status != "passed" else None,
            })
            if len(out) >= MAX_TESTS:
                return
        for child in suite.get("suites", []):
            if len(out) >= MAX_TESTS:
                return
            walk(child)

    for suite in data.get("suites", []):
        if len(out) >= MAX_TESTS:
            break
        walk(suite)
    return out


def _read_steps(zf: "zipfile.ZipFile") -> list:
    """The step timeline, written by our custom reporter into steps.json (the
    built-in JSON reporter omits steps)."""
    name = next((n for n in zf.namelist() if n.endswith("steps.json")), None)
    if not name:
        return []
    try:
        raw = json.loads(zf.read(name))
    except Exception:
        return []
    out = []
    for st in raw[:MAX_STEPS]:
        out.append({
            "title": (st.get("title") or "")[:200],
            "category": st.get("category"),
            "duration": st.get("duration", 0),
            "ok": bool(st.get("ok", True)),
        })
    return out


def parse_zip(zip_bytes: bytes) -> dict:
    """Turn a run's artifact zip into the result dict the Run status serves."""
    out: dict = {"summary": None, "screenshotBase64": None, "steps": [], "tests": [],
                 "has_video": False, "has_trace": False, "error": "", "num_tests": 0}
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
                out["error"] = clean_error(first_error(data))
                out["num_tests"] = count_tests(data)
                out["tests"] = read_tests(data)
            except Exception:
                pass
            break
    out["steps"] = _read_steps(zf)
    for name in names:
        if name.endswith(".png"):
            data = zf.read(name)
            if len(data) <= config.MAX_SCREENSHOT_BYTES:
                out["screenshotBase64"] = base64.b64encode(data).decode()
            break
    return out
