# TC-P16 — Parts 290–299

**Prefix:** TC-P16
**Parts covered:** 290–299 (10 sessions)
**Status:** ✅ Complete
**Method:** Inline — no subagents; full line-by-line re-read of all 10 session logs.

Covers: the last demo clips + the fade fix + the un-clippable tools; six new security tools (Log Anomaly / JWT / Secret-PII / Exploit-Payload / Network Intrusion detectors) and the forgotten side-registrations; the Testwright platform build (tool-card → `/qa` world → GitHub-Actions runner → 5 live stages → flakiness/assertions/visual/ownership-gate, recorder dropped); Text-to-SQL graduating to a platform; the `/ml /eda /vision` native worlds + HF-app reskin; the TECH_STACK.md map; the API-docs/secret-sweep sessions; the HF token leak; and the handbook rebuild + MMRAG backlog clear-out (Periodicity Finder, Scan Descreen, Meeting Intelligence).

---

## Last Clips + Fade + Un-clippable Tools (Part 290)

### TC-P16-001
**Category:** Bug-Regression
**Test Name:** Clips fade in/out (video stream re-encoded, not copied)
**Steps:**
1. Inspect the first/last frames of any clip.
**Expected Result:** 0.6s fade-in / 0.9s fade-out to `#0b0e17` — `mux()` re-encodes (was `-c:v copy`, so the title/closing cards dissolved in-page but the stream popped on/off); VP9 output is smaller than Playwright's VP8.
**Automation Hint:** first/last-frame brightness check.
**Source:** Part290 (`9e9bae1`)

### TC-P16-002
**Category:** Architecture
**Test Name:** Demo inputs chosen so the tool measures honestly, not to stage a result
**Steps:**
1. Review the PPE / plant-growth / photo-search / crime-scene demo inputs.
**Expected Result:** PPE cropped to one clean worker (a crowd photo triggered the honest misattribution warning, reading as "wrong"); plant-growth auto-detect OFF (on, it crops to the plant box and measures fraction-of-crop → barely changes); photo-search uses real Pexels photos (CLIP needs real semantics); crime-scene uses a synthetic textured 3D scene with unique per-face textures (repeated textures → cross-box feature mismatches → outlier points blow up the auto-fit).
**Automation Hint:** none (method).
**Source:** Part290

### TC-P16-003
**Category:** Feature
**Test Name:** Multi-file demo upload sends all frames in one call
**Steps:**
1. Record a `multiple`-input tool (plant-growth growth mode).
**Expected Result:** `file` accepted as an array → one `setInputFiles` call (the input replaces its list on each pick).
**Automation Hint:** recorder self-test.
**Source:** Part290 (`4b7f4b4`)

### TC-P16-004
**Category:** Architecture
**Test Name:** Some tools are correctly ruled un-clippable
**Steps:**
1. Review wildlife-reid / captcha / rag-analytics.
**Expected Result:** Not filmed — MegaDescriptor is trained on wild species not domestic pets (same cat ~0.35) and publishable species' datasets forbid reproduction; captcha bills (paid vision ×2/run) and the VLM wins at max hardening (Correct→Correct sells nothing); rag-analytics isn't a handbook chapter so a clip has nowhere to launch.
**Automation Hint:** none (judgment).
**Source:** Part290

---

## Security Tools (Parts 291–292)

### TC-P16-005
**Category:** Architecture
**Test Name:** A "critical RCE, upgrade now" claim is verified at the source
**Steps:**
1. Check the Next.js 16.3.5 "critical RCE" claim.
**Expected Result:** False — `npm audit` + release notes show 16.3.5 is a bugfix; the Aug criticals landed in 16.3.3 (16.3.4 has them). The "RCE" pages were SEO/AI spam.
**Automation Hint:** none (method).
**Source:** Part291

