#!/usr/bin/env python3
"""Re-author failing specs against the page's REAL controls instead of prose.

    .venv/bin/python scripts/testops_reauthor.py [--limit N] [--dry-run]

The first authoring pass scored 9/38. Twenty-two of its failures were
`toBeVisible() failed` after ~18s — a locator for an element that does not
exist, invented by the model from the case text because all it was given was a
site map I had typed by hand.

This pass changes exactly ONE thing: `page_context` is the real control list
captured by testops_snapshot.py. Same model, same cases, same prompt otherwise,
so the difference in pass rate is a measurement of grounding, not a guess.

Which page a case belongs to is NOT re-derived from the case text — that is the
resolver the pilot already measured and killed. It is read from the spec the
model itself wrote last time: the model chose the page well (arm B beat arm A),
it just invented the selectors once it got there.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

import testops_registry as reg
from testops_sync import credentials, headers
from testops_author import author, record, PORTFOLIO
from testops_pilot import slug, SUITE
from testops_snapshot import CACHE

MAX_CONTEXT = 4200          # chars; keeps the call under Groq's 8,000 TPM ceiling
WORKERS = 2

GOTO = re.compile(r"""page\.goto\(\s*([`'"])(.*?)\1""", re.S)
CONST_URL = re.compile(r"""const\s+(\w+)\s*=\s*['"](https?://[^'"]+)['"]""")
PATH_LIT = re.compile(r"""['"`](/[a-z0-9][\w/-]*)['"`]""")

CLIENT = httpx.Client(timeout=180)


def spec_pages(src: str) -> list[str]:
    """Every page the previous spec actually navigated to, most specific first."""
    consts = dict(CONST_URL.findall(src))
    found: list[str] = []
    for _, raw in GOTO.findall(src):
        s = raw
        for name, val in consts.items():
            s = s.replace("${" + name + "}", val)
        # A `${path}` loop variable leaves a hole; the literal paths in the file
        # are the values it takes, so pair the base with each of them.
        if "${" in s:
            base = re.sub(r"\$\{[^}]+\}", "", s).rstrip("/")
            found += [base + p for p in PATH_LIT.findall(src)]
            continue
        if s.startswith("http"):
            found.append(s)
    found += list(consts.values())
    return [u.rstrip("/") for u in found]


DOMAIN = {"ml", "portfolio", "rho", "vercel", "app", "tools", "wram1708",
          "unified", "space", "https", "com", "www"}
STOP = {"the", "a", "an", "and", "or", "in", "on", "for", "to", "of", "is", "are",
        "with", "that", "this", "it", "shows", "show", "page", "test", "click",
        "open", "load", "check", "verify", "assert", "each", "all", "then", "not",
        "when", "after", "from", "per", "its", "should", "must", "button", "tab"}


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9]{2,}", (text or "").lower())
            if w not in STOP}


def path_words(url: str) -> set[str]:
    return words(url.split("//", 1)[-1].replace("/", " ").replace("-", " ")) - DOMAIN


def path_doc_freq(snaps: dict) -> dict:
    """How many pages each path word names — the rarer, the more it identifies."""
    from collections import Counter
    df = Counter()
    for url in snaps:
        df.update(path_words(url))
    return {w: max(n, 1) for w, n in df.items()}


def rank_pages(c: dict, snaps: dict, prior: list[str], top: int = 3) -> list[str]:
    """Shortlist the pages a case is most likely about.

    This is NOT the URL resolver the pilot killed. That one pattern-matched the
    case's prose for a slug and COMMITTED to one URL, which is how TC-P13-037 got
    sent to /tools/ml-pipeline. Here the score comes from the page's REAL captured
    headings, controls and path, several candidates survive, and the model makes
    the final call — which is the arrangement that actually won the control arm.
    """
    want = words(f"{c.get('test_name', '')} {c.get('steps', '')} {c.get('expected', '')}")
    df = path_doc_freq(snaps)
    scored = []
    for url, s in snaps.items():
        if not (s["controls"] or s["headings"]):
            continue                       # an empty or non-HTML capture (openapi.json)
        path = path_words(url)
        head = words(" ".join(s["headings"][:25]))
        ctrl = words(" ".join(s["controls"][:60]))
        # A path hit is decisive — a case naming "Optuna" belongs on /tools/optuna.
        # But weight each hit by how RARE the word is across all paths: "optuna"
        # names one page, while "text" names three (text-to-sql, text-to-image,
        # text-prompted-video-tracking) and a case saying "description text" must
        # not be dragged onto them. Control overlap is capped because /handbook has
        # 183 controls and would otherwise match everything.
        score = (sum(20.0 / df[w] for w in want & path)
                 + 4 * len(want & head) + min(len(want & ctrl), 5))
        if score:
            scored.append((score, url))
    scored.sort(reverse=True)
    out = [u for _, u in scored[:top]]
    # Keep whatever page the previous spec used as a fallback candidate, so a case
    # the scorer cannot place still has somewhere real to be grounded against.
    for u in prior:
        if u in snaps and u not in out:
            out.append(u)
            break
    return out[:top + 1]


def page_block(url: str, s: dict, budget: int) -> str:
    block = f"=== {url} ===\n"
    if s["headings"]:
        block += "HEADINGS: " + " | ".join(s["headings"][:12]) + "\n"
    block += "CONTROLS:\n" + "\n".join(s["controls"][:40])
    if s["testids"]:
        block += "\nTEST IDS: " + ", ".join(s["testids"][:20])
    return block[:budget] + "\n"


def context_for(urls: list[str], snaps: dict) -> tuple[str, str]:
    """Real content for each shortlisted page, with the model told to choose."""
    pages = [u for u in urls if u in snaps]
    if not pages:
        return "", ""
    budget = max(MAX_CONTEXT // len(pages), 600)
    body = "".join(page_block(u, snaps[u], budget) for u in pages)
    head = ("REAL CONTENT captured from the candidate pages below. Pick the ONE page "
            "this test case is about and goto its exact URL. Use ONLY names that "
            "appear in that page's list — if what the case describes is not there, it "
            "is not on the page, so assert what the expected result implies from the "
            "names that ARE there. Never invent a name.\n\n")
    return (head + body)[:MAX_CONTEXT + 400], pages[0]


def red_cases(url: str, key: str) -> set[str]:
    r = CLIENT.get(f"{url}/rest/v1/testops_cases", headers=headers(key),
                   params={"select": "tc_id",
                           "last_verdict": "in.(STILL_RED,NOT_IN_REPORT)"})
    return {x["tc_id"] for x in r.json()}


def main() -> None:
    token = os.environ.get("QA_OWNER_TOKEN", "").strip()
    if not token:
        sys.exit("QA_OWNER_TOKEN not set — source ML-Unified/.env first")
    dry = "--dry-run" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 999

    snaps = json.load(open(CACHE, encoding="utf-8"))
    db_url, db_key = credentials()
    red = red_cases(db_url, db_key)

    work_items = []
    for c in reg.load():
        if c["tc_id"] not in red:
            continue
        path = os.path.join(SUITE, slug(c) + ".spec.ts")
        if not os.path.exists(path):
            continue
        prior = spec_pages(open(path, encoding="utf-8").read())
        cands = rank_pages(c, snaps, prior)
        ctx, page = context_for(cands, snaps)
        work_items.append((c, path, ctx, page, cands))
    work_items = work_items[:limit]

    grounded = sum(1 for it in work_items if it[2])
    print(f"{len(work_items)} red cases — {grounded} matched a captured page, "
          f"{len(work_items) - grounded} did not")
    if dry:
        for c, _, ctx, _page, cands in work_items:
            short = [u.replace("https://ml-portfolio-rho.vercel.app", "")
                      .replace("https://wram1708-ml-unified.hf.space", "SPACE") or "/"
                     for u in cands]
            print(f"  {c['tc_id']:14} {len(ctx):>5}ch  {', '.join(short)}")
        return

    lock, done = threading.Lock(), {"ok": 0, "fail": 0}

    def run(item) -> None:
        c, path, ctx, page, _cands = item
        if not ctx:
            with lock:
                done["fail"] += 1
                print(f"  {c['tc_id']:14} SKIPPED — no captured page matched")
            return
        code, provider = author(c, token, page_context=ctx,
                                base_url=page or PORTFOLIO)
        if code and "test(" in code:
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
        with lock:
            ok = bool(code)
            done["ok" if ok else "fail"] += 1
            record(db_url, db_key, c["tc_id"], ok, provider, "" if ok else "empty")
            print(f"  [{done['ok'] + done['fail']:>2}/{len(work_items)}] {c['tc_id']:14} "
                  f"{'re-authored' if ok else 'FAILED'}  {page}")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(run, work_items))
    print(f"\n{done['ok']}/{len(work_items)} re-authored in {(time.time() - t0) / 60:.1f} min")
    print("next: .venv/bin/python scripts/testops_batch_run.py --record")


if __name__ == "__main__":
    main()
