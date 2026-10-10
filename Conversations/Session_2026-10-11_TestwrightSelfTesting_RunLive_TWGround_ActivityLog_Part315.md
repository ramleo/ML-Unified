# Part 315 — Testwright self-tests the site: Run Live, TW-GROUND, and the Activity Log

Continues [Part 314](Session_2026-10-09_ObservabilityO6_AgentSpans_PageInspectorCoverage_Part314.md).
2026-10-10/11. Started with a handbook chapter + two audits, then turned Testwright on our
OWN site — which exposed a stack of authoring bugs (each fixed and generalised), drove a
new "Run Live" local-execution feature, and ended with a HuggingFace-style Activity Log.

Through-lines:
- **Use the product on itself and the gaps show themselves.** Testing our 63 pages with
  Testwright surfaced 5 real authoring defects + one observability gap — none visible from
  the outside.
- **"author-failed" is not one thing.** It was, variously: the daily budget cap (429 before
  provider selection), and a genuine validator bug — never assume; read the logs.
- **A "no" is a trigger to dig, not an answer.** The user's standing rule now
  ([[feedback_no_dead_ends_search_web]]): when stuck, search/debug to ground truth, then report.

---

## Arc 1 — handbook + audits
- **Handbook Ch17** gained an "observability layer" section (O1–O6 story) + 2 interview
  questions (`ml-portfolio 936af5e`). The handbook had zero coverage of the whole arc.
- **Platform audit** (5 platforms) and **tool audit** (58 tools): all live + wired — pages,
  thumbnails, breadcrumbs, backends, 200s. Only finds were a dead `ML_ANALYTICS_API` config
  + a stale homepage comment (`ml-portfolio 4f52930`). Method: cross-check registries vs
  filesystem vs live OpenAPI vs live HTTP; the "missing" endpoints were regex false-positives.

## Arc 2 — Testwright self-testing (Phase 1)
Drove the QA API directly (`/qa/discover → /qa/author/generate → /qa/run/execute`, poll) to
test ~29 UI-happy-path targets. Final: **28/28 in-scope green** (feature-selection → Phase 2,
needs upload). **Key correction:** most "author-failed" results were the **author daily cap
(429)**, *not* bugs — the cap check runs BEFORE provider selection, so even Gemini can't
bypass it; the unblock is raising `QA_TEST_AUTHOR_DAILY_CAP` (set via `HfApi.add_space_variable`),
not switching model. Gemini is paid + its key isn't in local `.env` (Space-secret only), so
it was never a usable shortcut here anyway. [[project_llm_provider_status]]

## Arc 3 — Run Live (Phase-2 MVP) — watch tests on your own machine
The user wanted to *see* tests run (like the Playwright VS Code ▶). **A website can't launch
a browser on the user's machine (sandbox)** — so headful needs a small local process. Built
the **Testwright Companion** (`ml-qa-runner/companion/`, `aad6259`): a `127.0.0.1` daemon
(`GET /health`, `POST /run`) that runs the authored spec `--headed` locally and returns
pass/fail; CORS locked to the Testwright origins, target host allow-listed. Frontend "Run
Live" button detects it and routes there (`ml-portfolio a1e0daa`); CI stays the headless
default. Design confirmed against Checkly/Playwright/Cypress — all run a local CLI/app for
live view; the cloud runs headless. MVP = run companion once then click; later = packaged
installer (zero-typing) + noVNC is the only path to live view on a *cloud* runner.

## Arc 4 — TW-GROUND: five stacked authoring bugs on one adversarial page
sql-app (`/tools/text-to-sql`) kept failing; each fix revealed the next layer. **All five are
general robustness wins, not one-off patches.** Backend commits are HF-uploaded.

| # | Bug | Fix | Commit |
|---|---|---|---|
| 1 | Guessed `'Run'` + shortened placeholder (SPA renders controls after async load → Discover captured none → gate no-op → LLM guessed) | `discover.py` network-idle settle before `grabControls`; `prompts.py` `10c-ready` wait | `ad07f63` |
| 2 | First-load **tour overlay** hid the input on a fresh browser (`ml_sql_walked` unset) | `discover.py` `_overlay_hint` (`===DISMISS===`); `prompts.py` `10d-overlay` non-fatal dismiss-first | `0289623` |
| 3 | Navigated to `/sql` (landing) not the given `/tools/text-to-sql` — rule 2 invited `goto(BASE_URL + '<path>')` | rule 2: open the provided base_url **verbatim** | `c860301` |
| 4 | Grounded author returned **empty** when context had no specific heading | rule 10: generic `getByRole('heading').first()` fallback, never empty | `70c9f5d` |
| 5 | **Validator rejected any locator name ending in `.`** — `_OPT_KEY_DOT_LEFT` scanned INSIDE strings, so `name: '… get a prediction.'` false-matched `word.'` → "unparseable" → both providers fail → empty | `validate.py` `_blank_strings` before the option-key-dot check (regression guards: real `{name.` typo + brace imbalance still rejected) | `636b39b` |

**Bug #5 was the real blocker** behind the ml/eda/vision landing "author-failed", and it
silently broke **every** sentence-style heading site-wide. Found by **reading the Space run
logs** (`/api/spaces/{id}/logs/run`) — added a content-free "head of rejected code" log
(`author.py`, kept) to see the actual output instead of guessing (my first two guesses —
tour, regex-brackets — were both wrong; the logs settled it). Local reproduction was blocked
(stale Cohere key in `.env.local`), so the log-and-read loop was the path.

