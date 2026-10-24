# Part 331 — gitignore cleanup, provider-cascade consolidation, and test cases for Parts 250–330 (2026-10-24)

Continues Part 330 (homepage chat grounded-RAG rework + its follow-up). This session
had four threads: committing the stray `.gitignore` edits, answering an AI-gateway
question, a behavior-preserving backend refactor (the duplicated LLM-judge cascades),
and the big one — generating the missing test cases for **Parts 250–330**.

Through-line: **check memory/evidence before asserting** — the session's one real
fumble (the HF deploy path) happened precisely because I trusted a stale CLAUDE.md
line instead of the memory that already had the answer.

---

## 1. "nothing pending?" → the `.gitignore` loose end

The user pushed back on an earlier "nothing pending." Checking the working trees found
`M .gitignore` uncommitted in **both** repos — pre-existing, not this session's:
- **ml-portfolio** ignores `docs/ACCESS_AND_AUTH.md`
- **ML-Unified** ignores `docs/prd/` + `docs/SECURITY_REFERENCE.md`

Verified the ignored files are **not tracked** (`git ls-files` empty), so they were
never pushed and aren't at risk either way. Committed on the user's go-ahead (explicit,
per the ask-before-commit rule):
- ml-portfolio **`49aa239`**, ML-Unified **`776757c`** — docs-local-only ignore rules.

A cwd race (both commits sent in parallel) left ML-Unified's uncommitted on the first
try; caught it (`git status` still showed `M`) and recommitted cleanly.

**`supabase/eval_online.sql` confirmed done** by the user → updated
[[project_platform_roadmap]] (the `/eval` "Online quality" section is now live;
Q4 fully complete incl. the online-eval migration).

---

## 2. AI-gateway question — we deliberately use none

User asked whether we use an AI gateway like Bifrost. Grep-confirmed **zero** gateway
deps (Bifrost/LiteLLM/Portkey/OpenRouter/Cloudflare AI Gateway). We've rolled our own
lightweight equivalent: `complete()` in `routers/qa/deps.py` (BYOK vs free cascade),
provider fallback cascades, `llm_calls` telemetry, budgets, rate limits, RAG caching.

Answer: **no need now** — a gateway would mostly consolidate what we already do, and a
managed one conflicts with the content-free privacy posture (routing prompts through a
third party); a self-hosted one adds a service to an ephemeral HF Space. The only real
cleanup it implied became thread 3. Saved [[project_provider_cascade_consolidation]].

---

## 3. Provider-cascade consolidation (ML-Unified `4a00957`, +HF)

The duplicated JUDGE cascade across three fixed-server-key tools
(`prompt_injection_check.py`, `ai_code_detector.py`, `siem_triage.py`) — each carried an
identical provider list + resolve-key/call/parse/fall-through loop.

- Extracted to **`routers/judge_cascade.py`** (`run_judge_cascade` + `JUDGE_CANDIDATES`
  = cohere→mistral→groq). Each tool now delegates, keeping only its own system prompt +
  parser. **Net −117 lines.**
- **Scope held deliberately:** only the 3 genuinely-identical judge cascades. The
  GENERATION cascades (`document/_llm.py`, `rag/generation.py`, `eda/_suggest.py`,
  `tenant_rag.py`) were left alone — different semantics (BYOK, paid-last, streaming)
  and pinned by `tests/test_provider_cascade.py`. Documented this in the new module so
  no one folds them in later.
- **Behavior-preserving, verified:** cascade mechanics (first-wins/no-extra-calls,
  empty-falls-through, all-fail→None, exception→continue), prompt-injection's exact
  `(verdict, judge_ran)` tuple, siem's count-guard closure parser, and all telemetry
  `tool=` tags — proven with stubbed providers (the full pytest suite needs backend deps
  the local env lacks; no test covers these modules anyway). Then verified **live** on
  all 3 endpoints after the Space rebuilt (prompt-injection risk=low/judge_ran=True,
  ai-code assessment=inconclusive, siem 1 verdict/priority=high).
- CI green (run 40071297221). `judge_cascade.py` 80 lines; all files < 400.

### The deploy fumble (the lesson of the session)

The HF upload step stalled: CLAUDE.md says "token from `git remote get-url hf`," but the
remote is now a **plain tokenless URL**; no `HF_TOKEN` env, no HF cache. I wrongly
concluded the token was *missing* and handed the user a 4-option menu — when I'd simply
been **blocked from reading** the credential, not shown it was absent.

The real mechanism: the token lives in the **macOS keychain** (`osxkeychain` helper —
the same credential that authenticates the tokenless GitHub `origin` push). This was
**already documented in [[reference_hf_deploy]]** (dated 2026-09-29) with the exact
`git credential fill` → Python upload recipe. I didn't check memory first. Once I used
that recipe, all 4 files uploaded cleanly.

**Lesson:** check `reference_hf_deploy` before deploying; "I can't read the credential"
≠ "the credential is gone." Memory refreshed with the keychain confirmation.

---

## 4. Test cases for Parts 250–330 — Round 8 (ML-Unified `9341be0`)

