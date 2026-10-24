# TC-P17 — Parts 300–309

**Prefix:** TC-P17
**Parts covered:** 300–309 (10 sessions; Part 307 is inside the Part 306 file, no separate 307 log)
**Status:** ✅ Complete
**Method:** Inline — no subagents; full line-by-line re-read of all session logs.

Covers: the logging-vocabulary activation (steps 1–6 + gap-closers + per-tool feature tracking); the 502 worker-starvation root cause and the Mistral-removal fix; observability (DIY error store + Sentry); the upload/LLM security hardening (malware block-everywhere, prompt-injection flag+log, decompression bombs, prompt-hardening); and the long Testwright maturation arc — Run perf, Stop/cancel, self-heal grounding, Discover grounding, deterministic locator disambiguation, the grounded-action gate, generation seeing destination pages, the verify-repair loop, the syntax guard, and the durable/interactive dashboard.

---

## Logging Activation + Feature Tracking (Parts 300–301)

### TC-P17-001
**Category:** Feature
**Test Name:** Client-side tools emit a content-free run event
**Steps:**
1. Run a client-side tool (JWT/secret/phishing/password-audit).
**Expected Result:** `trackToolRun` fires `query_run`; live-as-you-type tools debounce 1.2s (per settled edit, not keystroke); password-audit logs a content-free run (no password, not even the breach outcome) so the privacy page stays true.
**Automation Hint:** telemetry assertion.
**Source:** Part300 (`fcdd28e`)

### TC-P17-002
**Category:** Architecture
**Test Name:** Coverage grep includes all run-event signals and shared components
**Steps:**
1. Audit which tools emit run events.
**Expected Result:** Real gap was 11 not 16 — `feature-engineering`/`preprocessing` emit `run_success` directly and `automl` via shared `AutoMLModal`; `malicious-package-scanner`'s `fetch(` match was sample-code text (pure client-side). Read the match, don't count it.
**Automation Hint:** none (method).
**Source:** Part300

### TC-P17-003
**Category:** Feature
**Test Name:** guide_open / tool_card_click / citation_click wired per their real shape
**Steps:**
1. Open a guide modal, click a tool card, open a citation.
**Expected Result:** `guide_open` via a per-modal hook (44 near-identical copies, no shared base); `tool_card_click` once in shared `ToolCard.handleNavigate` (`{tool,source,opens}`); `citation_click` on open only (`{tool,index,kind}`, no cited text); `result_expand` is N/A (no expandable interaction to attach it to).
**Automation Hint:** telemetry per event.
**Source:** Part300 (`4c7e998`/`1d2fadd`/`705c3a6`)

### TC-P17-004
**Category:** Bug-Regression
**Test Name:** The 502s were worker-starvation, not OOM
**Steps:**
1. Diagnose browser 502s on `/rag/mm-ingest` while `/health` is 200.
**Expected Result:** Space logs show no crash/restart and every ingest that reached the app returned 200 → the 502s are HF-proxy responses for requests that never got a worker; `/document/analyze` held the single worker ~4s failing on Mistral (429 then 403 `tier_not_allowed`) before Cohere ran. The logs beat the "OOM" inference.
**Automation Hint:** none (method).
**Source:** Part301

