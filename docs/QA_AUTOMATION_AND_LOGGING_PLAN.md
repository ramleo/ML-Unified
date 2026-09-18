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
- **Phase 1 (MVP):** Mode 1 — user types plain-English steps → free-LLM →
  runnable **Playwright TypeScript**, shown with a copy button. Generation only,
  no execution. Frontend tool + one free-LLM endpoint. Lowest risk, fully free.
- **Phase 2:** after generating, show a **"Run these?"** prompt; on yes, execute
  the script **against the project's own site only** (bounded HF / GitHub
  Actions runner) and show pass/fail.
- **Phase 3:** Mode 2 — give the own-site URL → crawl (bounded) → propose test
  cases → user confirms → generate + run, still **own-site only**.
- **Phase 4:** allow other sites, gated by ownership verification / allow-list
  and the full SSRF controls above.

### First-day (2026-09-19) scope
Phase 1 only: the tool page + a "describe your test" box + a free-LLM endpoint
that returns a Playwright TS script + copy button. No execution yet. Confirm it
generates sensible tests for a couple of the site's own pages, then move to the
"Run?" prompt in Phase 2.

### Note
This is QA / test-automation, **not** a cybersecurity tool — it would live as
its own tool, separate from the security suite.

### References
- Stagehand (Playwright + AI, OSS): https://github.com/browserbase/stagehand
- Playwright: https://playwright.dev
- Open-source AI test generation (2026): https://getautonoma.com/blog/open-source-ai-test-generation-tools-2026
- SSRF-safe headless fetching: https://modpagespeed.com/blog/air-gapped-headless-fetch-ssrf-pinning/
