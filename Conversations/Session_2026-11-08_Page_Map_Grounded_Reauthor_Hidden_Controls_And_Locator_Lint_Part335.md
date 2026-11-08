# Part 335 — Per-case page map, grounded re-author, hidden controls, and a locator lint (2026-11-08)

Continues Part 334. That part ended with authoring grounded on real page controls and a
Groq daily cap. This session answered the user's challenge — *"why are you guessing URL or
button, don't you know where they are?"* — by reading every case, then used the result.

Suite: **25/54 → 38/54 → 43/54 → 44/54** (commits `14c7d04`, `5ae4b8d`, and the P3-020 follow-up in §5b).

---

## 1. The challenge, and the honest answer

The user asked why the AI guesses pages and buttons, whether the 1,795 cases are concrete, and
why I gave a *rough* count of cases that name their page. The rough count (80 / 483 / 254)
came from a script that cannot tell whether a case names its page; the user was right that I
should simply read them. I read all **817 browser cases** and judged each one.

| code | meaning | count |
|---|---|---|
| T | text names the page/tool/URL (34 of these MULTI-page) | 344 |
| I | page inferred from project knowledge | 331 |
| FEW | 2+ candidate pages | 78 |
| ANY | any page works | 29 |
| ? | cannot tell | 13 |
| M | names `/` but the feature moved to `/about` (Part 13-027) | 12 |
| NOPAGE | CI / Dockerfile / code-grep, not a page test | 10 |
| | **total** | **817** |

Usable page: 704 (T+I+ANY). **Unclear: 91**, not 254. Stored in `tests/.testops/pagemap.json`
(`{tc_id: {kind, url}}`) — hand-judged, not cheaply regenerable. `testops_reauthor.py` uses it
first and only falls back to word-overlap ranking when a case has no single page.

## 2. Grounded re-author with the page map

29 red cases re-authored with their page's real controls: **13/29 pass (0 before)**; full set
25/54 → **38/54**. No control arm — a second attempt alone could explain some of it. Groq
free = 200K tokens/day, so the 29-call run (23.9 min) used most of that day's quota.

## 3. The 16 still-red specs, read one by one

| group | cases | cause |
|---|---|---|
| Hidden, not missing | DOC-002, EARLY-011, EARLY-026, P3-129, P3-020 | snapshot listed controls that are in the DOM but **not visible** (collapsed "Sample Projects" group, closed theme picker). `#btn-iris` text matches, `is_visible()` False; Playwright role locators only match visible nodes |
| Invented / hardcoded | DOC-013, P3-112, P3-113, P4-090, P9-066 | `getByRole('heading')` on a page with no headings; `[class*="ks-stat"]`, `[class*="drift-hist"]`; `data-testid="sc-filename"`; session id `c6d9d4bf` hardcoded |
| Ambiguous | P3-023 | `'Predict'` matches 6 buttons (`#tabPredict`, `#predictBtn`, …) |
| Case vs app | P12-012, P9-028, P4-001, P6-022, P12-066 | see §5 — **none was an app bug** |

The prompt already said "never invent a name"; the model did it anyway. A sentence in a prompt
is a request, a check is a guarantee.

## 4. What was built

- **`scripts/testops_snapshot.py`** — each control now carries `#id` and `HIDDEN`
  (`e.checkVisibility()`), so the author can tell what needs opening first. Recaptured:
  103 pages, 1,504 controls, 59 marked hidden.
- **`scripts/testops_lint.py`** (new, ~90 lines) — rejects a generated spec that uses class
  selectors, an `#id` / `data-testid` absent from the page, a hardcoded 8-hex id, a name
  matching 2+ controls without `exact`/`.first()`, a heading on a heading-less page, or a
  HIDDEN control before any click. Names missing from the load-time snapshot are only
  flagged when nothing was clicked first (a control revealed by a click cannot be in the
  snapshot). On the old specs it flags 13 of the 16 reds; one false positive on a passing
  spec (P2-138, an emoji button) — safe, because a rejected spec leaves the old file.
- **`scripts/testops_reauthor.py`** — runs the lint, retries once with the exact complaints,
  never overwrites the old spec if the retry is still invalid; new `--ids a,b,c`.

Result of the grounded re-author run: **2 of 11** re-authored (DOC-002 now passes; P3-020
times out at 30 s, not yet investigated). The other 9 came back **empty with no lint
message**; a direct probe also returned no code and no error text. Cause not confirmed —
most likely the Groq daily quota already used by the 29-call run. Not retried (two-failures
rule).

