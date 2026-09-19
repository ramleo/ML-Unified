# Plan: Client-side run-logging sweep + AI QA Test-Automation tool

Two independent pieces of work, planned here before building. Part A is small
and mechanical. Part B is a new tool with real design and safety decisions.

Status: **plan only — not yet built.** Written 2026-09-18.

---

## Part A — Finish client-side run-logging

### The problem
Backend-calling tools log every run automatically, because `trackedFetch`
(the wrapper around the network call) emits `run_success` / `run_error` with
latency. **Client-side tools make no network call**, so nothing emits a "run"
event — we only get `tool_open` / `tool_close`. So for a client-side tool we
know it was opened and for how long, but not how many analyses ran inside it.

### Root cause
There is no single choke point (like `fetch`) for a client-side "run". Each
tool's "run" is its own local action, so each needs a one-line manual call.
Only `text-to-sql`, `feature-selection`, `jwt-analyzer` and `secret-scanner`
do this today.

### Solution
1. Add a shared helper in `ml-portfolio/src/hooks/useAnalytics.ts`:
   ```ts
   export function trackToolRun(toolId: string, meta: Record<string, unknown> = {}) {
     incrementQueryCount(toolId);
     track(EV.QUERY_RUN, { meta: { tool: toolId, ...meta } });
   }
   ```
2. Call `trackToolRun("<id>")` at each client-side tool's run moment.

### Scope (client-side tools still missing run logging)
password-audit, keystroke-biometric-auth-risk, extension-permission-analyzer,
malicious-package-scanner, and the WebGL/webcam tools (depth-parallax, face-*,
gait-pattern-comparison, pose-vj-visuals, movement-form-comparison, etc.).
Verify each against its source before editing — some may already call the
backend and be covered.

### Guardrails
- `meta` carries **action facts only** (counts, category, alg) — **never** the
  user's pasted/typed input (no passwords, tokens, secrets, PII).
- Writes are already production-gated (`analyticsWritesEnabled`), so local runs
  won't pollute analytics.

### Verify
Run a couple of the edited tools on the live site, then confirm the `query_run`
rows land in the Supabase `events` table.

### Effort
~1 focused pass, one line per tool. Low risk. The larger, separate item is the
full `LOGGING_SPEC.md` vocabulary (upload, config_change, result_view) —
deferred.

---

## Part B — AI QA Test-Automation tool ("AI Test Author")

### Goal
A tool with **two modes**:
- **Mode 1 — Instructions:** the user types what to test in plain English; the
  tool generates a runnable test and (optionally) runs it.
- **Mode 2 — From a link:** the user gives a URL; the tool crawls it,
  **auto-derives candidate test cases, shows the user the list of what it will
  test, and only runs after the user confirms.**

Hard constraint: **must be free to operate** — free LLM providers + open-source
Playwright + free/bounded execution. No per-test paid API.

### Why we cannot fully replicate testRigor
Four blockers, all infrastructure, not skill:
1. **No execution infra at scale.** Real runs need persistent/cloud browsers.
   Vercel functions live 10–60s and can't hold a browser session; the HF free
   tier is one small container. No fleet for parallel real-browser runs.
2. **Arbitrary-URL execution is a security hole.** Running tests against any
   user URL server-side = SSRF (reaching internal addresses), abuse (using our
   infra to hammer third-party sites), and cost. This is the opposite of the
   project's locked-down origin policy.
3. **The moat is scale, not the parser.** testRigor's self-healing and AI
   element-location are proven over millions of runs across web/mobile/desktop/
   mainframe — years of infra and data.
4. **It's a stateful SaaS.** Saved suites, run history, scheduling, CI hooks —
   a full backend with accounts, not a stateless demo.

So the realistic tool **generates** tests with AI and **runs a bounded subset
safely**, and is honest that it is not a cloud test farm.

### Free architecture
- **Generation:** free LLM providers already wired in this project (Groq,
  Cohere free tiers). One call per generation, behind the existing budget cap.
- **Test framework:** Playwright (open-source, already used here for demo
  recording). Generated output = a runnable Playwright script (TS or Python).
