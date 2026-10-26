#!/usr/bin/env python3
"""Validate a whole suite in ONE GitHub Actions dispatch, not one per test.

    .venv/bin/python scripts/testops_batch_run.py [--record] [--limit N]
    .venv/bin/python scripts/testops_batch_run.py --from <correlation_id> --record

`--from` reads a dispatch that already ran instead of starting a new one, so a
result can be recorded (or re-read) without paying for the run twice.

This is the fix for the mistake recorded in testops_pilot.py: that pilot paid
~2-3 min of queue, checkout and browser install PER TEST, which is where the
bogus "40 hours for 817 cases" figure came from. MAX_RUN_CODE is 60000 and a
spec is 1-2 KB, so ~40 specs fit in a single dispatch, and the runner already
returns per-test results (title / status / duration / error).

It takes the specs already on disk in tests/testwright-suite/, merges them,
dispatches once, and maps each per-test result back to its TC id. No LLM is
involved — authoring already happened. Running a built suite costs $0.

Merging rules, which the authored specs all happen to satisfy:
  - one `import { test, expect } from '@playwright/test';` kept at the top
  - each file's remaining body wrapped in a bare `{ }` block, so the
    module-scope `const BASE_URL` in six of them stops colliding
  - the inner test() title is prefixed with the TC id, because Playwright's
    JSON report gives the TEST title, not the describe title, and the id is
    the only thing that links a result back to a row
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import time

import httpx

import testops_registry as reg
from testops_sync import credentials, headers

SPACE = "https://wram1708-ml-unified.hf.space"
SUITE = os.path.join(reg.REPO, "tests", "testwright-suite")
MAX_RUN_CODE = 60000          # mirrors routers/qa/config.py
MAX_PER_DISPATCH = 40
POLL_EVERY, POLL_MAX = 10, 90
RUNNING = {"queued", "running", "in_progress", "pending", "starting", None}

IMPORT = "import { test, expect } from '@playwright/test';"
TC_FROM_FILE = re.compile(r"^(tc-[a-z0-9]+-\d+)-", re.I)
TC_IN_TITLE = re.compile(r"\[(TC-[A-Z0-9]+-\d+)\]")
TEST_CALL = re.compile(r"(\btest\s*\(\s*)(['\"])(.*?)(\2)", re.S)

CLIENT = httpx.Client(timeout=120)


def tc_of(path: str) -> str | None:
    m = TC_FROM_FILE.match(os.path.basename(path))
    return m.group(1).upper() if m else None


def one_block(path: str, tc: str) -> str:
    """One spec file as a self-contained block, its test titles tagged with the id."""
    body = open(path, encoding="utf-8").read()
    body = "\n".join(l for l in body.splitlines() if "@playwright/test" not in l)
    # Tag every test() title. A spec with two tests gets two tagged results, and
    # both map back to the same case — which is correct: the case is only usable
    # if all of its tests pass.
    body = TEST_CALL.sub(lambda m: f"{m.group(1)}{m.group(2)}[{tc}] {m.group(3)}{m.group(4)}", body)
    return "{\n" + body.strip() + "\n}\n"


def merge(paths: list[str]) -> tuple[str, list[str]]:
    blocks, ids = [IMPORT + "\n"], []
    for p in paths:
        tc = tc_of(p)
        if not tc:
            print(f"  skip (no TC id in filename): {os.path.basename(p)}")
            continue
        blocks.append(one_block(p, tc))
        ids.append(tc)
    return "\n".join(blocks), ids


def dispatch(code: str, name: str) -> tuple[str | None, dict]:
    r = CLIENT.post(f"{SPACE}/qa/run/execute",
                    json={"code": code, "base_url": "https://ml-portfolio-rho.vercel.app",
                          "test_name": name, "runs": 1, "authorized": False})
    try:
        acc = r.json()
    except ValueError:
        return None, {"status": "REJECTED", "detail": r.text[:300]}
    cid = acc.get("correlation_id")
    if not cid:
        return None, {"status": "REJECTED", "detail": str(acc)[:300]}
    for _ in range(POLL_MAX):
        time.sleep(POLL_EVERY)
        try:
            st = CLIENT.get(f"{SPACE}/qa/run/status/{cid}").json()
        except (httpx.HTTPError, ValueError):
            continue
        if st.get("status") not in RUNNING:
            return cid, st
    return cid, {"status": "timeout"}


def verdicts(tests: list[dict], ids: list[str]) -> dict[str, dict]:
    """Per-TC verdict. A case with several tests passes only if all of them do."""
    out: dict[str, dict] = {}
    for t in tests:
        m = TC_IN_TITLE.search(t.get("title") or "")
        if not m:
            continue
        tc = m.group(1)
        ok = t.get("status") == "passed"
        cur = out.setdefault(tc, {"verdict": "PASS", "ms": 0, "reason": ""})
        cur["ms"] += t.get("duration") or 0
        if not ok:
            cur["verdict"] = "STILL_RED"
            cur["reason"] = (t.get("error") or t.get("status") or "")[:300]
    for tc in ids:
        out.setdefault(tc, {"verdict": "NOT_IN_REPORT", "ms": 0,
                            "reason": "the merged run produced no result for this test"})
    return out


def record(url: str, key: str, tc: str, v: dict, batch: str) -> None:
    CLIENT.patch(f"{url}/rest/v1/testops_cases", params={"tc_id": f"eq.{tc}"},
                 headers=headers(key),
                 content=json.dumps({"last_verdict": v["verdict"], "last_run_at": "now()"}))
    payload = {"verdict": v["verdict"], "suite": "browser-batch", "batch": batch,
               "duration_ms": v["ms"]}
    if v["reason"]:
        payload["reason"] = v["reason"]
    CLIENT.post(f"{url}/rest/v1/testops_events", headers=headers(key),
                content=json.dumps({"kind": "run_verdict", "tc_id": tc,
                                    "actor": "browser-batch", "payload": payload}))


def main() -> None:
    do_record = "--record" in sys.argv
    limit = MAX_PER_DISPATCH
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    prior = None
    if "--from" in sys.argv:
        prior = sys.argv[sys.argv.index("--from") + 1]

    paths = sorted(glob.glob(os.path.join(SUITE, "*.spec.ts")))[:limit]
    if not paths:
        sys.exit(f"no specs in {SUITE}")
    code, ids = merge(paths)
    print(f"merged {len(ids)} specs -> {len(code):,} chars "
          f"({len(code) / MAX_RUN_CODE:.0%} of the {MAX_RUN_CODE:,} limit)")
    if len(code) > MAX_RUN_CODE:
        sys.exit("merged suite exceeds MAX_RUN_CODE — lower --limit")

    t0 = time.time()
    if prior:
        cid, st = prior, CLIENT.get(f"{SPACE}/qa/run/status/{prior}").json()
        elapsed = 0.0
        print(f"re-reading dispatch {cid} -> {st.get('status')}")
    else:
        cid, st = dispatch(code, f"testops-batch-{len(ids)}")
        elapsed = (time.time() - t0) / 60
        print(f"dispatch {cid} -> {st.get('status')} in {elapsed:.1f} min")
    if st.get("status") != "completed":
        sys.exit(f"run did not complete: {json.dumps(st)[:400]}")

    res = verdicts(st.get("tests") or [], ids)
    for tc in ids:
        v = res[tc]
        print(f"  {tc:14} {v['verdict']:14} {v['ms'] / 1000:6.1f}s {v['reason'][:60]}")

    good = sum(1 for v in res.values() if v["verdict"] == "PASS")
    print(f"\n{good}/{len(ids)} pass — ONE dispatch, {elapsed:.1f} min wall-clock")
    print(f"at this density, 817 cases = {-(-817 // MAX_PER_DISPATCH)} dispatches")

    if do_record:
        db_url, db_key = credentials()
        batch = cid or "unknown"
        for tc in ids:
            record(db_url, db_key, tc, res[tc], batch)
        print(f"recorded {len(ids)} verdicts to the registry")


if __name__ == "__main__":
    main()
