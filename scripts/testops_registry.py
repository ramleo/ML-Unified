#!/usr/bin/env python3
"""Parse the documented test cases and work out what each one needs to run.

Source of truth for a case's TEXT is Conversations/testcases/TC-*.md. This module
turns those files into records; testops_sync.py pushes the records to Supabase.

A caveat that belongs in the code, not just in a chat log: the lane classifier
below is regex over prose, and it was measured at **67% accuracy** against a
held-out sample of 42 hand-labelled cases (54% before a round of fixes). It is a
starting point, not a verdict. That is why `lane_origin` and `lane_locked` exist
in the schema — a human or model correction outranks this and sync must not
clobber it.
"""
from __future__ import annotations

import glob
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TCDIR = os.path.join(REPO, "Conversations", "testcases")
PORTFOLIO = os.path.join(os.path.dirname(REPO), "ml-portfolio")
TOOLS_DIR = os.path.join(PORTFOLIO, "src", "app", "tools")

SITE = "https://ml-portfolio-rho.vercel.app"
SPACE = "https://wram1708-ml-unified.hf.space"

# ── parsing ──────────────────────────────────────────────────────────────────
# A heading may carry a parenthetical suffix: "### TC-P10-100 (Fixed)". Matching
# only on a bare id silently dropped 8 cases.
HEADING = re.compile(r"^### (TC-[A-Z0-9]+-\d+)\b(.*)$")
FIELD = re.compile(
    r"^\*\*(Category|Test Name|Steps|Expected Result|Automation Hint|Source):\*\*\s*(.*)$")

FIELD_KEY = {
    "Category": "category", "Test Name": "test_name", "Steps": "steps",
    "Expected Result": "expected", "Automation Hint": "hint", "Source": "source_part",
}


def parse_file(path: str) -> list[dict]:
    lines = open(path, encoding="utf-8").read().splitlines()
    starts = [(i, m.group(1)) for i, ln in enumerate(lines) if (m := HEADING.match(ln))]
    out = []
    for n, (i, tc_id) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        rec = {"tc_id": tc_id, "source_file": os.path.basename(path)}
        cur = None
        for ln in lines[i + 1:end]:
            if ln.startswith("## "):
                break
            m = FIELD.match(ln.strip())
            if m:
                cur = FIELD_KEY[m.group(1)]
                rec[cur] = m.group(2).strip()
            elif cur and ln.strip():
                rec[cur] = (rec.get(cur, "") + " " + ln.strip()).strip()
        out.append(rec)
    return out


# ── classification ───────────────────────────────────────────────────────────
DEAD = re.compile(r"auto_pipeline|\bstart\.sh\b|\brun\.sh\b", re.I)
REPO_RE = re.compile(r"readFileSync|json\.load|open\(['\"]|subprocess|\bgrep\b|requirements\.txt"
                     r"|check-file-length|wc -l|py_compile|\bruff\b|glob\.", re.I)
BROWSER = re.compile(r"playwright|testwright|page\.|locator|expect\(page|getByRole|getBy[A-Z]"
                     r"|screenshot|\be2e\b|browser", re.I)
API = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH)\s+[`/h]|pytest|caplog|monkeypatch|httpx"
                 r"|TestClient|client\.(get|post)|curl\b", re.I)
API_HINT = re.compile(r"live fetch|api test|integration test|authed|endpoint|telemetry assertion"
                      r"|provider-cascade|parity test", re.I)
UI_BODY = re.compile(r"\bpanels?\b|\bbuttons?\b|\bclicks?\b|\btabs?\b|renders?\b|\bvisible\b"
                     r"|\bcharts?\b|\bsidebar\b|\bdashboard\b|browser tab|\bdownloads?\b"
                     r"|\bforms?\b|\blabels?\b|navigate", re.I)
HTTP_BODY = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH)\b\s+[`/h]|/predict|/schemas|/health"
                       r"|/metrics|response (body|has)|HTTP \d{3}|returns? \d{3}", re.I)
NO_HINT = re.compile(r"^\s*(\(?none\)?|n/?a|-)\b", re.I)
LESSON_HINT = re.compile(r"none\s*\((method|process|practice|policy|decision)", re.I)
UNIT_ONLY = re.compile(r"unit test|\bunit\b", re.I)

URL_RE = re.compile(r"https?://|(?<![\w/])/(tools/[a-z0-9-]+|handbook|docs|about|changelog"
                    r"|privacy|login|audit|eval|eda|sql)\b", re.I)
SETUP = re.compile(r"\bupload|drag|drop a file|run eda|\btrain\b|wizard|sign in|log in"
                   r"|authenticate|api key|\bcsv\b|\bpdf\b|\bvideo\b|image file|run automl", re.I)


