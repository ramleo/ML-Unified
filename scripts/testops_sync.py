#!/usr/bin/env python3
"""Push the parsed test-case registry into Supabase.

    .venv/bin/python scripts/testops_sync.py [--dry-run]

Credentials come from the environment, or from ml-portfolio/.env.local if that is
all there is. Needs the SERVICE ROLE key: testops_* has RLS on with no policies,
so the anon key can read and write nothing.

Two rules this script exists to honour:

1. The markdown is the source of truth for a case's TEXT. Every sync refreshes
   name/steps/expected/hint from the files.
2. The DATABASE is the source of truth for a case's JUDGEMENT. A row with
   lane_locked = true keeps its lane, ready and target_url — the regex classifier
   is 67% accurate and must never overwrite a human or model correction.
"""
from __future__ import annotations

import json
import os
import sys

import httpx

import testops_registry as reg

PORTFOLIO_ENV = os.path.join(reg.PORTFOLIO, ".env.local")
BATCH = 200


def credentials() -> tuple[str, str]:
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (url and key) and os.path.exists(PORTFOLIO_ENV):
        for line in open(PORTFOLIO_ENV, encoding="utf-8"):
            line = line.strip()
            if "=" not in line or line.startswith("#"):
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if k == "NEXT_PUBLIC_SUPABASE_URL" and not url:
                url = v
            elif k == "SUPABASE_SERVICE_ROLE_KEY" and not key:
                key = v
    if not (url and key):
        sys.exit("No Supabase credentials. Set NEXT_PUBLIC_SUPABASE_URL and "
                 "SUPABASE_SERVICE_ROLE_KEY, or provide ml-portfolio/.env.local.")
    return url.rstrip("/"), key


def headers(key: str, *, upsert: bool = False) -> dict:
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if upsert:
        h["Prefer"] = "resolution=merge-duplicates,return=minimal"
    return h


def locked_ids(client: httpx.Client, url: str, key: str) -> set[str]:
    """Cases whose classification a human or model has corrected."""
    r = client.get(f"{url}/rest/v1/testops_cases",
                   params={"select": "tc_id", "lane_locked": "eq.true", "limit": "10000"},
                   headers=headers(key))
    if r.status_code == 404 or r.status_code == 406:
        return set()
    r.raise_for_status()
    return {row["tc_id"] for row in r.json()}


JUDGEMENT = ("lane", "ready", "target_url", "resolve_method", "lane_origin")


def row_for(c: dict, *, include_judgement: bool) -> dict:
    row = {
        "tc_id": c["tc_id"],
        "source_file": c["source_file"],
        "category": c.get("category"),
        "test_name": c.get("test_name"),
        "steps": c.get("steps"),
        "expected": c.get("expected"),
        "hint": c.get("hint"),
        "source_part": c.get("source_part"),
        "updated_at": "now()",
    }
    if include_judgement:
        row.update({
            "lane": c.get("lane"),
            "ready": c.get("ready") or None,
            "target_url": c.get("target_url"),
            "resolve_method": c.get("resolve_method"),
            "lane_origin": "regex",
        })
    return row


def push(client: httpx.Client, url: str, key: str, rows: list[dict]) -> int:
    sent = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        r = client.post(f"{url}/rest/v1/testops_cases", headers=headers(key, upsert=True),
                        content=json.dumps(chunk))
        if r.status_code >= 400:
            sys.exit(f"upsert failed ({r.status_code}): {r.text[:400]}\n"
                     "If the table is missing, run supabase/testops.sql first.")
        sent += len(chunk)
    return sent


def log_event(client: httpx.Client, url: str, key: str, payload: dict) -> None:
    client.post(f"{url}/rest/v1/testops_events", headers=headers(key),
                content=json.dumps({"kind": "sync", "actor": "testops_sync.py",
                                    "payload": payload}))


def main() -> None:
    dry = "--dry-run" in sys.argv
    cases = reg.load()
    print(f"parsed {len(cases)} cases")

    if dry:
        import collections
        print("lanes     :", dict(collections.Counter(c["lane"] for c in cases)))
        print("resolution:", dict(collections.Counter(c["resolve_method"] for c in cases)))
        print("dry run — nothing written")
        return

    url, key = credentials()
    with httpx.Client(timeout=60) as client:
        locked = locked_ids(client, url, key)
        if locked:
            print(f"{len(locked)} case(s) have a locked classification — "
                  "their lane/url will be preserved")
        free = [row_for(c, include_judgement=True) for c in cases if c["tc_id"] not in locked]
        held = [row_for(c, include_judgement=False) for c in cases if c["tc_id"] in locked]
        n = push(client, url, key, free)
        n += push(client, url, key, held) if held else 0
        log_event(client, url, key,
                  {"total": len(cases), "classified": len(free), "preserved": len(held)})
    print(f"synced {n} rows")


if __name__ == "__main__":
    main()