- **Execution (optional):** a bounded, sandboxed Playwright run inside the
  existing HF Space container, or a GitHub Actions job (free minutes). Never a
  long-lived per-visitor browser.

### Mode 1 — Instructions → test (buildable, low risk)
1. User picks a target: the **project's own site** (default) or pastes steps
   only (no execution).
2. User types steps in plain English ("open pricing, click Sign up, expect the
   form").
3. LLM → a Playwright script with resilient role/text selectors + assertions,
   plus comments explaining choices (the "self-healing" idea, honestly framed).
4. Show the code with a copy button. Optional **Run** button executes it
   **only against the project's own site**, showing pass/fail.

### Mode 2 — Link → crawl → propose → confirm → run (the harder half)
1. **Accept a URL** and validate it (see Safety).
2. **Crawl a bounded set of pages** (cap pages + depth + time), collecting
   forms, links, buttons, headings.
3. **Derive candidate test cases** from the DOM + an LLM pass, e.g. "the login
   form rejects an empty password", "the nav links all return 200", "the search
   box returns results".
4. **Show the user the list** of proposed tests, plainly. **Nothing runs yet.**
5. **On explicit confirm**, run the bounded subset and report pass/fail.

### Safety — the non-negotiable part of Mode 2
Executing against a user URL is where the risk lives. Required controls:
- **Ownership or allow-list.** Prefer: only test a domain the user has
  **verified they own** (e.g. a meta-tag / DNS token check), OR restrict Mode 2
  to a small allow-list including the project's own domains.
- **SSRF guard.** Reject URLs resolving to loopback / private / link-local
  ranges; re-check after every redirect; block egress to internal ranges.
- **Read-mostly + caps.** GET-style checks by default; hard caps on pages,
  depth, total time; respect `robots.txt`; a clear user-agent.
- **Rate + budget limits.** Reuse the existing rate-limit + budget modules.
- **No stored credentials.** Never accept a login to a third-party site.

If verified-ownership is too heavy for v1, ship Mode 2 **against the project's
own site only** and label it as such — still a real demo, zero risk.

### Decisions (locked 2026-09-18)
1. **Target:** start with the **project's own site only**; add other sites
   later, behind ownership verification / allow-list (Phase 4).
2. **Output language:** **Playwright TypeScript** — matches the site's language,
   Playwright's best-supported language, and Node/Playwright is already set up
   here. (Python only if tests ever move next to the FastAPI backend.)
3. **Flow:** **generate the tests first, then ask "Run these?" — run only on an
   explicit yes**, against the own site, bounded.

Build starts **2026-09-19**.

### Phased build
- **Phase 1 (MVP): SHIPPED 2026-09-19.** Mode 1 — user types plain-English steps
  → free-LLM → runnable **Playwright TypeScript**, shown with a copy button.
  Generation only, no execution. Backend `POST /qa-test-author/generate`
  (cohere→mistral free cascade, budget-capped, rate-limited; ML-Unified
  `8af0689`, HF-uploaded + verified serving). Frontend `/tools/qa-test-author`
  in a new **Developer Tools** area (ml-portfolio `b50b080`). Verified
  end-to-end on the live site: the production UI generates valid Playwright TS
  with resilient role/text/testId locators and real assertions.
- **Phase 2:** after generating, show a **"Run these?"** prompt; on yes, execute
  the script **against the project's own site only** (bounded HF / GitHub
  Actions runner) and show pass/fail.
- **Phase 3:** Mode 2 — give the own-site URL → crawl (bounded) → propose test
  cases → user confirms → generate + run, still **own-site only**.
- **Phase 4:** allow other sites, gated by ownership verification / allow-list
  and the full SSRF controls above.
- **Phase 5:** **root-cause failure grouping + bulk fix** (see the section
  below). Needs Phase 2 execution in place first, because grouping operates on
  real run results.

### First-day (2026-09-19) scope
Phase 1 only: the tool page + a "describe your test" box + a free-LLM endpoint
that returns a Playwright TS script + copy button. No execution yet. Confirm it
generates sensible tests for a couple of the site's own pages, then move to the
"Run?" prompt in Phase 2.

