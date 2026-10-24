# TC-P15 — Parts 280–289

**Prefix:** TC-P15
**Parts covered:** 280–289 (10 sessions; Part 282 split a–d)
**Status:** ✅ Complete
**Method:** Inline — no subagents; full line-by-line re-read of all session logs incl. 282a–d.

Covers: the last handbook clips + their tool bugs; the frontend's first Playwright/vitest suites and the 6 heading-less pages; the backend test phases (deterministic shell + nightly golden evals); the ml-eda fold-in (3 live bugs) and the self-origin 403; numpy-2/pandas-3/opencv-5 migration fallout; the repos going public (AGPL) and the name-collision + "Mastercard" scope findings; and the big security sweep E9–E21 (server-key leak via `baseUrl`, pickle RCE via `joblib.load`, DuckDB file-read, SSRF, unauthenticated DELETE, cost caps, provider auth-failure alerting) plus the WEBSITE_GUIDELINES a11y/CWV pass.

---

## Last Clips + Their Tool Bugs (Parts 280–281)

### TC-P15-001
**Category:** Bug-Regression
**Test Name:** Prompt-injection judge falls back Cohere→Mistral; reports judge_ran
**Steps:**
1. Call `/prompt-injection/check` while Mistral is rate-limited.
**Expected Result:** Cohere answers (risk=high, `judge_ran=True`); Gemini excluded (only paid key, public endpoint); frontend states "judge unreachable", not "no server key configured".
**Automation Hint:** API test with Mistral stubbed 429.
**Source:** Part280 (`cd7f985`)

### TC-P15-002
**Category:** Bug-Regression
**Test Name:** Citation panel never shows "Used in answer — no" when it can't tell
**Steps:**
1. Ask a question answered by paraphrase (no 4-gram overlap).
**Expected Result:** `likely_used_indices()` empty array (`[]` is truthy) no longer renders a confident "no"; anchor prefers a bboxed used citation → any bboxed → any used → first card.
**Automation Hint:** unit test the index resolution + UI assertion.
**Source:** Part281 (`15b9332`)

### TC-P15-003
**Category:** Bug-Regression
**Test Name:** text-to-sql connect panel shows the real table/row counts
**Steps:**
1. Open the DB connect panel for the demo DB.
**Expected Result:** 15,607 rows across 11 tables (was hardcoded `11 tables · ~3.5k rows` — the Track table alone).
**Automation Hint:** UI assertion vs schema endpoint.
**Source:** Part281 (`8d69ec9`)

### TC-P15-004
**Category:** Bug-Regression
**Test Name:** Document cascade reaches a working free provider before the paid key
**Steps:**
1. Analyze a document; read `provider`.
**Expected Result:** Served by Cohere (`command-a-03-2025`) — reorder alone didn't fix it because the file asked for retired `command-r-plus` (404) and Cerebras 401→402 (free account, no service); Cerebras dropped from cascade, kept selectable; `_provider_map` now includes it.
**Automation Hint:** live analyze; assert non-Gemini provider.
**Source:** Part281 (`a24e583`/`94ddb05`/`e60d7b0`)

### TC-P15-005
**Category:** Bug-Regression
**Test Name:** "Verify number" only compares same-figure captions
**Steps:**
1. Analyze a doc with `65.8` (caption) vs `65.8%` (OCR), and a page with a % chart + a £ table.
**Expected Result:** No false flag — `_caption_page` takes `scoped=`, only the cropped-region caller flags; a genuine 42-vs-24 misread still fires.
**Automation Hint:** unit test 5 cases incl. the true misread.
**Source:** Part281 (`94660be`)

### TC-P15-006
**Category:** Bug-Regression
**Test Name:** Every tool page renders a heading element
**Steps:**
1. Load all 51 tool routes; assert a heading exists.
**Expected Result:** All have one — 6 modal-wizard pages rendered their title as a styled `<span>` → `<h1>` (same look); a `NO_HEADING_YET` guard fails if the list grows.
**Automation Hint:** Playwright smoke test over filesystem-derived routes.
**Source:** Part281 (`0bcd734`/`0444fb7`)