### TC-P16-006
**Category:** Feature
**Test Name:** Log Anomaly Detector (IsolationForest) tuned to its failure modes
**Steps:**
1. Run anomaly detection on the captured real POST body.
**Expected Result:** 86% precision / 100% recall after fixes — `contamination=0.05` (not `"auto"`, which over-flags ~19/34); a payload spike modeled as a two-signal event (IF under-ranks single-feature outliers); `path_randomness` digit-fraction feature (not path Shannon entropy, which flags `/` at entropy 0); standardizing features makes no difference.
**Automation Hint:** API test tuned on the captured payload.
**Source:** Part291 (`94923b7`)

### TC-P16-007
**Category:** Feature
**Test Name:** JWT analyzer runs real weak-secret crypto, discloses the limit
**Steps:**
1. Analyze a weak-secret HMAC JWT and a strong-secret one.
**Expected Result:** Weak cracks on `secret`; strong (64-char random) doesn't; Web Crypto, client-side; "not found" does NOT prove the secret safe (exhaustive cracking impossible by design).
**Automation Hint:** client unit test on both samples.
**Source:** Part291 (`e761c23`)

### TC-P16-008
**Category:** Bug-Regression
**Test Name:** Secret/PII scanner demo data doesn't trip real scanners
**Steps:**
1. Commit the scanner with its demo `.env` sample.
**Expected Result:** Secret-shaped literals split across `+` concatenations (joined at runtime) so no complete secret exists in source (first push was blocked by GitHub push protection on a Stripe-shaped sample); Luhn-checked cards, spans inside a detected secret skipped, phone regex requires separators.
**Automation Hint:** grep source for complete secret patterns.
**Source:** Part291 (`a27c04c`)

### TC-P16-009
**Category:** Feature
**Test Name:** Exploit-payload detector deobfuscates before matching
**Steps:**
1. Submit URL/HTML-entity/Base64 (incl. double) encoded payloads + 10 benign inputs.
**Expected Result:** 33 signatures over 12 attack classes; a hit found only after decoding is tagged "Obfuscated · <how>"; 10/10 benign clean (normal SQL, `&&` git, single `../`, `--` in prose); `admin'--` auth-bypass caught (fixed mid-build). `security.ts` split 450→238+250.
**Automation Hint:** unit test payload + benign sets.
**Source:** Part292 (`4ecea04`)

### TC-P16-010
**Category:** Feature
**Test Name:** Network Intrusion Classifier shows the honest R2L weakness
**Steps:**
1. Classify the NSL-KDD held-out set.
**Expected Result:** 74.8% overall (matches the RF ceiling), DoS/Probe F1 0.84/0.78, R2L recall 0.15 shown (not averaged away); caller owns the labelled data, backend does the ML.
**Automation Hint:** API test on the bundled NSL-KDD.
**Source:** Part292 (`26c4c2f`)

