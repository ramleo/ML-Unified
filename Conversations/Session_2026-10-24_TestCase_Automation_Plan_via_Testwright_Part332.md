# Part 332 — Automating the test cases: Testwright trial, cost model, and the free-path plan (2026-10-24)

Continues Part 331 (which generated the test cases for Parts 250–330). This session was
one thread: **how to actually run the ~1,545 documented test cases**, turning them from a
written checklist into a runnable suite. It ended with a costed plan and a scheduled build.

Through-line: **verify, don't assert** — every "failure" in the trial turned out to be a
test-writing or a URL mistake, not a site bug, and the headline cost number (manual tuning
hours) was wrong until the real mechanism was proven.

---

## 1. The question — "how do we test the testcases?"

The TC-*.md files are a **spec/registry, not executable** — markdown with
Category/Steps/Expected/**Automation Hint**/Source. "Testing them" = bridging each to a
harness. The Automation Hint field is the bridge. Three ways exist, all already in the repo:

- **pytest** (`services/ml-api/tests/`) — backend logic, cascades, gates.
- **Playwright e2e** (`tests/e2e/`) — live UI / per-role flows.
- **Testwright** (native `/qa` world) — authors + runs + heals UI tests against the live site.

Coverage audit: **1,545 TCs, 0 linked to running test code** yet. Split by what each needs:
~670 browser-automatable, ~449 backend/pytest, ~107 "none (method)" = **lessons** (e.g.
"don't delete AGENTS.md") with nothing to execute, the rest mixed (mostly browser).

---

## 2. Testwright trial — it works, author→run→heal via the Space

Testwright is self-contained under `routers/qa/` (mounted `/qa` on the live Space
`wram1708-ml-unified.hf.space`), no key needed to author:
- `POST /qa/author/generate` {instructions, base_url, test_name, page_context} → Playwright TS.
- `POST /qa/run/execute` → correlation_id; poll `GET /qa/run/status/{cid}` (running states
  include `in_progress`; terminal `completed` carries a `passed` bool + screenshot + steps).
- `POST /qa/run/heal` {correlation_id, code} → healed_code. **Honest gate:** heals
  locator/timing only; **refuses assertion failures** (returns empty + detail) so a real
  value mismatch escalates as a likely bug instead of being healed into a fake pass.

**Ad-hoc batch of 10:** 4 pass, 5 "fail", 1 rejected. Checked every failure in a real
browser — **zero were site bugs:**
- `/tools` returns **404** — there is no bare tools page. Tools live under category paths
  (`/tools/{computer-vision,security-trust,ml-pipeline,language-documents}`) and render as
  **cards** (an `<h3>` title + a `<button>`), **not** `<a href="/tools/…">` links.
- Nav links (Handbook, Docs…) appear in **both header and footer** → strict-mode "resolved
  to 2". The login form's email + button both matched too. All test-writing issues.
- The site is client-rendered (Next.js) — `curl` sees nothing; must use a browser.

---

## 3. The pushback — automate everything, stop hedging

User (rightly) rejected two things: the sycophantic tone, and the framing that the test
cases were for *manual* running. The point of writing them was to **automate** them.
Correction accepted: the earlier "15–20 hours of manual tuning" estimate was **wrong**.

Web research confirmed the industry-standard pattern is exactly **bounded
generate → run → heal (cap ~3) → escalate** — and Testwright already ships all three
stages, so no external tool is needed.

Built a driver (`scratchpad/tw_auto.py`) running that loop with no human in it. Re-ran the
5 earlier failures **feeding a real `page_context`** (the verified site map):
- **3 passed on the first try — no heal even needed, no manual tuning.** Proper context
  killed the guessing.
- 2 came back `code:""`, `provider:null`. Diagnosed precisely: `record_call` did **not**
  raise (so the daily cap was **not** hit) — `generate_test` returned `None` = **every free
  provider failed at once**, i.e. cohere/mistral **burst rate-limiting** after ~25 rapid
  generations. Recovers after a cooldown.

---

## 4. The real cost model

Key reframe: **authoring is a one-time cost per test; running a saved test uses no AI at
all; heal only fires on failures.** So the free LLM limit caps how fast you *build* the
suite, never how often you *run* it.

Inputs (verified): **670** browser-automatable cases; author cascade = cohere `command-a`
→ mistral (paid fallback gemini-3.6-flash); Cohere trial = **20 req/min + ~1,000 calls/mo**;
Gemini 3.6 Flash ≈ **$1.50/$7.50 per M** (promo ~$0.75/$3.75); **default daily cap = 20 per
pool** (`security/budget.py` `check_and_record_call`, `default_cap=20`).

**One-time build (670 tests):** free = $0 spread over a few days (~870 of the 1,000 monthly
Cohere calls); paid = **~$7 one-time**, ~6h in one sitting.

**User's cadence: twice a month, not daily** → this settles it. Each cycle = run 670 saved
specs ($0, no AI, ~6h) + heal ~10% drift (~67 calls, well within free limits).

| | Free path | Paid path |
|---|---|---|
| Per month (2 cycles) | **$0** | ~$1–2 |
| Per year | **$0** | ~$7 once + ~$15 ≈ ~$22 first yr, ~$15/yr after |

**Decision: FREE.** Paid buys almost nothing at twice-a-month. The one non-negotiable was
free too: raise the daily caps (otherwise a cycle throttles to 20/day).

---

## 5. Prepped for the build (scheduled: next session)

- **Prerequisite DONE:** user raised the Space daily caps from the default 20 →
  `QA_TEST_AUTHOR_DAILY_CAP=1000`, `QA_RUN_DAILY_CAP=1000`, `QA_HEAL_DAILY_CAP=300`
  (user added the heal var; the other two pre-existed). Caps no longer the bottleneck.
- **Start tomorrow** (user's call — the ~6h build is unattended/background anyway).
- **Driver to build:** read `Conversations/testcases/TC-*.md` → parse each `### TC` block →
  browser lane only → author (with page_context) → execute → poll → heal (≤3) → re-run →
  save passing `.spec.ts` to a suite dir + a results report; throttle between calls for the
  free limits. Prototype: `scratchpad/tw_auto.py`.

Saved to memory: [[project_testcase_automation]] (+ index line).

---

## Lessons

- **A red test has three causes, not one** — site bug, test written wrong, or the test-case
  note itself wrong (the `/tools` page that was never built). Every red needs a human glance
  to sort which; that triage is the real residual cost, not locator-typing.
- **Feed the author real page context.** With a verified site map in `page_context`,
  auto-written tests passed first try. Guessing (no context) is what produced the 404 and
  strict-mode misses.
- **`provider:null` + empty ≠ cap hit.** It means the free cascade rate-limited; the cap
  raises an HTTPException instead. Diagnose from which signal actually fired.
- **Price the architecture, not the activity.** Authoring is one-time; running is free;
  heal is the only recurring spend — so at twice-a-month the free path is $0/month.
- **The cap was the bottleneck, and it was free to fix** (owner's own Space env vars). Money
  (Gemini) only buys past the *provider* rate-limit, not the self-imposed daily caps.

## State after this session

- No code or docs committed this session (investigation + plan only); this log is local.
- Build **not yet run** — scheduled for next session; all prerequisites met.
- Open: build the driver + run the first ~6h suite build (free path).