def classify(c: dict) -> tuple[str, str]:
    hint = (c.get("hint") or "").strip()
    body = " ".join(str(c.get(k, "")) for k in ("test_name", "steps", "expected"))
    everything = body + " " + hint
    effective = "" if NO_HINT.match(hint) else hint

    if DEAD.search(everything):
        return "DEAD", ""
    if LESSON_HINT.search(hint):
        return "LESSON", ""
    if effective:
        browser = BROWSER.search(effective) and not UNIT_ONLY.search(effective)
    else:
        browser = BROWSER.search(body) or (UI_BODY.search(body) and not HTTP_BODY.search(body))
    if browser:
        has_url = bool(URL_RE.search(everything))
        needs_setup = bool(SETUP.search(everything))
        ready = ("READY" if has_url and not needs_setup else
                 "SETUP" if has_url else
                 "NO_URL" if not needs_setup else "NO_URL_SETUP")
        return "BROWSER", ready
    if REPO_RE.search(effective):
        return "REPO", ""
    if API.search(effective) or API_HINT.search(effective) or HTTP_BODY.search(body):
        return "API", ""
    if not effective:
        return "LESSON", ""
    return "UNKNOWN", ""


# ── URL resolution ───────────────────────────────────────────────────────────
# Code spans and CSS selectors are stripped BEFORE matching. Without this, a case
# about "Clean & Export" matched the `shap` tool because its steps mention a
# `.shap-header` selector — the panel reuses SHAP's styling.
CODE = re.compile(r"`[^`]*`|\.[a-zA-Z][\w-]*\b|#[a-zA-Z][\w-]*\b|<[^>]+>")
STOP = {"the", "and", "for", "with", "from", "that", "this", "not", "are", "all", "any", "its"}
STATIC = {"handbook": "/handbook", "docs": "/docs", "about": "/about", "changelog": "/changelog",
          "privacy": "/privacy", "login": "/login", "homepage": "/", "portfolio": "/", "eda": "/eda"}
SPACE_MODES = {"vision": f"{SPACE}/?mode=vision", "eda": f"{SPACE}/?mode=eda",
               "sidebar": f"{SPACE}/?mode=ml", "automl": f"{SPACE}/?mode=ml"}


def _slugs() -> list[str]:
    if not os.path.isdir(TOOLS_DIR):
        return []
    return sorted(d for d in os.listdir(TOOLS_DIR)
                  if os.path.isdir(os.path.join(TOOLS_DIR, d)) and not d.startswith("["))


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in STOP}


def resolve(case: dict, slugs: list[str] | None = None) -> tuple[str | None, str]:
    """-> (url, method) with method in explicit|slug|static|space-mode|unresolved."""
    slugs = _slugs() if slugs is None else slugs
    raw = " ".join(str(case.get(k, "")) for k in ("test_name", "steps", "expected"))

    m = re.search(r"https?://[^\s`)>\]]+", raw)
    if m:
        return m.group(0).rstrip(".,"), "explicit"
    m = re.search(r"(?<![\w/])(/(?:tools/[a-z0-9-]+|handbook|docs|about|changelog|privacy"
                  r"|login|eda))\b", raw)
    if m:
        return SITE + m.group(1), "explicit"

    clean = CODE.sub(" ", raw)
    cw = _words(clean)
    best, score = None, 0.0
    for s in slugs:
        sw = _words(s.replace("-", " "))
        if not sw:
            continue
        hit = len(sw & cw) / len(sw)
        if hit > score:
            best, score = s, hit
    # A single-word slug matching one incidental word is noise; require a
    # multi-word slug to match in full.
    if best and score >= 0.99 and len(_words(best.replace("-", " "))) >= 2:
        return f"{SITE}/tools/{best}", "slug"
    for name, path in STATIC.items():
        if re.search(rf"\b{re.escape(name)}\b", clean, re.I):
            return SITE + path, "static"
    for key, url in SPACE_MODES.items():
        if re.search(rf"\b{key}\b", clean, re.I):
            return url, "space-mode"
    return None, "unresolved"


def load() -> list[dict]:
    slugs = _slugs()
    cases: list[dict] = []
    for p in sorted(glob.glob(os.path.join(TCDIR, "TC-*.md"))):
        cases += parse_file(p)
    for c in cases:
        c["lane"], c["ready"] = classify(c)
        c["target_url"], c["resolve_method"] = resolve(c, slugs)
    return cases


if __name__ == "__main__":
    import collections
    cs = load()
    print(f"parsed {len(cs)} cases from {TCDIR}")
    for k, v in collections.Counter(c["lane"] for c in cs).most_common():
        print(f"  {k:9} {v}")
    print("resolution:", dict(collections.Counter(c["resolve_method"] for c in cs)))