### TC-P16-011
**Category:** Bug-Regression
**Test Name:** A new tool has all three side-registrations (card + thumbnail + breadcrumb)
**Steps:**
1. Add a `/tools/*` tool; check the card, its `public/thumbs/<id>.webp`, and `AREA_OF`.
**Expected Result:** Card renders a thumbnail (missing → blank white card) and breadcrumbs to its area (missing `AREA_OF` → only "Home"); grep a sibling id for the full class (`demos`/`securityLogExclusions` correctly don't include every tool). `feedback_new_tool_needs_thumbnail`.
**Automation Hint:** registration-consistency test over tool ids.
**Source:** Part292 (`3b5f264`/`63d3434`)

---

## Testwright Platform (Parts 293–294, 298)

### TC-P16-012
**Category:** Architecture
**Test Name:** A full app is a Platform world, not a tool card (match the tier)
**Steps:**
1. Review how QA Automation / Text-to-SQL are surfaced.
**Expected Result:** `/qa` (Testwright) and `/sql` are native worlds (hero + sub-nav + multiple routes), listed under Platforms, not the 50-tool Toolkit — "treat it like a website" means build the world.
**Automation Hint:** none (IA).
**Source:** Part293 (`98be844`)

### TC-P16-013
**Category:** Architecture
**Test Name:** Testwright is microservice-ready via one seam each side
**Steps:**
1. Trace a QA call.
**Expected Result:** Backend `routers/qa/` reaches shared infra only through `deps.py`, unified `/qa/*` prefix; frontend routes through `qaClient.ts` against `QA_API` (`NEXT_PUBLIC_QA_API_URL ?? ML_UNIFIED_API`) — extraction = copy folder + reimplement `deps.py` + one env var.
**Automation Hint:** architecture review.
**Source:** Part293 (`5e07563`)

### TC-P16-014
**Category:** Bug-Regression
**Test Name:** A graduated tool leaves the Toolkit fully
**Steps:**
1. Check Text-to-SQL's listings + breadcrumb.
**Expected Result:** Removed from `capabilities.ts`, area listing and metadata; `PLATFORM_OF` maps `/tools/text-to-sql` to its platform `/sql` (was double-listed, breadcrumbing to "Language & Documents").
**Automation Hint:** grep for the id across listings.
**Source:** Part293 (`f3a7de0`)

### TC-P16-015
**Category:** Bug-Regression
**Test Name:** Platform/toolkit tile caption sits on a scrim, not over the texture
**Steps:**
1. View a bento tile whose texture fills it.
**Expected Result:** Texture fills the tile, caption on its own `--bg-card` scrim (`.dom-cap::before`) — fixes both the Platforms and Toolkit grids (the name had overlapped the texture fade).
**Automation Hint:** visual/DOM check.
**Source:** Part293 (`ea5d852`)

### TC-P16-016
**Category:** Architecture
**Test Name:** Testwright executes on GitHub Actions (HF Docker Space now 402 PRO)
**Steps:**
1. Run a Testwright test.
**Expected Result:** Proxy `/qa/run/*` on the main Space (holds `GH_QA_TOKEN`) `workflow_dispatch`es `ramleo/ml-qa-runner` (public, free, isolated), polls by run-name, downloads the artifact; the token never reaches the browser.
**Automation Hint:** architecture review.
**Source:** Part294

### TC-P16-017
**Category:** Bug-Regression
**Test Name:** A failing test keeps the CI run green (pass/fail from results.json)
**Steps:**
1. Run a test that fails.
**Expected Result:** Pass/fail read from `results.json`, not the run conclusion — a QA tool's failures are normal, so the run stays green and doesn't email the owner.
**Automation Hint:** run a failing test; assert green + no email.
**Source:** Part294 (`91fc705`)

### TC-P16-018
**Category:** Bug-Regression
**Test Name:** Step timeline comes from a custom reporter (JSON reporter omits steps)
**Steps:**
1. View a run's step timeline + video/trace.
**Expected Result:** A workflow custom reporter writes `steps.json` (Playwright's JSON reporter omits per-step data); artifacts stream through the proxy so the token stays server-side.
**Automation Hint:** assert steps present.
**Source:** Part294 (`b152e2c`)

### TC-P16-019
**Category:** Feature
**Test Name:** Self-heal repairs locators from the ARIA snapshot
**Steps:**
1. Fail a run on a stale locator; click Heal & re-run.
**Expected Result:** LLM given the test + error + `error-context.md` (ARIA snapshot Playwright already writes) returns a fixed locator (`name:'AIRaML Platform'`→`'AIRaML'`), shows the diff, re-runs; a real bug still fails honestly.
**Automation Hint:** heal a known-stale locator.
**Source:** Part294 (`45a222a`)

### TC-P16-020
**Category:** Feature
**Test Name:** Testwright accepts any public URL, blocks private/internal
**Steps:**
1. Target a public site vs localhost/LAN/metadata IPs.
**Expected Result:** `validate_target_url` accepts any public http(s), blocks private/link-local/metadata; competitor names + "own-site only" framing removed; abuse bounded by per-stage daily caps.
**Automation Hint:** `urlcheck` unit test.
**Source:** Part294 (`85ceb0c`)

### TC-P16-021
**Category:** Feature
**Test Name:** Flakiness detection via `--repeat-each`
**Steps:**
1. Run a test 5×.
**Expected Result:** Mixed pass/fail across repeats → Flaky; `runs/pass_rate/flaky` from summed `expected`/`unexpected`; bounded `repeat_each` input; Runs 1/3/5/10 selector.
**Automation Hint:** repeat-each run with a flaky test.
**Source:** Part298 (`d7f8457`)

### TC-P16-022
**Category:** Feature
**Test Name:** Visual regression stores baseline in IndexedDB, diffs on canvas
**Steps:**
1. Capture a baseline, then a changed capture.
**Expected Result:** Pixel diff on a canvas (no pixelmatch dep), red overlay + % changed + tolerance; honest limit surfaced: WebGL/animated regions always read as changed.
**Automation Hint:** visual-diff unit test.
**Source:** Part298 (`a4f82f1`)

### TC-P16-023
**Category:** Feature
**Test Name:** Third-party targets require an authorization confirmation (backend-enforced)
**Steps:**
1. Run against a third-party host with `authorized:false`.
**Expected Result:** 403 before any dispatch (`validate_target_url` gates it); first-party demo hosts run freely; `OwnershipGate` checkbox on Run/Discover/Visual.
**Automation Hint:** API test third-party unauthorized.
**Source:** Part298 (`5ade9ab`)

### TC-P16-024
**Category:** Architecture
**Test Name:** Record-and-playback is dropped (same-origin policy)
**Steps:**
1. Confirm no browser-based recorder is shipped.
**Expected Result:** Dropped, not pending — a web app can't read events in a cross-origin iframe and sites send X-Frame-Options/CSP; real recorders (Playwright codegen) need desktop/extension privileges.
**Automation Hint:** none (constraint).
**Source:** Part298

---

## Native Worlds + App Reskin (Part 295)

### TC-P16-025
**Category:** Feature
**Test Name:** /ml /eda /vision are native platform worlds
**Steps:**
1. Load each; click "Open the platform".
**Expected Result:** Each = theme + guide + WorldShell/WorldNav + signature hero panel + honest-scope cards; `WorldNav.external` opens the HF Space in a new tab; `registry.json` entries `internal:true`+`href` (cards show "Enter"); copy verified against backend metrics.
**Automation Hint:** Playwright per world.
**Source:** Part295 (`8f2e5d7`/`64e8b40`)

### TC-P16-026
**Category:** Bug-Regression
**Test Name:** HF-app reskin includes the nav header and keeps the brand constant
**Steps:**
1. Open `?mode=ml|eda|vision`.
**Expected Result:** Two-bar chrome (AIRaML wordmark + portfolio links + `Source·AGPL` auto-injected + theme picker; world sub-nav with platform name); brand gradient is FIXED (`--brand-grad`), only the per-mode accent (fuchsia/emerald/violet) varies — tying the brand to the per-mode accent was the real "doesn't match".
**Automation Hint:** per-mode DOM/visual check.
**Source:** Part295 (`a4b02e8`/`0fc97b4`)

### TC-P16-027
**Category:** Bug-Regression
**Test Name:** A `<label>` styled as a dropzone uses `display:block`
**Steps:**
1. View the Clean & Export upload zone.
**Expected Result:** `display:block` → a proper dashed rectangle (inline labels fragment their border across line boxes).
**Automation Hint:** visual check.
**Source:** Part295 (`8cbbeb9`)

---

## Docs Sessions: Stack Map, API Docs, Secret Sweep (Parts 296–297)

### TC-P16-028
**Category:** Architecture
**Test Name:** TECH_STACK.md is code-verified, incl. the LangGraph soft dependency
**Steps:**
1. Cross-check TECH_STACK.md claims against the repos.
**Expected Result:** 18 categories grepped from code (embedding model IDs, LangGraph `StateGraph` for `/rag/agent` guarded by `_LANGGRAPH_OK`, degrades to direct retrieval, not pinned); deliberate gaps named (no Redis/auth/secret-manager/IaC/APM/object-storage/blue-green) with what covers each.
**Automation Hint:** none (doc accuracy).
**Source:** Part296 (`cab8d04`/`0acadbe`)

### TC-P16-029
**Category:** Architecture
**Test Name:** Deployed FastAPI docs are reachable and port drops on a real domain
**Steps:**
1. Fetch `/docs`, `/redoc`, `/openapi.json` on the live Space.
**Expected Result:** 200 (none disable `docs_url`); the `:port` only appears locally (443 implied on a domain); ml-sql/ml-vision have their own at their URLs.
**Automation Hint:** live fetch.
**Source:** Part297 (`b765fc8`)

### TC-P16-030
**Category:** Architecture
**Test Name:** Git-history secret sweep is clean; the AWS example key is scanner-safe
**Steps:**
1. Sweep both repos' full history (2,227 commits).
**Expected Result:** No real credentials; only intentional sample data in the security tools; the AWS `…EXAMPLE` key is whitelisted by gitleaks/GitHub, so the split-literal rule does NOT apply (changing it adds no value); values redacted in the report.
**Automation Hint:** CI gitleaks + manual sweep.
**Source:** Part297 (`cb92b05`)

---

## The Token Leak (Part 298)

### TC-P16-031
**Category:** Architecture
**Test Name:** A credential rule binds to the credential, not one command
**Steps:**
1. Run any git diagnostic.
**Expected Result:** Never run a command that prints a remote/credential (`git remote -v`, `get-url` to stdout) in any context or batch — the leak happened because the rule was filed under one command in the deploy context; inspect a batch's output surface first; when a safety classifier blocks an inline-token upload, hand it to the user, don't route around it.
**Automation Hint:** none (process; `feedback_never_print_tokens`).
**Source:** Part298

---

## Handbook Rebuild + MMRAG Clear-out (Part 299)

### TC-P16-032
**Category:** Bug-Regression
**Test Name:** Handbook keeps graduated-platform chapters (Platforms Part 1)
**Steps:**
1. Regenerate `handbook.md`.
**Expected Result:** `read_platforms()` reads `registry.json` + each world's guide → a "Platforms" Part 1 (Text-to-SQL keeps its deep chapter, Testwright/ml/eda/vision get one, the 4 security tools appear automatically); a naive regenerate would have DROPPED Text-to-SQL (its card left `capabilities.ts`). No prose invented.
**Automation Hint:** regenerate + diff; assert Text-to-SQL chapter present.
**Source:** Part299 (`8ebd569`)

### TC-P16-033
**Category:** Bug-Regression
**Test Name:** Testwright copy says five live stages (no dropped recorder claim)
**Steps:**
1. Read `theme.ts`, Author blurb, `TOOL_SUMMARY`.
**Expected Result:** "Five stages", Heal live, no "recorded click-through" (record-and-playback was dropped) — the summary also feeds the in-world AI assistant.
**Automation Hint:** content assertion.
**Source:** Part299 (`7bf0183`)

### TC-P16-034
**Category:** Feature
**Test Name:** Periodicity Finder (client-side FFT) with a valid SVG height
**Steps:**
1. Paste a numeric series / event timestamps.
**Expected Result:** Radix-2 FFT (detrend + Hann) finds the dominant cycle (sine p=12→12.2, weekly ts→~7 days; noise ~3× vs 10–225× for real signals); SVG uses a CSS height (invalid `height="auto"` fixed).
**Automation Hint:** engine unit test + render check.
**Source:** Part299 (`dc9e872`)

### TC-P16-035
**Category:** Feature
**Test Name:** Scan Descreen notch threshold tuned from measured data (10×)
**Steps:**
1. Descreen a halftone image and a clean image.
**Expected Result:** 2D-FFT notches periodic peaks >10× the local median (real screen spikes read hundreds×, a clean image tops ~5× → removed=0); non-generative (can't invent detail).
**Automation Hint:** API test clean vs halftone.
**Source:** Part299 (`e07b0d4`)

### TC-P16-036
**Category:** Feature
**Test Name:** Meeting Intelligence extracts, answers Q&A, streams with a heartbeat
**Steps:**
1. Upload a 2-speaker clip; ask an in-scope and an out-of-scope question.
**Expected Result:** Summary/decisions/action-items/talk-time (LLM instructed never to invent); `/rag/mm-meeting/ask` answers from the transcript, declines when absent; `/stream` emits a 10s heartbeat during the blocking transcription (so the proxy doesn't idle-timeout); in-tool player seeks on every transcript+agenda timestamp.
**Automation Hint:** API + Playwright on a `say`-generated clip.
**Source:** Part299 (`c73bf20`/`45584a6`/`f8f577d`)

### TC-P16-037
**Category:** Architecture
**Test Name:** Per-route body cap override, not a global bump
**Steps:**
1. Upload a 50MB file to `/rag/mm-meeting` vs another route.
**Expected Result:** `_ROUTE_CAPS` gives meeting routes 50MB; the tight 10MB `body_size.py` default holds for all ~50 other routes (raising the env var would loosen everything).
**Automation Hint:** API size tests both routes.
**Source:** Part299

### TC-P16-038
**Category:** Bug-Regression
**Test Name:** Object URL survives React StrictMode double-invoke
**Steps:**
1. Mount the meeting player in dev.
**Expected Result:** The effect creates AND revokes its own URL per run (a `useMemo` create + separate-cleanup revoke → dev mount→cleanup→mount revokes the URL `<video>` still points at → `ERR_FILE_NOT_FOUND`).
**Automation Hint:** console-error check in StrictMode.
**Source:** Part299

### TC-P16-039
**Category:** Architecture
**Test Name:** Don't build a feature that only reads from an unreliable source
**Steps:**
1. Check why transcript timestamps matter more than agenda timestamps.
**Expected Result:** `generate_chapters` is Mistral-only, no fallback, needs ≥4 segments → the agenda is frequently empty (free-tier 429s + short clips); the transcript always has timestamps, so clickable transcript timestamps are the reliable path.
**Automation Hint:** none (design).
**Source:** Part299

---

## Cross-cutting / Process (Parts 290–299)

### TC-P16-040
**Category:** Architecture
**Test Name:** Client-side tools need a manual run-log call
**Steps:**
1. Run a client-side tool (JWT/Secret scanner).
**Expected Result:** They emit a `query_run` (counts only, never the pasted input) via a manual `track`/`trackToolRun` — there's no `fetch` choke point for a local run, so `trackedFetch` doesn't cover them.
**Automation Hint:** telemetry assertion.
**Source:** Part291

### TC-P16-041
**Category:** Architecture
**Test Name:** A user guide is the real comprehensive guide, reused as one source
**Steps:**
1. Open a platform's "User Guide".
**Expected Result:** Opens the tool's own comprehensive modal (not the 72-line `userGuide.ts` distillation that only feeds the AI chat); the modal has a visible scrollbar + section search; reuse the single source rather than writing a thin new blurb.
**Automation Hint:** UI assertion.
**Source:** Part294 (`2ae7a51`)

### TC-P16-042
**Category:** Architecture
**Test Name:** Backend deploys verified by `/openapi.json` carrying the new route
**Steps:**
1. After an HF upload, poll then verify.
**Expected Result:** Poll until `stage=RUNNING` AND the new route is in `/openapi.json` (not just RUNNING), then a direct call, then Playwright — the standing batch-deploy discipline; a Python probe's SSL error is the probe's fault (use curl for TLS).
**Automation Hint:** none (method).
**Source:** Parts292/299

---

**Total: 42 test cases, Parts 290–299.**
