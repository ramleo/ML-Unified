#!/usr/bin/env python3
"""Author Playwright specs from case text, one LLM call per case.

    .venv/bin/python scripts/testops_author.py [n] [--ids TC-A-1,TC-B-2]

Authoring is the ONLY irreducible per-case cost in the browser lane: every case
needs its own LLM call, and no batching avoids that. Validation is separate and
cheap — testops_batch_run.py merges ~40 finished specs into one dispatch.

There is one arm, deliberately. The pilot ran a control: cases WITH a resolved
URL scored 10/13, cases with NO url and only the site map scored 6/7. The
resolver lost, and it had manufactured a false bug (TC-P13-037 sent to
/tools/ml-pipeline because that string appears in the case's expected text, when
the case is about `/`). So nothing here passes a target URL. The model picks the
page from the site map.

Pacing is the real ceiling, not a guess: Groq free is 8,000 TPM and an author
call costs ~5,900 because the server appends a 3,600-token AUTHOR_GROUNDING
block whenever page_context is sent. That is ~1.4 calls/min.
"""
from __future__ import annotations

import json
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

import testops_registry as reg
from testops_sync import credentials, headers
from testops_pilot import Bucket, SITE_MAP, RULES, slug, SUITE, SPACE

AUTHORS_PER_MIN = 1.3
WORKERS = 2
PORTFOLIO = "https://ml-portfolio-rho.vercel.app"

LLM = Bucket(AUTHORS_PER_MIN)
CLIENT = httpx.Client(timeout=180)


def instructions(c: dict, grounded: bool = False) -> str:
    txt = (f"Test case {c['tc_id']} — {c.get('test_name', '')}\n"
           f"Steps:\n{c.get('steps', '')}\n"
           f"Expected result: {c.get('expected', '')}\n")
    if c.get("hint"):
        txt += f"Automation hint from the case author: {c['hint']}\n"
    txt += ("\nThe page's real contents are given below; use them.\n" if grounded else
            "\nThe case does not name a page; choose the right one from the site map.\n")
    return (txt + RULES)[:3800]


def author(c: dict, token: str, page_context: str = "",
           base_url: str = PORTFOLIO) -> tuple[str, str]:
    """One author call. Returns (code, provider) — empty code means it failed.

    With no page_context the model gets the hand-written site map and invents
    selectors; with one it gets the page's real controls (testops_snapshot.py).
    """
    grounded = bool(page_context)
    for attempt in range(3):
        LLM.take()
        try:
            r = CLIENT.post(f"{SPACE}/qa/author/generate", json={
                "instructions": instructions(c, grounded), "base_url": base_url,
                "test_name": slug(c), "page_context": page_context or SITE_MAP,
                "provider": "groq", "model": "openai/gpt-oss-120b",
                "owner_token": token,
            })
            body = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            body = {"_error": str(exc)[:120]}
        code = (body.get("code") or "").strip()
        if code:
            return code, (body.get("provider") or "")
        time.sleep(40 * (attempt + 1))
    return "", ""


def pick(n: int, ids: list[str] | None, seed: int = 1026) -> list[dict]:
    """Up to n browser cases with no spec on disk yet, plus any explicitly named.

    The sample is RANDOM, not the first n by id. Sorting by id picks 40
    consecutive cases out of one TC file — all the same feature, all the same
    author's style — and a yield measured on that does not generalise to 817.
    Seeded so a re-run picks the same cases.
    """
    cases = reg.load()
    have = {f.split(".spec.ts")[0] for f in os.listdir(SUITE)} if os.path.isdir(SUITE) else set()
    todo = [c for c in cases if c["lane"] == "BROWSER" and slug(c) not in have]

    chosen: list[dict] = []
    if ids:
        want = {i.strip().upper() for i in ids}
        chosen = [c for c in cases if c["tc_id"].upper() in want]
        picked = {c["tc_id"] for c in chosen}
        todo = [c for c in todo if c["tc_id"] not in picked]

    fill = max(n - len(chosen), 0)
    random.seed(seed)
    chosen += random.sample(todo, min(fill, len(todo)))
    return chosen


def record(url: str, key: str, tc: str, ok: bool, provider: str, detail: str) -> None:
    payload = {"ok": ok, "provider": provider or None, "suite": "browser-author"}
    if detail:
        payload["reason"] = detail[:300]
    CLIENT.post(f"{url}/rest/v1/testops_events", headers=headers(key),
                content=json.dumps({"kind": "author", "tc_id": tc,
                                    "actor": "browser-author", "payload": payload}))


def main() -> None:
    token = os.environ.get("QA_OWNER_TOKEN", "").strip()
    if not token:
        sys.exit("QA_OWNER_TOKEN not set — source ML-Unified/.env first")

    ids = None
    if "--ids" in sys.argv:
        ids = sys.argv[sys.argv.index("--ids") + 1].split(",")
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 40

    cases = pick(n, ids)
    if not cases:
        sys.exit("nothing to author — every selected case already has a spec")
    print(f"authoring {len(cases)} cases at ~{AUTHORS_PER_MIN}/min "
          f"(~{len(cases) / AUTHORS_PER_MIN:.0f} min)", flush=True)

    os.makedirs(SUITE, exist_ok=True)
    db_url, db_key = credentials()
    lock, done = threading.Lock(), {"ok": 0, "fail": 0}

    def work(c: dict) -> None:
        try:
            code, provider = author(c, token)
        except Exception as exc:                  # one bad case must not kill the run
            code, provider = "", ""
            detail = f"{type(exc).__name__}: {exc}"
        else:
            detail = "" if code else "every author attempt came back empty"
        # The server already rejects code that cannot parse; this only catches an
        # answer that is prose rather than a test.
        if code and "test(" not in code:
            code, detail = "", "the model returned something that is not a test"
        if code:
            with open(os.path.join(SUITE, f"{slug(c)}.spec.ts"), "w", encoding="utf-8") as f:
                f.write(code)
        with lock:
            done["ok" if code else "fail"] += 1
            record(db_url, db_key, c["tc_id"], bool(code), provider, detail)
            print(f"  [{done['ok'] + done['fail']:>3}/{len(cases)}] {c['tc_id']:14} "
                  f"{'ok' if code else 'FAILED'}  {detail[:60]}", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, cases))

    mins = (time.time() - t0) / 60
    print(f"\n{done['ok']}/{len(cases)} authored in {mins:.1f} min "
          f"({mins / max(len(cases), 1) * 60:.0f}s per case)")
    print("next: .venv/bin/python scripts/testops_batch_run.py --record")


if __name__ == "__main__":
    main()