### TC-P17-005
**Category:** Bug-Regression
**Test Name:** Document auto-path drops always-failing Mistral
**Steps:**
1. Analyze a document; read `provider`.
**Expected Result:** Text path Cohere→Gemini, vision Gemini-only — Mistral removed from the auto cascade AND the simple/fast tier (it 429/403'd on every call, ~4s dead time); still BYOK-selectable. Not a swap — removal of dead config, with the user's OK.
**Automation Hint:** live analyze.
**Source:** Part301 (`3889bd6`)

### TC-P17-006
**Category:** Feature
**Test Name:** Remaining log vocabulary wired centrally, content-free
**Steps:**
1. Load a sample, paste text, retry after an error, scroll.
**Expected Result:** `sample_load` (per-tool); `paste_input` one global listener, length bucket only (password excluded); `run_retry` derived centrally in `track()` (a run after that tool's prior error); `scroll_depth` one global hook (25/50/75/100); `error` global window handler (class+source, no message/stack); new `feedback{tool,rating}` from the RAG thumbs.
**Automation Hint:** telemetry per event.
**Source:** Part301 (`89f5726`/`b9d2a3f`)

### TC-P17-007
**Category:** Feature
**Test Name:** Feature tracking is one `feature_use` event + properties (RPC dashboard)
**Steps:**
1. Use a bespoke control; view the feature-usage panel.
**Expected Result:** One delegated listener reads `data-wt`/`data-ev` → `feature_use{tool,control,action,value?}` (not one event per control — the event-explosion anti-pattern); reuses the 232 existing `data-wt` anchors; the dashboard reads a server-side `GROUP BY` RPC (`feature_usage.sql`), never pages raw rows (highest-volume event).
**Automation Hint:** telemetry + dashboard integration.
**Source:** Part301 (`1fbc07e`/`9a0a333`)

---

## Observability + Security Hardening (Part 302)

### TC-P17-008
**Category:** Feature
**Test Name:** DIY error store captures frontend + backend, content-free, no Space DB key
**Steps:**
1. Trigger a browser error and an unhandled router exception.
**Expected Result:** Both POST to one `/api/error` (browser direct; backend `error_capture_dispatch` middleware best-effort posts then re-raises so Sentry + 500 still apply); grouped by `source:kind:route`; query stripped, password page excluded; no Supabase key on the Space.
**Automation Hint:** inject both; assert stored + grouped.
**Source:** Part302 (`d715db1`/`40a6f53`)

### TC-P17-009
**Category:** Bug-Regression
**Test Name:** needs_setup detection reads the Postgres error code
**Steps:**
1. Query a table before its migration runs.
**Expected Result:** Detected via `error.code` (PGRST205/202) + message (Supabase says "Could not find … in the schema cache", not "does not exist") — in both `/api/error` and `/api/feature-usage`.
**Automation Hint:** unit test the detector.
**Source:** Part302 (`325b82b`)

### TC-P17-010
**Category:** Feature
**Test Name:** Malicious uploads are blocked at every upload boundary
**Steps:**
1. Upload an EICAR/embedded-PE/webshell file to any upload route; upload a benign file.
**Expected Result:** 400 via `gate_or_raise()` — 27 advisory callers converted to blocking + 8 unscanned routers gated; advisory heuristics (entropy) still only log so legit files aren't falsely rejected; `mm_malware_image` + `mm_ingest` left as-is.
**Automation Hint:** API test EICAR vs benign.
**Source:** Part302 (`4517b09`)

### TC-P17-011
**Category:** Feature
**Test Name:** Prompt injection in uploaded text is flagged + logged, not blocked
**Steps:**
1. Ingest a doc containing override/jailbreak phrasing.
**Expected Result:** `prompt_gate` logs content-free `prompt_injection_flagged{direct_override,jailbreak}` yet still processes (a legit doc can contain such phrasing); benign → clean. Plus `build_system_prompt` leads the chunk block with an untrusted-data rule.
**Automation Hint:** API test flagged vs clean.
**Source:** Part302 (`549624e`/`073843a`)

### TC-P17-012
**Category:** Feature
**Test Name:** Decompression bombs and pixel limits are enforced
**Steps:**
1. Upload a 20KB .docx that unzips to 20MB (ratio ~1000); load a huge image.
**Expected Result:** 413 via `zip_bomb_check` (a .docx is a zip); PIL/OpenCV pixel cap (~64MP) set in `app.py` before cv2/PIL import; mm-ingest's 20MB declared cap added to `body_size` route caps (the global 10MB had shadowed it).
**Automation Hint:** API tests for bomb + pixel cap.
**Source:** Part302 (`dd19f1c`)

### TC-P17-013
**Category:** Bug-Regression
**Test Name:** Testwright Run slowness is CI setup, not the test
**Steps:**
1. Time a trivial Testwright run.
**Expected Result:** ~68s wall-clock but the test ran ~0.9s — ~99% is GitHub-runner setup; the container image helps modestly (~50–56s) but ephemeral runners re-pull the ~2GB image, so download is the floor (a warm runner is the only real lever; measured, not the predicted ~10–20s). Result now shows `test 0.9s · total 55.8s`.
**Automation Hint:** none (measurement).
**Source:** Part302 (`5ee9264`)

### TC-P17-014
**Category:** Feature
**Test Name:** Testwright Stop cancels the GitHub job; self-heal grounds locators verbatim
**Steps:**
1. Stop a running test; heal a stale-locator failure.
**Expected Result:** `cancel_run()` hits GitHub's cancel API (not just the client poll); heal requires every locator string copied verbatim from the ARIA snapshot and uses role locators (a search box → `getByRole('searchbox',{name:<exact>})`, not a guessed placeholder) — grounding beats "don't hallucinate".
**Automation Hint:** cancel + heal e2e.
**Source:** Part302 (`970d8f3`/`21fc8c6`)

---

## Testwright Discover + Deterministic Locators (Part 303)

### TC-P17-015
**Category:** Bug-Regression
**Test Name:** Self-heal stages a fix (no auto-run)
**Steps:**
1. Fail a run; click "Suggest a fix".
**Expected Result:** Healed code staged in the editor with a diff + "Re-run healed test"/"Discard" — no auto-fired ~50s CI cycle on a possibly-bad fix.
**Automation Hint:** heal e2e, assert no auto-run.
**Source:** Part303 (`2911264`)

### TC-P17-016
**Category:** Bug-Regression
**Test Name:** Discover grounds code-generation in the page (link→href map)
**Steps:**
1. Discover-generate a nav test.
**Expected Result:** Generation gets the ARIA snapshot + a link accessible-name→href map (`ariaSnapshot()` has no hrefs → URLs were guessed, e.g. clicking the logo and asserting `/ai-airaml`); URL assertions use the real href, in-page `#` anchors assert a visible result not a URL.
**Automation Hint:** assert generated code uses the real href.
**Source:** Part303 (`30c1d62`)

### TC-P17-017
**Category:** Bug-Regression
**Test Name:** Multi-test suites aren't mislabeled flaky
**Steps:**
1. Run a 7-test file (1 pass, 6 fail, runs=1).
**Expected Result:** "Failed", not "Flaky · 7 runs" — flakiness only when `num_tests==1 and total_runs>1` (`_count_tests` counts distinct spec titles; `expected+unexpected` also sums across different tests).
**Automation Hint:** multi-test single-run assertion.
**Source:** Part303 (`4364cc4`)

### TC-P17-018
**Category:** Bug-Regression
**Test Name:** Locator disambiguation is deterministic (both ambiguity classes)
**Steps:**
1. Generate a nav test with names like 'Tools', 'Handbook'.
**Expected Result:** `_disambiguate_locators` post-processes from real per-element counts (ARIA snapshot lists EVERY element — don't dedupe into a set) — a substring over-match ('Tools' inside 'Browse the tools') → `{exact:true}`; an identical duplicate (nav+footer 'Handbook') → `.first()`; unique names untouched. Playwright name match is substring by default.
**Automation Hint:** `locators` unit test both classes.
**Source:** Part303 (`e9eab55`/`a694015`)

### TC-P17-019
**Category:** Feature
**Test Name:** Discover persists results + visible round-trip from Run
**Steps:**
1. Discover → Generate → Send to Run → Back to Discover.
**Expected Result:** Proposals + page_context cached in `sessionStorage` (restored client-only, no SSR mismatch); Run shows a "Sent from Discover … still there" banner + "← Back to Discover"; "Send all N to Run" merges drafts into one file (single import + single BASE_URL).
**Automation Hint:** round-trip e2e.
**Source:** Part303 (`82b648d`/`4be6961`/`618c9e7`)

---

## Verify-Repair Loop + Destination-Page Grounding (Parts 304–305)

### TC-P17-020
**Category:** Feature
**Test Name:** Generated tests have no hard waits; self-heal removes invented assertions only
**Steps:**
1. Generate a test; heal one with an invented `getByText` presence check and one with a value mismatch.
**Expected Result:** `page.waitForTimeout` stripped + web-first asserts (R1); heal removes a presence assertion that fails not-found AND whose target is absent from the snapshot, but NEVER a value mismatch (Expected/Received differ) — an honest bug still fails.
**Automation Hint:** heal unit tests both shapes.
**Source:** Part304 (`af5e1cb`/`127a1fc`/`ddb3239`)

### TC-P17-021
**Category:** Bug-Regression
**Test Name:** A compound card link is located by stable href, not accessible name
**Steps:**
1. Generate a test clicking the "Security & Trust" category card.
**Expected Result:** `locator('a[href="/tools/security-trust"]')` — the card `<a>`'s accessible name concatenates all 25 nested tool names and changes with CSS reveal state, so any name locator is non-deterministic; shared-label hrefs (`/#capabilities` for two labels) keep the name; nav+footer dupes get `.first()`.
**Automation Hint:** href-grounding unit test.
**Source:** Part304 (`d038de6`/`b87efef`/`cc75539`)

### TC-P17-022
**Category:** Feature
**Test Name:** Auto-fix verify-repair loop (run → heal → re-run)
**Steps:**
1. Seed a test with an invented assertion; click Auto-fix & re-run.
**Expected Result:** ≤2 passes run→heal→re-run until pass or heal can't fix it — generation is BLIND (one-shot snapshot vs live page), so execution is the ground truth; the loop fixes mechanics + removes invented checks, a real value mismatch still fails.
**Automation Hint:** auto-fix e2e.
**Source:** Part304 (`5393fcd`)

### TC-P17-023
**Category:** Efficiency
**Test Name:** Merged suites run in parallel (244s → ~94s)
**Steps:**
1. Run a 13-test merged suite.
**Expected Result:** `fullyParallel:true` + `workers:3` (2-vCPU sweet spot) in `qa-run.yml`.
**Automation Hint:** timing.
**Source:** Part304 (`d0727008`)

### TC-P17-024
**Category:** Bug-Regression
**Test Name:** Generation sees the destination pages (deep explore default)
**Steps:**
1. Discover-generate a multi-page suite.
**Expected Result:** Deep explore ON by default visits ≤12 same-origin pages (parallel, chunks of 4), each captured as title + visible h1–h3; prompt asserts each page's REAL heading (`===PAGE <url>===`), never a guessed class/heading — live-proven 3/3 green first run. Band-aid prompt rules were the symptom; loading the page is the fix.
**Automation Hint:** assert real-heading assertions.
**Source:** Part305 (`957d197`/`f07324b`)

### TC-P17-025
**Category:** Bug-Regression
**Test Name:** A link's accessible name excludes aria-hidden decoration
**Steps:**
1. Build the Discover link map for a category card whose first child is `<span aria-hidden>` of tool names.
**Expected Result:** Label = the accessible name (aria-hidden excluded), matched on an alphanumeric-normalized form so `"Security & Trust26 tools"` == `"…Trust 26 tools"`; textContent ≠ accessible name.
**Automation Hint:** link-map unit test.
**Source:** Part305 (`c155804`)

### TC-P17-026
**Category:** Bug-Regression
**Test Name:** Junk/wildcard locators are stripped; raw href locators get `.first()`
**Steps:**
1. Generate code containing `name:'*'` and a raw `locator('a[href="#capabilities"]')`.
**Expected Result:** `strip_junk_locators` drops the wildcard step (29.5s timeout); `first_on_href_locators` appends `.first()` to any raw href locator matching >1 link; extracted to `locators.py`.
**Automation Hint:** `locators` unit test.
**Source:** Part305 (`95748eb`)

### TC-P17-027
**Category:** Architecture
**Test Name:** "Shipped" means committed + deployed + proven
**Steps:**
1. Verify a claimed-shipped Discover UX feature.
**Expected Result:** The timer/Select-all existed only in the working tree (` M`, never committed) — a prior summary's "shipped" was wrong; check git, trust git.
**Automation Hint:** none (process).
**Source:** Part305 (`7bf4a3e`)

---

## Grounded-Action Gate + Live Predictor (Parts 306–307)

### TC-P17-028
**Category:** Bug-Regression
**Test Name:** Dashboard shows the test-case pass rate, not run pass rate
**Steps:**
1. View the dashboard gauge with 28/50 tests passing across 14 runs.
**Expected Result:** 56% (test-case), with the per-run metric relabeled "all-green run rate" (was a misleading 7% counting whole runs as failed if any test fails).
**Automation Hint:** dashboard metric check.
**Source:** Part306 (`ec8db2b`)

### TC-P17-029
**Category:** Feature
**Test Name:** The grounded-action gate drops ungrounded interactions, never assertions
**Steps:**
1. Generate tests that click page text as a button and fill a dynamic placeholder.
**Expected Result:** `action_gate.drop_ungrounded_actions` parses the `===CONTROLS===` allow-list (real interactive elements, accessible name, aria-hidden excluded) and drops any `test()` whose interaction (incl. variable-based locators) targets a non-control; assertions untouched; if all tests drop, the model cascade retries. An anti-hedge guard rejects `// Placeholder`/"in a real test" output.
**Automation Hint:** `action_gate` unit test on the failing shapes.
**Source:** Part306 (`310254e`/`d6030c0`)

### TC-P17-030
**Category:** Feature
**Test Name:** Per-test visibility names which test failed and why
**Steps:**
1. Run a 10-test suite with 2 failures.
**Expected Result:** `run_report.py` parses each spec's title/status/duration/error from `results.json` → a "Tests (N) — X passed · Y failed" list with each failure's own error inline (old UI showed only the first error).
**Automation Hint:** per-test parse test.
**Source:** Part306 (`d6030c0`)

### TC-P17-031
**Category:** Bug-Regression
**Test Name:** A submit/predict test asserts a knowable state change, not an always-true check
**Steps:**
1. Generate a predictor test (pick model → Fill Sample → Predict).
**Expected Result:** Ends with `expect(getByText('Fill in the fields and click Predict')).toBeHidden()` (rule 10c) — not `getByRole('main').toBeVisible()` (true before prediction). Verified on the live app: the empty-state text stays in the DOM but becomes `offsetParent:null` (present ≠ visible), so `toBeHidden()` is correct, a `count===0` check would be a false-RED. `MAX_CONTROLS` 40→60 so real CTAs aren't crowded off the list.
**Automation Hint:** assert the state-change assertion is generated.
**Source:** Part307/in-306 (`4ed2a48`)

---

## Measure-First, Durable Dashboard, Syntax Guard (Parts 308–309)

### TC-P17-032
**Category:** Feature
**Test Name:** Learn-from-edits ships measurement only (Phase 0)
**Steps:**
1. Save a generated test you changed.
**Expected Result:** Content-free `TEST_EDITED` (changed-line count + locator/assertion/other booleans, assertion-precedence so an `expect()` wrapping a locator counts as assertion) — no code/host/text; Phase 1 gated on whether corrections stay frequent. Don't build the feedback loop on a guess.
**Automation Hint:** telemetry assertion.
**Source:** Part308 (`dbb1082`)

### TC-P17-033
**Category:** Bug-Regression
**Test Name:** Deep-crawl heading capture filters to VISIBLE headings
**Steps:**
1. Generate a handbook test.
**Expected Result:** Doesn't assert `heading 'The AIRaML Handbook'` (exists but `offsetParent:null` in the print/PDF layer) — capture filters by `getBoundingClientRect` size + visibility. Present ≠ visible; verified on the live page before encoding.
**Automation Hint:** heading-capture unit test.
**Source:** Part308 (`af68989`)

### TC-P17-034
**Category:** Bug-Regression
**Test Name:** A misread locator name is repaired, never dropped (assertions safe)
**Steps:**
1. Generate `name:'PDF for print (AA)'` when the real control is "PDF for print (A4)".
**Expected Result:** `repair_ungrounded_names` rewrites to the real captured name when exactly one close match exists (difflib cutoff 0.86) — repairs (safe on assertions), never drops; the action-gate drops interactions but never assertions, so a misread name in an `expect()` needs repair.
**Automation Hint:** repair unit test on AA→A4.
**Source:** Part308 (`49b6ca1`)

### TC-P17-035
**Category:** Feature
**Test Name:** Durable cross-device run history + interactive dual-view strip
**Steps:**
1. Log runs across browsers; open the dashboard.
**Expected Result:** `qa_runs` table (content-light, RLS service-role; one-time migration; `needs_setup` until run) via `/api/qa-run/log` + `/stats` shaped like `HistoryEntry` so one `computeDashboard` serves both; a "This device ↔ All runs" toggle; a [Runs|Tests] outcome strip (captioned, hover tooltips, click a run bar → inline per-test breakdown).
**Automation Hint:** dashboard integration + migration smoke.
**Source:** Part308 (`4bfd4f1`/`0acf47d`)

### TC-P17-036
**Category:** Bug-Regression
**Test Name:** Directional href tiers resolve a truncated run-on name
**Steps:**
1. Generate `getByRole('link',{name:'ML Unified PlatformPlatform · Enter…'})`.
**Expected Result:** Rewritten to `a[href="/ml"].first()` — `href_link_locators` uses DIRECTIONAL tiers (exact → map-starts-with-code → code-starts-with-map → substring); the model usually truncates, so map-starts-with-code wins uniquely (one combined tier tied between the /ml card and a shorter sibling).
**Automation Hint:** href-tier unit test.
**Source:** Part308 (`86bf7eb`)

### TC-P17-037
**Category:** Bug-Regression
**Test Name:** A model punctuation typo doesn't fail the whole spec
**Steps:**
1. Heal produces `getByRole('searchbox', { name. 'Search…' })`.
**Expected Result:** `sanitize_option_punctuation` repairs `{ key. literal }` → `{ key: literal }` (known option keys, literal value only, real method chains untouched); `looks_syntactically_valid` (balanced brackets outside strings/comments, defines `test(`) gates output → fall through to the next provider rather than ship a zero-test spec reported as "No tests found". Runs in both Author and Heal.
**Automation Hint:** `validate`/`locators` unit tests incl. the exact broken line.
**Source:** Part309 (`918103b`)

### TC-P17-038
**Category:** Architecture
**Test Name:** Fix the class, don't swap Heal to the paid model
**Steps:**
1. Consider using Gemini for Heal.
**Expected Result:** Kept on the free cascade — Gemini is the only paid key and `/qa` is public (every visitor's "Suggest a fix" would bill); any model can typo, so the deterministic sanitizer/validator is the provider-independent fix. An off-line 2-call Gemini comparison (not wired in) confirmed it's stronger but two samples aren't proof of immunity; decision unchanged.
**Automation Hint:** none (decision).
**Source:** Part309

### TC-P17-039
**Category:** Architecture
**Test Name:** Reds were the generated tests' wrong assumptions, verified live
**Steps:**
1. Investigate "ML Unified Platform → HF Space" and "search malware → category visible" reds.
**Expected Result:** The platform link opens a new tab (`target="_blank"`) so a same-tab `toHaveURL` can't pass (needs popup capture); the category link exists at rest but disappears when you type (search swaps the grid). The tests asserted wrong states — not a regression from the grounding commits.
**Automation Hint:** none (method).
**Source:** Part309

### TC-P17-040
**Category:** Feature
**Test Name:** Grounding heuristics (laws vs advice) for new-tab/print/button
**Steps:**
1. Generate tests touching a new-tab link, a print button, a filter button.
**Expected Result:** The `[download]` marker (a LAW — `<a download>` only) lets the model tell a real download from a print button; rules 10e (a filter/toggle button doesn't navigate — no `toHaveURL`) and 10f (print never fires `download`) are ADVICE (prompt heuristics); the syntax guard + Heal are the safety net. Be explicit which fixes are guaranteed vs heuristic.
**Automation Hint:** none (design).
**Source:** Part309 (`e119d8c`)

### TC-P17-041
**Category:** Bug-Regression
**Test Name:** Dashboard labels numbered tests and scopes aggregates correctly
**Steps:**
1. View a run of unnamed tests + the Top-Failing/Flaky panels.
**Expected Result:** Tests numbered `Test 1, Test 2…` (was falling back to the run name "Untitled test · Untitled test"); a skipped proposal says why ("no groundable element, skipped"); Top-Failing/Flaky captioned "across all runs in view — not the selected bar" (they're history-wide aggregates).
**Automation Hint:** dashboard assertions.
**Source:** Part309 (`c371fe7`)

---

## Cross-cutting / Process (Parts 300–309)

### TC-P17-042
**Category:** Architecture
**Test Name:** HF `RUNNING_APP_STARTING` serves the old container — verify stage==RUNNING
**Steps:**
1. Probe the Space right after an upload.
**Expected Result:** The first post-upload probe hit stale code (bit twice in one session); confirm `stage==RUNNING` (not `RUNNING_APP_STARTING`) before testing; Vercel deploy lag is likewise real (API route deploys before the static bundle).
**Automation Hint:** none (method).
**Source:** Parts300/303

### TC-P17-043
**Category:** Architecture
**Test Name:** Each AI-generated run surfaces the next failure class — fix classes, not instances
**Steps:**
1. Iterate Testwright generation against the live site.
**Expected Result:** Strict-mode href → wildcard names → unstable card names → invented assertions → interactions → syntax — fixed as deterministic laws (sanitizer, gate, disambiguation, href grounding) with heal/auto-fix as the net; never promise "last class ever"; the count stays flat when the cause moves (peel every layer).
**Automation Hint:** none (method).
**Source:** Parts304–309

### TC-P17-044
**Category:** Architecture
**Test Name:** When the user says search online, search online (don't patch from reasoning)
**Steps:**
1. Face a recurring Testwright failure class.
**Expected Result:** The research (Octomind/Checkly/Playwright-MCP) confirmed the plain-logic fix — only act on interactive elements, load the page and read it — rather than another prompt band-aid.
**Automation Hint:** none (method).
**Source:** Parts305/306

---

**Total: 44 test cases, Parts 300–309.**