The user asked where the test-case effort stood. Memory was stale (110 days, stopped at
TC-P8); the live index (`Conversations/testcases/testcases.md`, last touched 2026-08-24)
showed **Parts 1–249 covered, ~1351 TCs across 17 files**, and flagged its own gap:
Parts 250+ had no coverage. The project had since run to **Part 330** (~80 logs).

User chose **batches of 10 parts per file, full line-by-line re-read**. Done inline (no
subagents, per the standing TC-generation practice — and Rule 2: never spawn parallel
agents to write near-identical docs). Mapped part→filename first (no Part 307 file; Part
282 split a–d; Part 307 content lives inside the Part 306 file).

**447 new test cases across 8 files**, each `TC-P<N>-###` with
Category/Steps/Expected/Automation-Hint/Source, tracing to a commit where one exists:

| File | Parts | TCs | Spine of the range |
|---|---|---|---|
| TC-P12 | 250–259 | 94 | logging audit, search-bar bug, theme audit, FFT stego/moiré, PRNU, EC-001→008, Groq removal, deepfake, domain NER, +new CV/security tools |
| TC-P13 | 260–269 | 73 | cybersecurity sprint, app-safeguard `security/` layer + CORS/rate-limit bugs, product/CV split, tools rebuild, globals.css split + 400-line CI gate, handbook-as-book + 50 deep chapters |
| TC-P14 | 270–279 | 66 | demo markers + 2x-speed, return-to-position, clip audit + recorder rebuild, 3 shipped backend bugs (/models 500, drift baseline, CatBoost), the provider audit, logging + security_log + Turnstile |
| TC-P15 | 280–289 | 54 | frontend Playwright/vitest suites, test phases, ml-eda fold-in, numpy-2/pandas-3/opencv-5 migration, repos public (AGPL), the E9–E21 security sweep (RCE, DuckDB read, key leak, SSRF), a11y/CWV |
| TC-P16 | 290–299 | 42 | last clips + fade, six security tools + registrations, Testwright platform build, Text-to-SQL→platform, native worlds + app reskin, TECH_STACK, secret sweep, token leak, handbook rebuild + MMRAG clear-out |
| TC-P17 | 300–309 | 44 | logging activation + feature tracking, 502 worker-starvation, observability O1–O3a, the Testwright grounding/verify-repair/syntax-guard progression |
| TC-P18 | 310–319 | 40 | model selection (owner+BYOK) + monitoring, CI rescue, doc-coverage gate, observability O1–O6 + ts-column bug, Run-Live Companion, Phase-2 fixtures + volatile-control taxonomy, click audit |
| TC-P19 | 320–330 | 34 | ClamAV/hybrid-gate hardening, the full roadmap (Q5 auth, Q1 API, Q2 MCP, Q4 eval, Q3 chatbot builder→Stripe), site-search + chat chips, grounded-chat rework |

Index updated: **25 files, ~1798 TCs, Parts 1–330, no gaps**; Round 8 added to the
generation history; the stale "beyond 249" closing note corrected to 330. Committed
docs-only (`9341be0`, 9 files, +4,430 lines) — no code, no HF.

Caught and corrected a stray `<br>` typo in TC-P18 before committing.

---

## Commits

| Repo | Commit | What |
|---|---|---|
| ml-portfolio | `49aa239` | gitignore: local-only `ACCESS_AND_AUTH.md` |
| ML-Unified | `776757c` | gitignore: local-only `prd/`, `SECURITY_REFERENCE.md` |
| ML-Unified | `4a00957` | refactor: judge cascades → `routers/judge_cascade.py` (+HF, verified live) |
| ML-Unified | `9341be0` | docs(testcases): TC-P12→TC-P19, Parts 250–330 (447 cases) |

No ml-portfolio code changed beyond the gitignore; the only HF deploy was `4a00957`
(4 `.py` files via the keychain token, verified live after rebuild).

---

## Lessons

- **Check memory before deploying/asserting.** `reference_hf_deploy` already had the
  keychain recipe; trusting the stale CLAUDE.md line cost a detour and a bad options-menu.
  "Blocked from reading a credential" is not "the credential is gone."
- **Refactor only what's genuinely identical.** The 3 judge cascades were; the 4
  generation cascades weren't (BYOK/paid-last/streaming, test-pinned) — left alone and
  documented so the boundary is explicit.
- **Prove a behavior-preserving change preserves behavior** — stubbed-provider cascade
  tests + the exact `(verdict, judge_ran)` tuple + live checks on all 3 endpoints, not
  "it compiles."
- **A deliberate "we built our own" is worth recording** — no AI gateway, by design;
  the only cleanup it implied (DRY the judge loop) is now done.
- **Close a coverage gap the index itself flags.** The testcases index had named the
  Parts-250+ gap; Round 8 closed it end to end, file by file, verifying the part→log
  mapping (307 gap, 282a–d) rather than trusting the sequence.

## State after this session

- Both repos' working trees clean; all four commits pushed.
- Test-case coverage: **Parts 1–330, ~1798 TCs, no gaps.**
- Deferred (unchanged, demand-gated / user's): Q2 M3 OAuth 2.1+PKCE, Q3 M4c Stripe
  Connect reseller, go-live billing (live Stripe keys / India account).
- Optional low-priority: the generation cascades remain separate by design — no action
  unless a gateway or cross-provider semantic caching is ever wanted
  ([[project_provider_cascade_consolidation]]).