### TC-P15-007
**Category:** Bug-Regression
**Test Name:** secret-scan (gitleaks) has PR-commit read scope
**Steps:**
1. Open a PR; run CI.
**Expected Result:** Job-scoped `permissions` grants reading PR commits (was 403 "Resource not accessible" → every PR red, main green; 8 Dependabot PRs stuck); PR comments stay disabled (Dependabot token is read-only).
**Automation Hint:** CI check on a PR.
**Source:** Part281 (`03865f4`)

---

## Backend Test Phases (Part 282a)

### TC-P15-008
**Category:** Architecture
**Test Name:** Phase 3 deterministic-shell suite (165 tests, providers stubbed)
**Steps:**
1. Run the ml-api suite.
**Expected Result:** Covers cascade order/fallback/missing-keys, budget caps at the boundary, 8 schemas + normalizer, validation rules, security gates — no provider ever called; proven failable (planting Gemini-first + budget `>`→`>=` reddens 13 tests).
**Automation Hint:** pytest + mutation probe.
**Source:** Part282a (`299350b`)

### TC-P15-009
**Category:** Bug-Regression
**Test Name:** Origin allowlist regex doesn't match slashes/colons
**Steps:**
1. Send `Origin: https://evil.com/?next=https://x.vercel.app`.
**Expected Result:** 403 — host part is `[A-Za-z0-9.-]+\.vercel\.app` (was `.*\.vercel\.app`, which `.*` let through); real preview subdomains still 200.
**Automation Hint:** origin-policy unit test.
**Source:** Part282a

### TC-P15-010
**Category:** Feature
**Test Name:** Nightly golden evals check by property; paid-provider-serving is a hard failure
**Steps:**
1. Run the 6-golden eval against the Space.
**Expected Result:** Values match by property (`1180`/`1,180.00`/`$1,180.00` all pass); no field count asserted; a run served by the paid key fails even if values are perfect (free providers ahead are dead); PDFs generated per run with a unique footer ref (the analyzer caches on bytes).
**Automation Hint:** eval harness run (free providers).
**Source:** Part282a (`c27d609`)

---

## ml-eda Fold-In + Self-Origin (Parts 282b–c)

### TC-P15-011
**Category:** Bug-Regression
**Test Name:** EDA returns 200 with `kurtosis: null` on a short numeric column
**Steps:**
1. POST a CSV with a numeric column of <4 non-null values.
**Expected Result:** `json_safe()` at the response boundary emits `null` (pandas gives NaN kurtosis for 3 points; JSON can't carry NaN → old ml-eda Space 500'd, with a passing `/health` and 35 green tests because every fixture was large enough).
**Automation Hint:** API test with a 5-row CSV.
**Source:** Part282b (`a0108ec`)

### TC-P15-012
**Category:** Bug-Regression
**Test Name:** EDA `/eda/suggest` has a free-first capped cascade
**Steps:**
1. Call suggest with no provider.
**Expected Result:** Free first, paid last, budget cap + LLM rate limit, names the provider that answered (was pinned to a retired Cohere model, defaulted to the rate-limiting provider, offered the paid key uncapped).
**Automation Hint:** API test.
**Source:** Part282b

### TC-P15-013
**Category:** Bug-Regression
**Test Name:** A bad clean-config returns 400 (not a 500 masquerading as CORS)
**Steps:**
1. POST `/eda/clean` with a wrong-shape config.
**Expected Result:** 400 naming the offending key (an unhandled 500 is produced outside the CORS middleware → browser reports a CORS error, hiding the real cause).
**Automation Hint:** API test on malformed config.
**Source:** Part282b

### TC-P15-014
**Category:** Bug-Regression
**Test Name:** The Space's own served page can call its own API
**Steps:**
1. POST from the Space's own origin (`?mode=eda` upload).
**Expected Result:** 200 — `_self_origins()` reads `SPACE_HOST`/derives from `SPACE_ID` (a same-origin POST still carries an `Origin` header; the Space's origin wasn't allowlisted → 403); one exact origin, not a `hf.space` wildcard; other Spaces stay 403.
**Automation Hint:** API test from each origin.
**Source:** Part282c (`d30d6b4`)

