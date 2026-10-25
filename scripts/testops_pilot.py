#!/usr/bin/env python3
"""Browser-lane pilot: take real test cases end to end and record what happens.

    .venv/bin/python scripts/testops_pilot.py [n]

For each case: author a Playwright test from the case TEXT (Groq, via the Space's
owner token), run it on the GitHub Actions runner, heal up to 3 times, and write
the verdict back to the TestOps registry.

Two arms, so the URL resolver is measured against a control rather than assumed:
  A  the case resolved to a target  -> author with that URL
  B  it did not                     -> author with the site map only
If B passes at A's rate the resolver earns nothing; if it does not, it is the
critical piece. Either answer changes what gets built next.

Pacing is set by the real ceilings: Groq free is 8,000 tokens/min and an author
call costs ~5,900, so roughly 1.4 authors/min. The Space caps LLM routes at
10/min per IP. Nothing here goes faster than that.

KNOWN LIMITATION — do not copy this shape for the full build.
This dispatches ONE GitHub Actions run per test, which is fine for 20 cases and
badly wrong for 817: each dispatch pays ~2-3 min of queue, checkout and browser
install to run a test that takes seconds, which is where the bogus "40 hours for
817 cases" figure came from.

MAX_RUN_CODE is 60000 and a spec is 1-2 KB, so ~40 tests fit in ONE dispatch, and
the runner already returns per-test results — merged suites are first class. The
full build should author per case (the only irreducible per-test cost) and then
validate in batches: ~21 dispatches for 817 tests, run concurrently, minutes not
hours. Running a finished suite involves no AI at all.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

import testops_registry as reg
from testops_sync import credentials, headers

SPACE = "https://wram1708-ml-unified.hf.space"
HEAL_CAP = 3
WORKERS = 2
AUTHORS_PER_MIN = 1.3
POLL_EVERY, POLL_MAX = 10, 36

SUITE = os.path.join(reg.REPO, "tests", "testwright-suite")
RUNNING = {"queued", "running", "in_progress", "pending", "starting", None}

SITE_MAP = (
    "SITE MAP (verified): the portfolio is https://ml-portfolio-rho.vercel.app — "
    "home '/', /handbook, /docs, /about, /changelog, /privacy, /login, /eda. Tool "
    "CATEGORY pages: /tools/computer-vision, /tools/security-trust, /tools/ml-pipeline, "
    "/tools/language-documents. There is NO bare /tools page (404); individual tools "
    "live at /tools/<slug> and on a category page render as CARDS (an <h3> title plus "
    "a <button>, not an <a href>). The ML Unified app is https://wram1708-ml-unified.hf.space "
    "with modes ?mode=ml, ?mode=eda, ?mode=vision. Nav links appear in BOTH header and "
    "footer, so use .first(). Both sites are client-rendered — wait for elements, never "
    "read raw HTML."
)
RULES = (
    "Write ONE Playwright test that asserts the expected result. page.goto() MUST use an "
    "ABSOLUTE url — the runner sets no baseURL, so '/' fails to navigate. Prefer role and "
    "text locators, use .first() where a label repeats, and wait for elements rather than "
    "sleeping. If the scenario needs a file upload or a signed-in session, do not invent "
    "one — assert only what is visible without it."
)


class Bucket:
    """Token bucket — the Groq TPM ceiling is the real limit, not the API's."""

    def __init__(self, per_min: float):
        self.gap = 60.0 / per_min
        self.next = 0.0
        self.lock = threading.Lock()

    def take(self) -> None:
        with self.lock:
            now = time.time()
            wait = max(0.0, self.next - now)
            self.next = max(now, self.next) + self.gap
        if wait:
            time.sleep(wait)


LLM = Bucket(AUTHORS_PER_MIN)
CLIENT = httpx.Client(timeout=180)