### Feature: root-cause failure grouping + bulk fix (Phase 5)
Requested 2026-09-19. This is a real testRigor feature: when many tests fail,
testRigor **groups all the cases affected by the same underlying issue and lets
you fix them in place all at once**, instead of showing N separate red failures
for one broken thing. We should do the same.

**The problem it solves.** One broken thing (a renamed button, a moved route, a
changed label) makes every test that touches it fail. A flat list of 12 red
tests hides that it's really *one* defect in 12 places — you fix it 12 times, or
miss some.

**What we build.**
1. **Group failures by root cause, don't list them flat.** After a run, cluster
   the failures by a deterministic *failure signature* — the failing
   locator/selector, the step text, the error kind (element-not-found vs
   assertion-mismatch vs navigation/HTTP error), and the target URL. Failures
   with the same signature are one **issue**. An LLM pass then writes a one-line
   plain-English cause ("the 'Sign up' button was renamed to 'Get started'").
2. **Show one issue, list every place it hit.** The UI shows **"1 issue,
   affecting 12 tests"** with the 12 locations expandable underneath — not 12
   top-level failures. (This is exactly the screenshot the user described.)
3. **Fix all in one click.** Because we own the generated Playwright TS, a fix is
   a concrete edit — usually a corrected selector or step. Apply the proposed
   fix to **all** affected locations at once (a scoped find/replace across the
   generated suite, or, better, tests referencing a **shared locator/helper
   module** so one edit heals all of them — the "self-healing" idea, done
   honestly and visibly). Show a diff, then re-run the affected subset to
   confirm the group goes green.
4. **Or fix them one by one.** Same proposed fix, but each location has its own
   Accept / Skip / Edit, so a partial or per-case correction is possible when
   the group isn't truly uniform.

**Honest limits (state these in the tool).**
- Grouping is reliable for the **common case** — one selector/route/label broke
  and many tests share that exact signature. It will **not** perfectly cluster
  coincidentally-similar-but-unrelated failures; the plain-English cause is an
  LLM suggestion to confirm, not a proven diagnosis.
- "Fix" here means **updating the generated test** (selector/step/assertion) to
  match reality — it does **not** fix the application. If the app genuinely
  broke, the right action is a bug report, and the UI must not let a one-click
  test edit paper over a real regression. So each group offers **"update the
  tests"** *and* **"this looks like a real bug"** as distinct choices.
- A one-click bulk edit is only safe because we run against our **own** generated
  suite and re-run to verify; never apply blind edits without the confirming
  re-run.

### testRigor feature audit — what is feasible for us
Reviewed testRigor's public **Features** page + docs on 2026-09-19. The app
itself (`app.testrigor.com`) is behind a login and could **not** be inspected
directly — this audit is from their public feature list, not the running app.
Every listed capability is mapped to our constraints: **free**, **Playwright
TypeScript**, **own-site-first**, bounded HF / GitHub-Actions execution, no
device farm.