## Arc 5 — Activity Log (the "0 errors hides failures" gap)
The user wanted an HF-style log: *see everything — ok, warning, 429, in-band 200-failure*.
The Errors panel only logs app crashes + 500s, so recovered failures (the 23 mistral 429s)
showed as "0 errors". Built a unified **Activity Log** (`ml-portfolio 7f66d67`):
`/api/activity` merges `llm_calls` (ok/warn/429/error, via status + http_status) + `errors`
into one chronological feed; `AnalyticsActivityLog.tsx` renders it newest-first with
All/Warnings/Errors filter chips and **clickable rows** that expand to full detail (provider
error envelope, http, tool, trace id). Live-verified: 144 ok / 23 warn-429 / 0 error today.

## Arc 6 — Activity Log, round 2: the 200-with-broken-payload gap + UX
A dashboard screenshot showed `Errors 0` while authoring was visibly failing. Two
distinct problems, both fixed:

**6a — the real blind spot (backend, `ML-Unified 4d2d5dc`, HF-uploaded).** When a
provider returns bad code, the **HTTP call still succeeds (200)**, so `call_log`
records it as `ok`. The validator rejects the code a moment later *inside the author
route*, and that rejection went only to the Space's throwaway run buffer — never to
`llm_calls`. So the "200-with-a-broken-payload" case the whole Activity Log was built
for was itself invisible. Fix: `author.py._log_reject()` now logs every in-band
rejection (non-test output / hedge / no-grounded-test / unparseable) as a content-free
row — `status=error, http=422, error_code=output_rejected, op=qa-author` — with the
reason + a short head of the generated code (test code, never user data). The four
reject sites in `generate_test()` each call it before falling through to the next model.
Diagnosis was debug-first: traced the flow `author → deps.complete → rag/llm.complete →
instrument()` and saw `instrument` logs `ok/200` on any successful HTTP, confirming the
rejection never reached the DB.

**6b — three UX defects (frontend, `ml-portfolio d6a4802`).** The user did not want to
click to see what's wrong, and filtering jumped the page. Verified clickability live
first (a row *did* expand — it only *looked* dead because every row was a green `ok`
with no interesting detail). Fixes in `AnalyticsActivityLog.tsx`:
1. **Reasons inline, no click** — warning/error rows (`level !== "ok"`, so the new 422
   rows included) print their reason + http/tool/trace inline; OK rows stay one line.
2. **No scroll jump** — the list moved into a **fixed-height scroller** and rows are no
   longer nulled on a filter change, so switching All/Warnings/Errors never resizes the
   card. Root cause: the old `if (rows === null) return null` unmounted the whole card on
   every filter click → page collapsed up then re-mounted back.
3. **`· N err` is a link** — the LLM panel's error badge now dispatches an
   `airaml:activity-focus` window event; the log listens, sets the Warnings filter and
   `scrollIntoView`s. Cross-component with no shared store.

**Lesson:** an "ok" from the transport layer is not an "ok" from the application. The
logger sat at the HTTP funnel (right place for provider errors) but the *usefulness*
check happens one layer up, so that layer has to emit its own failure row.

## Key decisions / lessons
- **Read the logs before theorising.** The validator bug was invisible to reasoning; the raw
  rejected code named it instantly. [[feedback_debug_first]] [[feedback_status_claims_need_evidence]]
- **Classify a failure before "fixing" it.** Budget cap vs provider contention vs real
  defect look alike (all "author-failed") and have different fixes.
- **Headful = a local process, by browser design.** Any "watch it live" feature needs a
  companion/CLI/extension; the web app alone cannot.
- **An error panel that only logs crashes under-reports.** A 200-with-failed-payload or a
  recovered 429 is a failure the operator should see — merge the call log, don't rely on the
  errors table. [[project_page_error_log_coverage]]
- **A validator is code too** — its own false-positive silently broke valid output for days.

## Commits
| Repo | Commits |
|---|---|
| ML-Unified (Testwright backend, HF) | `ad07f63` v1 · `0289623` v2 · `c860301` base_url · `70c9f5d` heading-fallback · `636b39b` validator-fix + diagnostic · `4d2d5dc` log in-band author rejections |
| ml-portfolio | `936af5e` handbook obs · `4f52930` config/copy cleanup · `a1e0daa` Run Live button · `7f66d67` Activity Log · `d6a4802` Activity Log inline reasons + no-jump + err-badge link |
| ml-qa-runner | `aad6259` local Companion |

## Open / next
- **Phase 2 proper:** fixtures + fake-media so the ~34 upload/camera tools (incl.
  feature-selection) are testable; Run-Live packaged installer; optional VS Code extension.
- Caps left: run 60, discover 40, author 60. `author.py` rejected-code diagnostic is a keeper.
- The Testwright plan doc has R11/R12 (v1) but not v2/base_url/fallback/validator/Activity-Log.

Related: [[feedback_no_dead_ends_search_web]], [[feedback_debug_first]],
[[project_page_error_log_coverage]], [[project_llm_provider_status]],
[[project_testwright_qa_platform]], [[project_testwright_run_perf]].
