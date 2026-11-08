#!/usr/bin/env python3
"""Reject a generated spec whose locators are not on the page it was grounded on.

The prompt already says "never invent a name" and the model did it anyway
(`[class*="ks-stat"]`, `data-testid="sc-filename"`, a hardcoded session id). A
sentence in a prompt is a request; this is a check. It reads the spec and the
page's captured control list and returns the violations, so the author step can
ask once more with the exact complaints instead of shipping a spec that cannot
resolve.

    violations(code, snapshot) -> list[str]     # empty = clean
"""
from __future__ import annotations

import re

CONTROL = re.compile(r'^\[(\w+)\] (?:name|placeholder)=("(?:[^"\\]|\\.)*")(?: #(\S+))?( HIDDEN)?$')
ROLE_CALL = re.compile(r"""getByRole\(\s*(['"])(\w+)\1\s*(?:,\s*\{(.*?)\})?\s*\)(\s*\.(?:first|last|nth)\()?""", re.S)
NAME_ARG = re.compile(r"""name:\s*(['"`])(.*?)\1""")
CLASS_SEL = re.compile(r"""\[class[*^$]?=|locator\(\s*['"`][^'"`]*(?<![\w#\[=-])\.[a-z][\w-]*""")
TESTID = re.compile(r"""data-testid\s*=\s*\\?["']?([\w-]+)|getByTestId\(\s*['"]([\w-]+)['"]""")
ID_SEL = re.compile(r"""locator\(\s*['"`]#([\w-]+)""")
HEX_ID = re.compile(r"""\b[0-9a-f]{8}\b""")


def parse(snapshot: dict) -> list[dict]:
    out = []
    for line in snapshot.get("controls", []):
        m = CONTROL.match(line)
        if m:
            import json
            out.append({"role": m[1], "name": json.loads(m[2]), "id": m[3] or "",
                        "hidden": bool(m[4])})
    return out


def violations(code: str, snapshot: dict) -> list[str]:
    ctrls = parse(snapshot)
    ids = {c["id"] for c in ctrls if c["id"]}
    testids = set(snapshot.get("testids", []))
    bad: list[str] = []

    for m in ROLE_CALL.finditer(code):
        role, opts, chained = m[2], m[3] or "", m[4]
        nm = NAME_ARG.search(opts)
        if role == "heading" and not snapshot.get("headings"):
            bad.append("getByRole('heading') — this page has no headings; use a control from the list")
            continue
        if not nm:
            continue
        name = nm[2]
        if HEX_ID.search(name):
            bad.append(f"name '{name}' contains a hardcoded id; live data changes between runs")
        exact = re.search(r"exact:\s*true", opts)
        low = name.lower()
        clicked = ".click(" in code[:m.start()]      # earlier steps may reveal new controls
        if role == "heading":
            heads = snapshot.get("headings", [])
            if not clicked and not any(low in h.lower() for h in heads):
                bad.append(f"heading '{name}' is not in HEADINGS")
            continue
        hits = [c for c in ctrls if c["role"] == role and
                ((c["name"] == name) if exact else (low in c["name"].lower()))]
        if not hits and clicked:
            continue                                  # not on the load-time page; cannot judge
        if not hits:
            bad.append(f"getByRole('{role}', name '{name}') — no such {role} in the list")
        elif not chained and len(hits) > 1:
            bad.append(f"name '{name}' matches {len(hits)} {role}s "
                       f"({', '.join(h['id'] and '#' + h['id'] or h['name'] for h in hits[:4])}); "
                       "use exact:true, an #id from the list, or .first()")
        elif all(c["hidden"] for c in hits) and not clicked:
            bad.append(f"'{name}' is HIDDEN until something is opened; click what reveals it first")

    for m in ID_SEL.finditer(code):
        if m[1] not in ids:
            bad.append(f"#{m[1]} is not an id in the list")
    for m in TESTID.finditer(code):
        t = m[1] or m[2]
        if t not in testids:
            bad.append(f"data-testid '{t}' is not in the TEST IDS list")
    if CLASS_SEL.search(code):
        bad.append("CSS class selectors are not allowed; the list has no class names")
    return list(dict.fromkeys(bad))