## 5. The five "case vs app" cases — all test mistakes

| case | finding | evidence |
|---|---|---|
| P9-028 Ctrl+K | test pressed `Control+K` (uppercase); the app matches `e.key === "k"` | live: `Control+k` focuses the textarea, `Control+K` leaves focus on BODY. Then the spec asserted an invented "Ask" button (not on the page). Rewritten to assert Ctrl+Enter POSTs to `/sql/query`, with the request aborted so no model call is spent |
| P12-012 scroll | test scrolled to 500 (search box at y≈1928, off-screen) then typed → page moved 500→1043 | user checked by hand: typing in the on-screen box does not move the page. Spec now scrolls the box into view first |
| P4-001 | `#modelList .model-btn` does not exist | invented selector (a re-author target), not cold start |
| P6-022 | the spec looked for "Saved" before any run; the case needs a finished AutoML run first | rewritten: generated 150-row CSV, upload, select `label`, "Run AutoML Competition" (~8 s), "Save Version" → disabled "Saved!" → reverts |
| P12-066 | case says 10 tools; spec only opened the category page | category now has **26** tools (ids from `toolNav.ts` `AREA_OF`); one test per tool: "User Guide" button opens a "<tool> — User Guide" panel, "AI Assistant" (title only, no text) opens "Ask about <tool> or this website…" |

Every hand-written spec was run in a local Playwright and **mutated to prove it can fail**
(P6-022 expecting `Saved!!`, P9-028 pressing the wrong key, P12-012 forcing a 100 px
scroll — all went red). P12-066: 26/26 pass locally.

## 5b. TC-P3-020 (sidebar stagger) — fixed after the first commit

Re-authored spec timed out at 30 s: it waited for every `.sb-anim` to be *visible*, but items in
collapsed groups never are. Mechanism (common.js `animateSidebarIn`): each item gets `sb-anim`,
then `sb-visible` via `setTimeout(i*55+30)`.

My first rewrite measured wall-clock gaps between the class additions: 3/3 locally (gaps ≈55 ms,
12 items) but **red on the runner — median gap 0.1 ms**. On a busy runner the page's timers fire
back-to-back, and a MutationObserver callback stamps one `performance.now()` for the whole batch.
Playwright's fake clock did not help (time keeps flowing after `install`). Final spec records the
delay each `sb-visible` timer is *scheduled* with (wraps `setTimeout` in an init script),
asserts consecutive delays differ by exactly 55, and separately waits for every `.sb-anim` to be
`.sb-visible`. Mutated to expect 20 → fails with the real 55. Runner: PASS. White-box: it depends
on the app using `setTimeout` with `sb-visible` in the callback.

**Lesson:** a timing assertion measured on a shared runner needs a load-independent source (what
was scheduled), not observed wall-clock.

## 6. Numbers

`44/54` pass (43 before §5b), ~2.5 min wall-clock. Still red (10): DOC-013, EARLY-011,
EARLY-026, P3-023, P3-112, P3-113, P3-129, P4-001, P4-090, P9-066 — all need a
Groq re-author.

## 7. Mistakes made this session (so they are not repeated)

- A `while pgrep -f testops_snapshot` wait loop **matched its own command line** and never
  ended; the capture had finished 3 minutes earlier. Wait on a PID or the output file, not a
  `pgrep -f` pattern contained in the waiting command.
- Re-ran the whole 54-spec batch twice to read two lines. Grep the first run's output.
- Reported "Saved! vs Saved" as a stale case before reading the spec; the real cause was a
  missing precondition.
- Promised the user a screenshot link of the search box they could not see; they cannot view
  images I read. Describe locations in text (the box under "58 tools, each live and
  testable").

## 8. Open

1. Re-author the ten (needs Groq quota reset or the paid tier — the user's decision).
2. CI for `5ae4b8d` was queued when the session ended (`14c7d04` was green).
3. Carried from Part 334: heal-by-test-title backend change + one batched HF upload; TC-P2-127 /
   TC-P10-096 authoring empty; TC-P2-132 stale; 91 unclear-page cases need user answers;
   12 "moved" cases → `/about`; 10 NOPAGE cases leave the browser lane; API lane (566) and
   262 unclassified unchanged.
