"""
Testwright (QA Automation) — Discover stage.

Point at any public URL: an "explore" run on the isolated runner renders the
page and dumps its ARIA snapshot; the LLM then proposes candidate test cases
from that snapshot. Reuses the qa-run workflow (the explore spec writes
aria.txt, which the workflow uploads).
"""

import json
import logging
import re
import uuid

from fastapi import APIRouter, HTTPException, Request

from routers.qa import config, github_runner
from routers.qa.deps import complete, resolve_key, record_call, limiter, LLM_LIMIT
from routers.qa.prompts import DISCOVER_SYSTEM
from routers.qa.models import DiscoverStart, DiscoverStatus, RunAccepted
from routers.qa.urlcheck import validate_target_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discover")

# Delimiter that separates the ARIA snapshot from the link map inside aria.txt.
# Kept identical on the writer (explore spec) and reader (status) sides.
LINKS_DELIM = "\n\n===LINKS (accessible name -> href)===\n"
# Same string escaped for embedding inside a JS single-quoted string literal.
LINKS_DELIM_JS = LINKS_DELIM.replace("\n", "\\n")


# Delimiter prefix for an extra page's section in aria.txt (deep mode). The full
# header is `===PAGE <url>===`; the reader treats everything before LINKS_DELIM as
# the (possibly multi-page) snapshot, so no reader change is needed.
PAGE_DELIM_JS = "\\n\\n===PAGE "


def build_explore_spec(url: str, deep: bool = False) -> str:
    """A Playwright test that navigates the URL and writes the page's ARIA snapshot
    PLUS a link accessible-name -> href map to aria.txt (uploaded by the workflow).
    The link map lets code generation use real destinations instead of guessing a
    URL from a link's visible label. When `deep`, it also visits up to
    MAX_DEEP_PAGES same-origin links one hop away IN THE SAME RUN and appends each
    page's snapshot, so proposals and grounding span linked pages — no extra CI
    dispatches. The link map block is always written LAST."""
    safe = url.replace("\\", "\\\\").replace("'", "\\'")
    deep_js = ""
    if deep:
        deep_js = (
            "  // One hop deep (opt-in): follow a few same-origin links from THIS\n"
            "  // page and append each linked page's snapshot.\n"
            "  const startUrl = page.url();\n"
            "  const origin = new URL(startUrl).origin;\n"
            "  const targets = await page.$$eval('a[href]', (els, args) => {\n"
            "    const [origin, startUrl, max] = args;\n"
            "    const seen = new Set(); const out = [];\n"
            "    for (const a of els) {\n"
            "      let u; try { u = new URL(a.href); } catch (e) { continue; }\n"
            "      if (u.origin !== origin) continue;\n"
            "      u.hash = '';\n"
            "      const s = u.toString();\n"
            "      if (s === startUrl || seen.has(s)) continue;\n"
            "      seen.add(s); out.push(s);\n"
            "      if (out.length >= max) break;\n"
            "    }\n"
            "    return out;\n"
            f"  }}, [origin, startUrl, {config.MAX_DEEP_PAGES}]);\n"
            "  for (const t of targets) {\n"
            "    try {\n"
            "      await page.goto(t, { waitUntil: 'domcontentloaded' });\n"
            "      await page.waitForTimeout(800);\n"
            "      const snap = await page.locator('body').ariaSnapshot();\n"
            f"      sections += '{PAGE_DELIM_JS}' + t + '===\\n' + "
            f"snap.slice(0, {config.MAX_DEEP_PAGE_CHARS});\n"
            "    } catch (e) { /* skip an unreachable link */ }\n"
            "  }\n"
        )
    return (
        "import { test } from '@playwright/test';\n"
        "import fs from 'fs';\n\n"
        "test('explore', async ({ page }) => {\n"
        f"  await page.goto('{safe}', {{ waitUntil: 'domcontentloaded' }});\n"
        "  await page.waitForTimeout(1500);\n"
        "  const snapshot = await page.locator('body').ariaSnapshot();\n"
        "  let sections = '';\n"
        f"  const links = await page.$$eval('a[href]', (els, max) => {{\n"
        "    const seen = new Set(); const out = [];\n"
        "    for (const a of els) {\n"
        "      const name = (a.getAttribute('aria-label') || a.textContent || '')"
        ".replace(/\\s+/g, ' ').trim().slice(0, 80);\n"
        "      const href = a.getAttribute('href') || '';\n"
        "      if (!name || !href) continue;\n"
        "      const k = name + ' -> ' + href;\n"
        "      if (seen.has(k)) continue;\n"
        "      seen.add(k); out.push(k);\n"
        "      if (out.length >= max) break;\n"
        "    }\n"
        "    return out;\n"
        f"  }}, {config.MAX_LINKS});\n"
        + deep_js +
        "  const block = links.length"
        f"    ? '{LINKS_DELIM_JS}' + links.join('\\n') : '';\n"
        "  fs.writeFileSync('aria.txt', snapshot + sections + block);\n"
        "});\n"
    )