def post(path: str, payload: dict, *, llm: bool = True, tries: int = 3) -> dict:
    for i in range(tries):
        if llm:
            LLM.take()
        try:
            r = CLIENT.post(SPACE + path, json=payload)
        except httpx.HTTPError as exc:
            if i == tries - 1:
                return {"_error": str(exc)}
            time.sleep(15 * (i + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(25 * (i + 1))
            continue
        try:
            return r.json()
        except ValueError:
            return {"_error": r.text[:200]}
    return {"_error": "exhausted retries"}


def slug(c: dict) -> str:
    return re.sub(r"[^a-z0-9]+", "-", f"{c['tc_id']}-{c.get('test_name', '')}".lower())[:70].strip("-")


def instructions(c: dict, url: str | None) -> str:
    txt = (f"Test case {c['tc_id']} — {c.get('test_name', '')}\n"
           f"Steps:\n{c.get('steps', '')}\n"
           f"Expected result: {c.get('expected', '')}\n")
    if c.get("hint"):
        txt += f"Automation hint from the case author: {c['hint']}\n"
    txt += (f"\nThe page under test is: {url}\n" if url
            else "\nThe case does not name a page; choose the right one from the site map.\n")
    return (txt + RULES)[:3800]


def author(c: dict, url: str | None, owner_token: str) -> tuple[str, str]:
    r = post("/qa/author/generate", {
        "instructions": instructions(c, url),
        "base_url": url or "https://ml-portfolio-rho.vercel.app",
        "test_name": slug(c), "page_context": SITE_MAP,
        "provider": "groq", "model": "openai/gpt-oss-120b", "owner_token": owner_token,
    })
    return (r.get("code") or ""), (r.get("provider") or "")


def run_once(code: str, name: str, base: str) -> tuple[str | None, dict]:
    acc = post("/qa/run/execute", {"code": code, "base_url": base, "test_name": name,
                                   "runs": 1, "authorized": False})
    cid = acc.get("correlation_id")
    if not cid:
        return None, {"status": "REJECTED", "detail": str(acc)[:200]}
    for _ in range(POLL_MAX):
        time.sleep(POLL_EVERY)
        try:
            st = CLIENT.get(f"{SPACE}/qa/run/status/{cid}").json()
        except (httpx.HTTPError, ValueError):
            continue
        if st.get("status") not in RUNNING:
            return cid, st
    return cid, {"status": "timeout"}


def pilot_one(c: dict, owner_token: str) -> dict:
    url = c.get("target_url")
    arm = "A" if url else "B"
    base = url or "https://ml-portfolio-rho.vercel.app"
    name = slug(c)

    code = ""
    for attempt in range(3):
        code, _ = author(c, url, owner_token)
        if code.strip():
            break
        time.sleep(40 * (attempt + 1))
    if not code.strip():
        return {"arm": arm, "verdict": "AUTHOR_EMPTY",
                "reason": "every author attempt came back empty (provider rate limit)"}

    cid, res = run_once(code, name, base)
    if res.get("passed"):
        return {"arm": arm, "verdict": "PASS", "code": code, "heals": 0}

    for attempt in range(1, HEAL_CAP + 1):
        if res.get("status") != "completed":
            return {"arm": arm, "verdict": "STILL_RED",
                    "reason": f"run did not complete: {res.get('status')}"}
        h = post("/qa/run/heal", {"correlation_id": cid, "code": code,
                                  "provider": "groq", "model": "openai/gpt-oss-120b",
                                  "owner_token": owner_token})
        healed, detail = (h.get("healed_code") or ""), (h.get("detail") or "")
        if not healed.strip():
            low = detail.lower()
            bug = "assertion" in low or "real bug" in low
            return {"arm": arm, "verdict": "BUG" if bug else "STILL_RED",
                    "reason": (detail or res.get("error_message") or "")[:300]}
        code = healed
        cid, res = run_once(code, name, base)
        if res.get("passed"):
            return {"arm": arm, "verdict": "HEALED", "code": code, "heals": attempt}

    return {"arm": arm, "verdict": "STILL_RED", "heals": HEAL_CAP,
            "reason": (res.get("error_message") or "")[:300]}


def record(url: str, key: str, tc: str, r: dict, spec: str | None) -> None:
    CLIENT.patch(f"{url}/rest/v1/testops_cases", params={"tc_id": f"eq.{tc}"},
                 headers=headers(key),
                 content=json.dumps({"last_verdict": r["verdict"], "last_run_at": "now()",
                                     "spec_path": spec}))
    payload = {"verdict": r["verdict"], "arm": r["arm"], "suite": "browser-pilot"}
    for k in ("reason", "heals"):
        if r.get(k):
            payload[k] = r[k]
    CLIENT.post(f"{url}/rest/v1/testops_events", headers=headers(key),
                content=json.dumps({"kind": "run_verdict", "tc_id": tc,
                                    "actor": "browser-pilot", "payload": payload}))


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    token = os.environ.get("QA_OWNER_TOKEN", "").strip()
    if not token:
        sys.exit("QA_OWNER_TOKEN not set — source ML-Unified/.env first")

    cases = [c for c in reg.load() if c["lane"] == "BROWSER"]
    random.seed(1025)
    resolved = [c for c in cases if c.get("target_url")]
    unresolved = [c for c in cases if not c.get("target_url")]
    pick = random.sample(resolved, min(n * 2 // 3, len(resolved))) \
        + random.sample(unresolved, min(n - n * 2 // 3, len(unresolved)))
    print(f"pilot: {len(pick)} cases "
          f"(arm A resolved={sum(1 for c in pick if c.get('target_url'))}, "
          f"arm B unresolved={sum(1 for c in pick if not c.get('target_url'))})", flush=True)

    os.makedirs(SUITE, exist_ok=True)
    db_url, db_key = credentials()
    results: dict[str, dict] = {}
    lock = threading.Lock()

    def work(c: dict) -> None:
        try:
            r = pilot_one(c, token)
        except Exception as exc:                      # a pilot must not die on one case
            r = {"arm": "?", "verdict": "ERROR", "reason": f"{type(exc).__name__}: {exc}"[:200]}
        spec = None
        code = r.pop("code", "")
        if code and r["verdict"] in ("PASS", "HEALED"):
            spec = f"tests/testwright-suite/{slug(c)}.spec.ts"
            with open(os.path.join(reg.REPO, spec), "w", encoding="utf-8") as f:
                f.write(code)
        with lock:
            results[c["tc_id"]] = r
            record(db_url, db_key, c["tc_id"], r, spec)
            print(f"  [{len(results):>2}/{len(pick)}] {c['tc_id']:14} {r['arm']} "
                  f"{r['verdict']:13} {str(r.get('reason', ''))[:70]}", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, pick))

    from collections import Counter
    print(f"\nelapsed {(time.time() - t0) / 60:.1f} min", flush=True)
    for arm in ("A", "B"):
        sub = [r for r in results.values() if r["arm"] == arm]
        if sub:
            good = sum(1 for r in sub if r["verdict"] in ("PASS", "HEALED"))
            print(f"  arm {arm}: {good}/{len(sub)} usable — {dict(Counter(r['verdict'] for r in sub))}")
    print("overall:", dict(Counter(r["verdict"] for r in results.values())))


if __name__ == "__main__":
    main()