### TC-P15-015
**Category:** Architecture
**Test Name:** A service nobody calls is unmonitored, not dormant
**Steps:**
1. Review the old ml-eda Space state.
**Expected Result:** It was up, `/health` ok, 35 tests green, and 500ing on ordinary input — nothing referenced it so no user hit it; checking the thing you changed (`ML_EDA_URL` repoint) is not the same as using it (open the page).
**Automation Hint:** none (lesson).
**Source:** Part282c

---

## Layout + Migration Fallout (Parts 282d–283)

### TC-P15-016
**Category:** Bug-Regression
**Test Name:** Heatmap SVG is sized to its viewBox (labels not giant)
**Steps:**
1. Render the correlation heatmap.
**Expected Result:** `width`/`height` pinned to the viewBox with `maxWidth:100%` (a viewBox-only SVG fills its container and scales 10px text to ~60px).
**Automation Hint:** measured rendered text height.
**Source:** Part282d

### TC-P15-017
**Category:** Bug-Regression
**Test Name:** A wide table scrolls itself, not the page (`min-width:0`)
**Steps:**
1. Load a page with a 760px-min table at narrow width.
**Expected Result:** No sideways page scroll — grid/flex items get `minWidth:0` (they default to `min-width:auto` and won't shrink below content, so the table's own scroller never engaged).
**Automation Hint:** Playwright overflow check.
**Source:** Part282d

### TC-P15-018
**Category:** Bug-Regression
**Test Name:** numpy-2 ABI is exercised by an import test (spacy 3.8)
**Steps:**
1. Import the 11 compiled-extension deps; assert numpy is 2.x.
**Expected Result:** `test_native_abi.py` passes — thinc's pre-compiled C broke on numpy 2 (`dtype size changed`); fixed by `spacy>=3.8.0` (thinc≥8.3.12). CI stayed green for hours because nothing imported spacy.
**Automation Hint:** the ABI import test.
**Source:** Part283

### TC-P15-019
**Category:** Bug-Regression
**Test Name:** Dark PDF text is legible (print-color-adjust in the host stylesheet)
**Steps:**
1. Generate a dark EDA/handbook report PDF.
**Expected Result:** Text readable — `print-color-adjust: exact` + text color live in the host document stylesheet (Paged.js rewrites/rescopes its own input and drops the declaration; `@media print`/computed-style checks pass while the print rasterizer still darkens — only a rendered PDF reproduces it).
**Automation Hint:** render a PDF (not emulateMedia).
**Source:** Part283

### TC-P15-020
**Category:** Bug-Regression
**Test Name:** Non-numeric columns are left intact, not coerced to NaN
**Steps:**
1. Predict with a row carrying a categorical (cabin letter / region).
**Expected Result:** `coerce_numeric()` is all-or-nothing via try/except (pandas 3 removed `errors="ignore"`; `errors="coerce"` would silently blank categoricals → the model predicts from nothing, a wrong answer not an error).
**Automation Hint:** unit test with a mixed-type column.
**Source:** Part283

---

## Repos Public + Collisions (Part 284)

### TC-P15-021
**Category:** Architecture
**Test Name:** Public+licensed source satisfies AGPL §13 (going public is the fix)
**Steps:**
1. Confirm both repos public (ML-Unified AGPL-3.0, ml-portfolio MIT) with a source link from the app.
**Expected Result:** AGPL §13 needs network users to obtain source — private+hosted can't; the exposure was from being private. 3 Ultralytics models (incl. `signature-detector` YOLO11s) documented in THIRD_PARTY.md.
**Automation Hint:** none (compliance).
**Source:** Part284

### TC-P15-022
**Category:** Architecture
**Test Name:** ml-api and ml-vision modules don't collide on import
**Steps:**
1. Run `pytest services/` (both suites in one interpreter).
**Expected Result:** No cross-import — ml-vision's `app.py`/`shared/progress.py` renamed `vision_app`/`vision_shared` (both owned generic names; only one `app`/`shared.progress` can win → 7 visible failures + 400 meaningless passes asserting the wrong app). Evicting from `sys.modules` made it worse (61 failures).
**Automation Hint:** full-suite run.
**Source:** Part284