def _strip_fences(raw: str) -> str:
    if not raw:
        return ""
    fence = re.search(r"```(?:json)?\s*\n(.*?)```", raw, re.DOTALL)
    return (fence.group(1) if fence else raw).strip()


def propose_tests(snapshot: str) -> list[dict]:
    """Ask the LLM for candidate test cases from the ARIA snapshot. Returns a
    list of {title, steps}; empty on failure."""
    # MAX_PAGE_CONTEXT (not MAX_SNAPSHOT_CHARS) so a deep multi-page snapshot isn't
    # truncated down to a single page's worth before proposing.
    snap = (snapshot or "")[: config.MAX_PAGE_CONTEXT]
    if not snap.strip():
        return []
    user = f"Accessibility snapshot of the page:\n{snap}"
    for provider, model in config.GEN_CANDIDATES:
        key = resolve_key(provider)
        if not key:
            continue
        try:
            raw = complete(provider, model, key,
                           [{"role": "user", "content": user}], system=DISCOVER_SYSTEM)
        except Exception as exc:
            logger.warning("qa/discover: %s failed: %s", provider, exc)
            continue
        parsed = _parse_proposals(_strip_fences(raw))
        if parsed:
            return parsed
        logger.warning("qa/discover: %s returned unparseable proposals", provider)
    return []


def _parse_proposals(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data[: config.MAX_PROPOSALS]:
        if isinstance(item, dict) and item.get("title") and item.get("steps"):
            out.append({
                "title": str(item["title"])[:160],
                "steps": str(item["steps"])[:800],
            })
    return out


@router.post("/start", response_model=RunAccepted)
@limiter.limit(LLM_LIMIT)
def start(request: Request, req: DiscoverStart):
    """Dispatch an explore run that renders the URL and captures its snapshot."""
    validate_target_url(req.url, required=True, authorized=req.authorized)
    record_call(config.DISCOVER_FEATURE, pool=config.DISCOVER_BUDGET_POOL,
                daily_cap_env=config.DISCOVER_DAILY_CAP_ENV)
    correlation_id = uuid.uuid4().hex
    spec = build_explore_spec(req.url.strip(), deep=req.deep)
    try:
        github_runner.dispatch(spec, req.url.strip(), "explore", correlation_id)
    except Exception as exc:
        logger.error("qa/discover: dispatch failed: %s", exc)
        raise HTTPException(status_code=502, detail="Could not start discovery.")
    return RunAccepted(correlation_id=correlation_id, status="queued")


@router.get("/status/{correlation_id}", response_model=DiscoverStatus)
def status(correlation_id: str):
    try:
        run = github_runner.find_run(correlation_id)
    except Exception as exc:
        logger.error("qa/discover: status lookup failed: %s", exc)
        return DiscoverStatus(status="error", detail="Could not read discovery status.")
    if not run:
        return DiscoverStatus(status="pending", correlation_id=correlation_id)

    gh_status = run.get("status") or "pending"
    run_url = run.get("html_url")
    if gh_status != "completed":
        return DiscoverStatus(status=gh_status, correlation_id=correlation_id, run_url=run_url)

    raw = None
    try:
        raw = github_runner.fetch_text_artifact(run.get("id"), "aria.txt")
    except Exception as exc:
        logger.warning("qa/discover: snapshot fetch failed: %s", exc)
    if not raw:
        return DiscoverStatus(status="error", correlation_id=correlation_id, run_url=run_url,
                              detail="Could not capture the page. Check the URL is reachable.")

    # aria.txt = ARIA snapshot, optionally followed by the link map.
    aria_part, _, links_part = raw.partition(LINKS_DELIM)
    proposals = propose_tests(aria_part)
    if not proposals:
        return DiscoverStatus(status="error", correlation_id=correlation_id, run_url=run_url,
                              detail="No test cases could be proposed from this page.")

    # Page context carried into code generation: the snapshot (so locators are
    # real) plus the link map (so URL assertions use real hrefs, not guesses).
    page_context = aria_part[: config.MAX_PAGE_CONTEXT]
    if links_part.strip():
        page_context += LINKS_DELIM + links_part.strip()[: config.MAX_LINKS_CHARS]
    return DiscoverStatus(status="completed", correlation_id=correlation_id,
                          run_url=run_url, proposals=proposals, page_context=page_context)
