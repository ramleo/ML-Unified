#!/usr/bin/env python3
"""Run a pytest suite and report each result back to the TestOps registry.

    .venv/bin/python scripts/testops_report_pytest.py tests/testcases/

Links a documented case to the test that exercises it by reading the test's own
name: `test_tc_p12_081_no_ultralytics…` -> TC-P12-081, including parametrised
ids like `test_file_length_gate[tc_p13_069]`.

Coverage rule, deliberately strict: `spec_path` is set only for a test that
actually EXECUTED. A skipped test is linked and its verdict recorded, but it does
not count as automated — a retired case with a skip marker is not coverage, and
counting it would make the headline number flatter.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import httpx

from testops_sync import credentials, headers

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# test_tc_<part>_<num>_rest   |   ...[tc_<part>_<num>...]
# NOT \btc — "_" is a word character, so \b never matches inside "test_tc_p9_083".
NAME_RE = re.compile(r"(?:^|[^a-z0-9])tc[_-]([a-z0-9]+(?:[_-][ab])?)[_-](\d{1,4})(?![0-9])", re.I)
LINE_RE = re.compile(r"^(?P<file>\S+?\.py)::(?P<node>\S+)\s+(?P<outcome>PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)")

OUTCOME_VERDICT = {
    "PASSED": "PASS", "FAILED": "STILL_RED", "ERROR": "STILL_RED",
    "SKIPPED": "SKIPPED", "XFAIL": "KNOWN_FAIL", "XPASS": "PASS",
}


def tc_id_from(node: str) -> str | None:
    """TC id encoded in a test's function name or its parametrised id."""
    m = NAME_RE.search(node)
    if not m:
        return None
    part = m.group(1).upper().replace("_", "-")
    return f"TC-{part}-{int(m.group(2)):03d}"


def run_pytest(target: str) -> list[tuple[str, str, str]]:
    """-> [(file, node, outcome)] for every collected test."""
    r = subprocess.run(
        [sys.executable, "-m", "pytest", target, "-v", "--tb=no", "-p", "no:cacheprovider"],
        cwd=REPO, capture_output=True, text=True)
    out: list[tuple[str, str, str]] = []
    for line in (r.stdout + r.stderr).splitlines():
        m = LINE_RE.match(line.strip())
        if m:
            out.append((m.group("file"), m.group("node"), m.group("outcome")))
    if not out:
        sys.exit(f"pytest produced no parseable results:\n{r.stdout[-1500:]}")
    return out


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "tests/testcases/"
    results = run_pytest(target)
    print(f"{len(results)} tests collected from {target}")

    linked: dict[str, dict] = {}
    unlinked = 0
    for path, node, outcome in results:
        tc = tc_id_from(node)
        if not tc:
            unlinked += 1
            continue
        verdict = OUTCOME_VERDICT.get(outcome, outcome)
        executed = outcome in ("PASSED", "FAILED", "ERROR", "XPASS")
        # One case can have several tests (a parametrised gate). A failure of any
        # of them is the case's verdict — never let a green sibling mask a red.
        prev = linked.get(tc)
        if prev and prev["_verdict_rank"] <= _rank(verdict):
            continue
        linked[tc] = {
            "tc_id": tc,
            "spec_path": path if executed else None,
            "last_verdict": verdict,
            "last_run_at": "now()",
            "_verdict_rank": _rank(verdict),
            "_node": node,
        }

    print(f"{len(linked)} documented cases linked, {unlinked} test(s) carry no TC id")
    url, key = credentials()
    rows, events = [], []
    for tc, d in sorted(linked.items()):
        node = d.pop("_node")
        d.pop("_verdict_rank")
        rows.append(d)
        events.append({"kind": "run_verdict", "tc_id": tc, "actor": "pytest",
                       "payload": {"verdict": d["last_verdict"], "node": node,
                                   "suite": target}})

    # PATCH, not upsert: these cases were created by testops_sync.py and a
    # POST upsert would build a full INSERT, tripping NOT NULL on source_file.
    missing = []
    with httpx.Client(timeout=60) as client:
        for d in rows:
            tc = d.pop("tc_id")
            r = client.patch(f"{url}/rest/v1/testops_cases",
                             params={"tc_id": f"eq.{tc}"},
                             headers={**headers(key), "Prefer": "return=representation"},
                             content=json.dumps(d))
            if r.status_code >= 400:
                sys.exit(f"update of {tc} failed ({r.status_code}): {r.text[:300]}")
            if r.json() == []:
                missing.append(tc)   # a test names a case that is not in the registry
        r = client.post(f"{url}/rest/v1/testops_events", headers=headers(key),
                        content=json.dumps(events))
        if r.status_code >= 400:
            sys.exit(f"event insert failed ({r.status_code}): {r.text[:400]}")
    if missing:
        print(f"WARNING: {len(missing)} test(s) name a case absent from the registry: "
              f"{', '.join(missing[:8])}")

    from collections import Counter
    tally = Counter(d["last_verdict"] for d in rows)
    print("recorded:", dict(tally))
    automated = sum(1 for d in rows if d["spec_path"])
    print(f"{automated} case(s) now count as automated (skips deliberately excluded)")


def _rank(verdict: str) -> int:
    """Lower is worse — a case's verdict is its worst test's verdict."""
    return {"STILL_RED": 0, "KNOWN_FAIL": 1, "SKIPPED": 2, "PASS": 3}.get(verdict, 2)


if __name__ == "__main__":
    main()
