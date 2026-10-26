#!/usr/bin/env python3
"""Capture what is REALLY on each page, locally, so authoring stops guessing.

    .venv/bin/python scripts/testops_snapshot.py [--pages N]

The first authoring pass scored 24% and 22 of its 29 failures were "locator
never resolved" — the model inventing a selector from prose. The cure is to show
it the page's real controls.

Testwright's Discover stage does this on the runner, but its /status endpoint
throws the snapshot away if its LLM proposal step fails, and that step runs on
free quotas that are exhausted. Capturing locally has no LLM in the path, no
rate limit and no CI cost, so the whole site can be captured in one go and
re-captured whenever the UI changes.

The output format deliberately matches what routers/qa/locators.py already
grounds against — `[role] name="..."` lines plus a link map — so the server's
deterministic locator transforms keep working on the generated code.
"""
from __future__ import annotations

import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

import testops_registry as reg

CACHE = os.path.join(reg.REPO, "tests", ".testops", "snapshots.json")
PORTFOLIO = "https://ml-portfolio-rho.vercel.app"
SPACE = "https://wram1708-ml-unified.hf.space"
SEEDS = [PORTFOLIO, f"{SPACE}/?mode=ml", f"{SPACE}/?mode=eda", f"{SPACE}/?mode=vision"]
MAX_PAGES = 120
# Crawling alone misses most of the site: on a category page a tool renders as a
# CARD (an <h3> plus a <button>), not an <a href>, so ~60 tool routes have no link
# to follow. The filesystem has the real answer, so read the routes from there.
APP_DIR = os.path.join(reg.PORTFOLIO, "src", "app")
SKIP_ROUTES = {"/embed/widget"}        # not a page a test navigates to
MAX_CONTROLS = 60
SETTLE_MS = 2500

# Mirrors routers/qa/discover.py's grabControls: the page's real interactive
# elements, one per line, named the way a Playwright role locator would find them.
GRAB = """() => {
  const sel = 'a[href],button,input,textarea,select,[role=button],[role=link],'
    + '[role=combobox],[role=searchbox],[role=textbox],[role=listbox],'
    + '[role=checkbox],[role=radio],[role=tab],[role=menuitem],[role=switch]';
  const roleOf = (e) => {
    let r = (e.getAttribute('role') || '').toLowerCase();
    if (r) return r;
    const tn = e.tagName.toLowerCase();
    if (tn === 'a') return 'link';
    if (tn === 'button') return 'button';
    if (tn === 'select') return 'combobox';
    if (tn === 'textarea') return 'textbox';
    if (tn !== 'input') return tn;
    const ty = (e.getAttribute('type') || 'text').toLowerCase();
    if (ty === 'search') return 'searchbox';
    if (ty === 'checkbox' || ty === 'radio') return ty;
    if (ty === 'button' || ty === 'submit' || ty === 'reset') return 'button';
    return 'textbox';
  };
  const name = (e) => {
    const al = (e.getAttribute('aria-label') || '').trim();
    if (al) return al;
    // Accessible name, not raw text: drop aria-hidden decoration so a card link
    // is named by its title and not by every nested label concatenated.
    const c = e.cloneNode(true);
    c.querySelectorAll('[aria-hidden="true"]').forEach((n) => n.remove());
    return (c.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 60);
  };
  const out = [];
  for (const e of document.querySelectorAll(sel)) {
    const r = roleOf(e), n = name(e);
    const ph = (e.getAttribute('placeholder') || '').trim();
    if (n) out.push('[' + r + '] name=' + JSON.stringify(n));
    if (ph) out.push('[' + r + '] placeholder=' + JSON.stringify(ph));
  }
  const heads = [...document.querySelectorAll('h1,h2,h3')]
    .map((h) => (h.textContent || '').replace(/\\s+/g, ' ').trim())
    .filter(Boolean).slice(0, 40);
  const links = [...document.querySelectorAll('a[href]')]
    .map((a) => [(a.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 60), a.href])
    .filter(([t]) => t);
  const testids = [...document.querySelectorAll('[data-testid]')]
    .map((e) => e.getAttribute('data-testid'));
  return { controls: [...new Set(out)], headings: [...new Set(heads)],
           links, testids: [...new Set(testids)] };
}"""


def same_site(url: str) -> bool:
    return url.startswith(PORTFOLIO) or url.startswith(SPACE)


def routes_from_disk() -> list[str]:
    """Every static portfolio route, read from src/app. Dynamic segments ([slug])
    are skipped — there is no single URL to capture for them."""
    out = []
    for root, _dirs, files in os.walk(APP_DIR):
        if "page.tsx" not in files:
            continue
        rel = os.path.relpath(root, APP_DIR)
        if "[" in rel:
            continue
        # Route groups like (auth) are organisational only and not in the URL.
        parts = [p for p in rel.split(os.sep) if p not in (".",) and not p.startswith("(")]
        path = "/" + "/".join(parts)
        if path in SKIP_ROUTES:
            continue
        out.append(PORTFOLIO + (path if path != "/" else ""))
    return sorted(set(out))


def capture(page, url: str) -> dict | None:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as exc:
        print(f"  !! {url} — {type(exc).__name__}")
        return None
    # Both sites are client-rendered: without a settle the snapshot is the shell.
    page.wait_for_timeout(SETTLE_MS)
    try:
        return page.evaluate(GRAB)
    except Exception as exc:
        print(f"  !! {url} — evaluate failed: {exc}")
        return None


def crawl(limit: int) -> dict[str, dict]:
    snaps: dict[str, dict] = {}
    queue = list(SEEDS) + routes_from_disk()
    seen: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        while queue and len(snaps) < limit:
            url = queue.pop(0).rstrip("/")
            if url in seen:
                continue
            seen.add(url)
            data = capture(page, url)
            if not data:
                continue
            links = data.pop("links", [])
            snaps[url] = data
            print(f"  [{len(snaps):>2}] {url}  "
                  f"{len(data['controls'])} controls, {len(data['headings'])} headings")
            for _, href in links:
                h = href.split("#")[0].rstrip("/")
                if same_site(h) and h not in seen and h not in queue:
                    queue.append(h)
        browser.close()
    return snaps


def main() -> None:
    limit = MAX_PAGES
    if "--pages" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--pages") + 1])
    t0 = time.time()
    snaps = crawl(limit)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(snaps, open(CACHE, "w", encoding="utf-8"), indent=1)

    ctrls = sum(len(s["controls"]) for s in snaps.values())
    ids = sum(len(s["testids"]) for s in snaps.values())
    print(f"\n{len(snaps)} pages, {ctrls} controls, {ids} data-testid "
          f"in {(time.time() - t0) / 60:.1f} min -> {CACHE}")


if __name__ == "__main__":
    main()