**Feasible — build these (roughly in priority order):**
- Plain-English → Playwright TS test generation via a free LLM. [Phase 1]
- Generate tests from a pasted documented test case, or from a prompt. [Phase 1]
- Crawl an own-site URL → propose test cases → confirm → run. [Phase 3]
- **Record-and-playback** as a third input mode (from Katalon's "object spy"):
  click through the own site, Playwright's built-in `codegen` records the
  actions into a script, then an LLM pass rewrites brittle selectors into
  resilient role / text / accessible-name locators.
- **Import API tests from an OpenAPI / Swagger spec or a Postman collection**
  (from Katalon) → generated Playwright API-request tests, no infra needed.
- Root-cause failure grouping + one-click / one-by-one bulk fix. [Phase 5]
- Screenshots, video, and trace of every run — native Playwright. [Phase 2]
- **Reusable Rules** → emitted as reusable helper / Page-Object functions.
- **Stored values / variables** + predefined vars (e.g. today's date) → fixtures.
- Conditional steps + loops ("until") → generated control flow.
- **Data-driven testing** from a user CSV → Playwright parametrized tests.
- **Visual / screenshot comparison** → Playwright `toHaveScreenshot` snapshots.
- **Accessibility testing** → `@axe-core/playwright` (open-source).
- **API testing / validation** → Playwright request context against own endpoints.
- Retries for flaky tests + scheduling → Playwright retries + GH Actions cron.
- Interactions: tables, forms, multi-tab, iFrame, Shadow DOM, cookies /
  localStorage / session, geolocation, JS execution, file upload — all native.
- Unique test-data generation (format / regex) → a small generator helper.
- HTML report + our own results view. [Phase 2]
- Sitemap-crawl → screenshot PDF of the own site (Playwright screenshots → PDF).
- CI/CD via **GitHub Actions** (already used in this project).

**Partially feasible — bounded / honest version only:**
- **Self-healing:** not Vision-AI at their scale. We can re-locate a broken
  element by role / text / accessible-name and **propose** a fix (visible,
  confirmed), tied into the Phase 5 grouping. Honest assistance, not magic.
- **Parallel execution:** yes, but limited by one free runner — not "full
  regression in under 15 minutes" across a fleet.
- File validation (PDF / Word / Excel), OCR (Tesseract.js), audio / video
  checks: possible but heavy — add later, per need, own-site only.
- Load testing: only a small bounded burst, not real load.
- Production monitoring: scheduled own-site runs + free Slack / email posting;
  no PagerDuty-grade alerting or SLAs.
- App-level **TOTP** 2FA for our own site via a TOTP library — but **not**
  SMS / phone 2FA.
- Import from TestRail / Jira / Zephyr: doable via their APIs *if* the user has
  an account + key; otherwise just paste the test case in.

**Not feasible — needs infra / scale / paid services we don't have:**
- 3,000+ browser / device / OS combinations via LambdaTest / BrowserStack /
  SauceLabs (paid device farm). We get local Chromium / Firefox / WebKit only.
- Native **mobile** (iOS / Android) and native **Windows desktop** testing
  (device / desktop farms).
- **Mainframe** testing; Chrome-extension testing (niche).
- **Email deliverability / rendering**, **SMS & phone-call** flows via Twilio
  (paid communications infrastructure).
- Compliance certifications (SOC 2, HIPAA, ISO 27001, 21 CFR Part 11,
  GDPR / CCPA controls) — these are organisation / product certifications, not a
  feature we build.
- testRigor's own **Claude Code MCP / Skills** integration — that's their
  product hook, not something we reproduce.

**Net:** the core testRigor value — plain-English authoring, generation, stable
selectors, screenshots / video, reusable rules, data-driven runs, visual + a11y
checks, retries / scheduling, and root-cause grouping with bulk fix — is all
feasible on our free stack **for our own site**. What we cannot match is the
breadth of platforms (mobile / desktop / mainframe), the paid device-farm scale,
and the communications / compliance surface.

### Note
This is QA / test-automation, **not** a cybersecurity tool — it would live as
its own tool, separate from the security suite.

### References
- Stagehand (Playwright + AI, OSS): https://github.com/browserbase/stagehand
- Playwright: https://playwright.dev
- Open-source AI test generation (2026): https://getautonoma.com/blog/open-source-ai-test-generation-tools-2026
- SSRF-safe headless fetching: https://modpagespeed.com/blog/air-gapped-headless-fetch-ssrf-pinning/
- testRigor — grouping affected cases + fixing them at once: https://testrigor.com/blog/lessons-to-learn-from-your-failing-test-suites/
- testRigor — root cause analysis: https://testrigor.com/blog/root-cause-analysis-explained/
- testRigor — Features (public list, audited 2026-09-19): https://testrigor.com/features/
- testRigor — Documentation: https://testrigor.com/docs/
- Katalon Studio — Features (audited 2026-09-19): https://katalon.com/web-testing-dg
- Playwright codegen (record-and-playback): https://playwright.dev/docs/codegen