### TC-P15-023
**Category:** Architecture
**Test Name:** EDA assistant answering off-topic is a scope gap, not a jailbreak
**Steps:**
1. Ask "what is mastercard?" in the EDA assistant with/without a relevant upload.
**Expected Result:** Scope follows what was RETRIEVED, not keywords — with no relevant upload it declines, with a Mastercard briefing uploaded it answers cited to the upload. `build_system_prompt()` had no decline rule; not a keyword blocklist.
**Automation Hint:** live upload/no-upload test.
**Source:** Part284

### TC-P15-024
**Category:** Architecture
**Test Name:** Read all of a check's output, not just the last line
**Steps:**
1. Run `check-file-length.sh` / a gitleaks failure proof / an SSE probe.
**Expected Result:** `tail -1` hid a real failure (baseline pinned a renamed file → 868-line violation); the gitleaks "can it fail" proof must use a non-allowlisted token (AWS's example key is allowlisted); an SSE probe reading `ev['token']` printed blanks and populated the cache → `cache_hit=True` next run (read only `cache_hit=False` results).
**Automation Hint:** none (method).
**Source:** Part284

---

## Security Sweep E9–E21 (Parts 285–287)

### TC-P15-025
**Category:** Bug-Regression
**Test Name:** Vercel build skips `standalone` output (adapter crash)
**Steps:**
1. Build on Vercel (adapter injected) vs Docker.
**Expected Result:** `output: process.env.VERCEL ? undefined : "standalone"` — Next 16.3.x + any adapter crashes `onBuildComplete`/standalone trace (`ENOENT .nft.json`); Docker still needs standalone. Reproduced locally with a no-op adapter.
**Automation Hint:** build both ways.
**Source:** Part285 (`b3c3029`)

### TC-P15-026
**Category:** Bug-Regression
**Test Name:** A caller-supplied `baseUrl` never receives a server key (E9)
**Steps:**
1. POST `/api/ai-tools` with `provider:"groq"` and `baseUrl` to an attacker host.
**Expected Result:** No `GROQ_API_KEY`/`GEMINI_API_KEY` sent — a caller URL only ever gets the caller's own key and must be https (was: `resolveKey` fell back to the server env key then `fetch(baseUrl)` with it — key exfil since the repo went public).
**Automation Hint:** local planted-key + listener proof.
**Source:** Part285 (`dc2bf19`)

### TC-P15-027
**Category:** Feature
**Test Name:** Vercel Hobby rate rule guards `/api/*` LLM+contact routes
**Steps:**
1. Fire 25 requests at an `/api/*` route.
**Expected Result:** 20/60s per IP, path operator "Is any of" (not "Contains", which would also throttle `/api/track`); `/api/news` unaffected; `contact` gets Turnstile + HTML-escaped email body.
**Automation Hint:** rate test with free (empty-body) requests.
**Source:** Part285 (`2790333`)

### TC-P15-028
**Category:** Bug-Regression
**Test Name:** Custom model upload accepts skops only (pickle RCE closed, E18)
**Steps:**
1. Upload a malicious pickle (`__reduce__`→`os.system`) and a skops file naming `builtins.eval` to `/shap/custom/upload`.
**Expected Result:** Both refused — only `.skops` with every type under an ML allowlist (sklearn/numpy/scipy/xgboost/lightgbm) loads; a genuine skops model round-trips. Was `joblib.load` → arbitrary code on the Space (API keys + HF write token).
**Automation Hint:** `skops_safe` unit test incl. a marker-file proof the payload never ran.
**Source:** Part286 (`a93a951`)

### TC-P15-029
**Category:** Bug-Regression
**Test Name:** DuckDB uploads can't read the Space's files (E10)
**Steps:**
1. Upload a CSV, then run `SELECT * FROM read_csv('/proc/self/environ')`.
**Expected Result:** "file system operations are disabled" — every upload is copied into a table, then `enable_external_access=false` + `lock_configuration=true` so caller SQL can't re-enable file access.
**Automation Hint:** `test_duckdb_conn.py` with a planted secret.
**Source:** Part286 (`20b3d74`)

### TC-P15-030
**Category:** Bug-Regression
**Test Name:** `/sql/connect` refuses private/metadata addresses (SSRF, E14)
**Steps:**
1. Connect to `169.254.169.254` / a loopback / private host.
**Expected Result:** Refused — `_conn_guard.py` allows only a single public https host (before the fix the metadata request hung ~20s actually reaching it).
**Automation Hint:** `test_conn_guard.py` (DNS mocked, 25 cases).
**Source:** Part286 (`14775fb`)

### TC-P15-031
**Category:** Feature
**Test Name:** ml-portfolio LLM routes cap cost + default free (E11–E13)
**Steps:**
1. Call `ai-tools`/`ai-explain`/`chat`.
**Expected Result:** Model restricted to the site's own tools, output/size/message-count caps, Cohere/free-first default; `ai-explain` gains Turnstile + a Groq→Cohere→Mistral→Gemini→Claude chain (free before billed).
**Automation Hint:** route cost-cap tests.
**Source:** Part286 (`180408f`/`5692b36`/`4e259ba`)

### TC-P15-032
**Category:** Architecture
**Test Name:** Both Spaces honor a BLOCKED_IPS variable (E17)
**Steps:**
1. Set `BLOCKED_IPS`; request from a listed IP.
**Expected Result:** Refused (HF has no firewall, browsers hit Spaces directly); shipped dormant.
**Automation Hint:** API test with the var set.
**Source:** Part286 (`7dcba14`)

### TC-P15-033
**Category:** Bug-Regression
**Test Name:** Local runs don't write to the live analytics tables
**Steps:**
1. Run an e2e/demo locally.
**Expected Result:** `/api/track` + `/api/security-log` skip writes unless `VERCEL` is set (`.env.local` holds prod Supabase keys → local runs polluted live data: 833/1000 rows no country, 182 keepalive `run_error`s from laptops pinging `localhost:8000`).
**Automation Hint:** assert no write without `VERCEL`.
**Source:** Part286 (`905cea9`)

### TC-P15-034
**Category:** Bug-Regression
**Test Name:** Analytics success reads run outcomes and pages past 1000
**Steps:**
1. Load the dashboard over 7 days of events.
**Expected Result:** Success from `run_success`/`run_error` (not stale `meta.success` on `query_run` after the 2026-09-06 rewrite → everything counted as failure); paginates past the 1000-event cap (count 1000→4801).
**Automation Hint:** dashboard integration test.
**Source:** Part286 (`b48bde4`)

### TC-P15-035
**Category:** Architecture
**Test Name:** A deploy-poll must refuse for free on BOTH old and new code
**Steps:**
1. Poll a route to detect a new deploy.
**Expected Result:** Use a request both versions refuse without a paid call (21 messages + a keyless provider) — a no-token probe ran against OLD code and spent the billed Claude/Gemini key 3×.
**Automation Hint:** none (method).
**Source:** Part286

### TC-P15-036
**Category:** Architecture
**Test Name:** Guard proofs become CI tests; ml-sql enters CI (E4)
**Steps:**
1. Run the new ml-sql suite + E18 test.
**Expected Result:** `test_duckdb_conn`/`test_conn_guard`/`test_providers`/`test_skops_safe` in CI (`test-ml-sql` job); each proven to fail against the pre-fix open (a plain `duckdb.connect()` leaks the planted secret).
**Automation Hint:** CI run.
**Source:** Part287 (`2192ccc`)

### TC-P15-037
**Category:** Bug-Regression
**Test Name:** Only the mislabeled download button is relabeled (.skops vs .pkl)
**Steps:**
1. Inspect Step4Results' two download buttons.
**Expected Result:** The winner's button serves `.skops` (export route, since E18) — relabeled; the action-bar button genuinely serves a joblib `.pkl` — left correct. (File split to `AutoMLAnalysisPanel.tsx` first, over the gate.)
**Automation Hint:** live header check on both routes.
**Source:** Part287 (`4dfce66`)

### TC-P15-038
**Category:** Bug-Regression
**Test Name:** Model DELETE requires an allowlisted Origin (E21, partial)
**Steps:**
1. `curl -X DELETE /models/{id}` with no Origin.
**Expected Result:** 403 (guard fires before lookup — a no-Origin DELETE of a nonexistent id is 403 on new vs 404 on old) — `origin_present_and_allowed`; named as partial (doesn't stop a forged Origin; worst case is a model that regenerates).
**Automation Hint:** `test_model_delete_origin.py`.
**Source:** Part287 (`af02fcc`)

### TC-P15-039
**Category:** Feature
**Test Name:** A dead free key is surfaced, not silently escalated to the paid key (E3)
**Steps:**
1. Make a 401/403 (dead key) vs a 429/5xx (transient) on an LLM route.
**Expected Result:** `isAuthFailure` flags only real auth failures → an `auth_failure` row in `llm_calls` + `PROVIDER_AUTH_FAIL` log, VERCEL-gated, throttled to 1/route/provider/10min; transient blips ignored.
**Automation Hint:** classifier test (8 auth vs 6 transient shapes).
**Source:** Part287 (`078d076`)

### TC-P15-040
**Category:** Feature
**Test Name:** robots.txt + sitemap exist; reduced-motion + focus + landmarks
**Steps:**
1. Fetch `/robots.txt` and `/sitemap.xml`; set `prefers-reduced-motion`; Tab the page; check `<main>`.
**Expected Result:** 58-URL sitemap from filesystem slugs; the canvas constellation draws one static frame under reduced-motion (the rAF loop had ignored the CSS); site-wide `:focus-visible`; exactly one `<main>` per tool page (53 pages).
**Automation Hint:** route fetch + axe + Playwright.
**Source:** Part287 (`e830ce3`/`618ee08`)

---

## Guidelines a11y/CWV + Clips as Integration Tests (Parts 288–289)

### TC-P15-041
**Category:** Bug-Regression
**Test Name:** Zero axe contrast violations on both themes
**Steps:**
1. Run axe on light and dark.
**Expected Result:** 0 — `--text3` retuned (dark `#7e8ca4`, light `#4d5a6d`); a `--link` token (≥4.5:1) for inline links; light theme also failed over the constellation lines (fixed by bolder dots + modest lines, the dots being the escape hatch axe rarely samples as text background).
**Automation Hint:** axe both themes incl. animated samples.
**Source:** Part288 (`a8090b1`/`fd21981`)

### TC-P15-042
**Category:** Bug-Regression
**Test Name:** Tool pages have a two-button back nav (Home + area), correctly keyed
**Steps:**
1. Load each tool page; check the back nav.
**Expected Result:** `<ToolBackNav>` gives Home→`/` plus the tool's area on all 53 pages; fixed 3 bugs — pipeline-cinema "Home" went to ML Pipeline; feature-engineering/selection mis-keyed (`featureeng`/`featureselect` vs route slugs) fell back to lone Home.
**Automation Hint:** SSR sweep — ≥2 correct links per page.
**Source:** Part288 (`6bd64b0`)

### TC-P15-043
**Category:** Efficiency
**Test Name:** Home Core Web Vitals (defer below-fold client components)
**Steps:**
1. Lighthouse (mobile) on home.
**Expected Result:** perf 66→100, LCP 4.2→1.6s, TBT 860→10ms — chatbot + 3 below-fold sections via `dynamic ssr:false`, hero + tool grid server-rendered (tool pages already 98–100). Use the warm-run median, not a cold-cache outlier.
**Automation Hint:** Lighthouse median of warm runs.
**Source:** Part288 (`f3a6426`)

### TC-P15-044
**Category:** Architecture
**Test Name:** `next/image` migration closed as not-needed by evidence
**Steps:**
1. Audit all `<img>`.
**Expected Result:** All are dynamic runtime images (blob/data/canvas — `next/image` can't optimize) or already optimized (`/thumbs/*.webp` lazy+async+sized); migrating adds image-opt requests for no gain.
**Automation Hint:** none (audit).
**Source:** Part288 (`cc4ba52`)

### TC-P15-045
**Category:** Architecture
**Test Name:** Frontend has unit tests (vitest) in CI
**Steps:**
1. Run the vitest suite.
**Expected Result:** 22 unit tests for pure-logic libs (`runOutcomes`, `chatLimits`, `aiToolsLimits`); a `unit` CI job (ml-portfolio DID already have a CI workflow — claimed otherwise twice). One test failed first-run on a wrong test assumption (per-message cap vs total-chars trim).
**Automation Hint:** vitest + CI.
**Source:** Part288 (`0e67e4d`/`2d474eb`)

### TC-P15-046
**Category:** Architecture
**Test Name:** Dead code removed via the compiler, not guesswork
**Steps:**
1. After the nav swap, run `tsc --noUnusedLocals`.
**Expected Result:** 279 orphaned declarations flagged and removed (net −195 lines); iterate until clean — don't guess the cascade across 48 files.
**Automation Hint:** `tsc --noUnusedLocals`.
**Source:** Part288 (`4c828cb`)

### TC-P15-047
**Category:** Bug-Regression
**Test Name:** siem-triage + ai-code judges fall back off Mistral (200-with-null)
**Steps:**
1. Call `/siem-triage/judge` and `/ai-code-detect/judge` while Mistral 429s.
**Expected Result:** Cohere→Mistral cascade returns real verdicts (login burst→high, new admin→critical) — was `200` with a `null` body / "Judge unavailable" on every group.
**Automation Hint:** API test with Mistral stubbed.
**Source:** Part289 (`dcef469`)

### TC-P15-048
**Category:** Bug-Regression
**Test Name:** Astrophotography detection survives OpenCV 5's HoughLinesP shape
**Steps:**
1. Run anomaly detection on frames containing a streak.
**Expected Result:** Returns a detection, not 500 — `lines.reshape(-1, 4)` handles OpenCV 5's `(N,4)` return (was `(N,1,4)`, indexed `[:,0,:]` → `IndexError` only WHEN a line was found, i.e. exactly when there was an anomaly to report).
**Automation Hint:** API test with a synthetic streak.
**Source:** Part289 (`c51ee25`)

### TC-P15-049
**Category:** Architecture
**Test Name:** A guided demo is an integration test; the fix belongs to the tool
**Steps:**
1. Record a clip that runs the real UI path against the live backend.
**Expected Result:** Catches bugs unit tests + `expect` miss (null judges, OpenCV-5 crash) because they manifest only on a real interaction's exact input; a 200 is not a success; the honest move is to fix the live tool, then record it.
**Automation Hint:** none (method).
**Source:** Part289

### TC-P15-050
**Category:** Architecture
**Test Name:** Demo inputs are crafted to the tool's real rules, never staged verdicts
**Steps:**
1. Build QR/malware/astro demo inputs.
**Expected Result:** Read the backend heuristics first (`mm_qr_phishing.py` → `http://paypal.com@paypa1.com/login` trips @-trick + typosquat + HTTP honestly); synthetic mixed-entropy / night-sky inputs measure true; never scan a third party or stage a finding. Narration matches the frame (yellow not blue; JPEG default 50 not 75).
**Automation Hint:** none (method).
**Source:** Part289

---

## Cross-cutting / Process (Parts 280–289)

### TC-P15-051
**Category:** Architecture
**Test Name:** "commit" from the user means commit + push (one step)
**Steps:**
1. User says "commit".
**Expected Result:** Commit then push — no separate "want me to push?"; `feedback_always_push_github` updated.
**Automation Hint:** none (process).
**Source:** Part286

### TC-P15-052
**Category:** Architecture
**Test Name:** "move all the X files" is a request to tidy, not to move files already home
**Steps:**
1. Reorganize repo-root docs.
**Expected Result:** `CLAUDE.md`/`README.md`/`THIRD_PARTY.md` stay at root (tooling/GitHub/license); specs → `docs/`; verify references are prose not path-reads; update memory pointers; delete nothing (stale-looking files are the user's call).
**Automation Hint:** none (judgment).
**Source:** Part286 (`91b927b`)

### TC-P15-053
**Category:** Architecture
**Test Name:** An interrupt means the work is unwanted, not "hold for later"
**Steps:**
1. User interrupts a build.
**Expected Result:** Discard the interrupted work and revert to the pre-change tree — don't commit unverified work or leave a "pick up tomorrow" note; keep responses short (no unrequested caveats/recaps).
**Automation Hint:** none (process).
**Source:** Part282d

### TC-P15-054
**Category:** Architecture
**Test Name:** Save the Space's current requirements before uploading a migration
**Steps:**
1. Before a risky dependency bump to the Space.
**Expected Result:** Prior requirements saved to scratchpad first → a numpy-2 build failure was a ~4-minute decision rollback, not a scramble; a local Docker build is the strongest pre-deploy check (`docker version` fails identically for stopped vs absent).
**Automation Hint:** none (process).
**Source:** Part283

---

**Total: 54 test cases, Parts 280–289.**
