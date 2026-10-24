# TC-P14 — Parts 270–279

**Prefix:** TC-P14
**Parts covered:** 270–279 (10 sessions)
**Status:** ✅ Complete
**Method:** Inline — no subagents; full line-by-line re-read of all 10 session logs.

Covers: handbook demo markers + 2x-speed audio fix; return-to-position scrolling; the demo-clip audit (7 of 11 clips narrated something untrue) and the recorder rebuild (headed Chrome for WebGL, hover/drag/range actions, title/closing cards, audio-offset + dead-air fixes, spotlight `with`); three SHIPPED backend bugs (`/models` 500, drift's invented baseline, CatBoost never running); the full provider audit (Mistral best-effort free tier, Groq retired models, Cohere promoted, Gemini demoted) and the efficiency work around it; the complete logging spec (`trackedFetch`/`instrument`, `llm_calls`, `security_log`); and the security-log hardening arc (DB rate limit, Turnstile, CSP, IST views).

---

## Handbook Demo Markers + 2x-Speed Audio (Part 270)

### TC-P14-001
**Category:** Feature
**Test Name:** Contents marks which chapters have a guided demo
**Steps:**
1. Open the handbook contents; search "demo".
**Expected Result:** 11 marked rows via `role="img"` + `aria-label` (zero text node, so no phantom search hits — an `.sr-only` caption would add 11); legend uses the same marker element; markers hidden in the PDF.
**Automation Hint:** assert `.hb-toc-demo` text empty; search "guided demo" → 1.
**Source:** Part270 (`9c6aa36`)

### TC-P14-002
**Category:** Bug-Regression
**Test Name:** Handbook edition is a constant, not `date.today()`
**Steps:**
1. Regenerate `handbook.md` on any date.
**Expected Result:** Title page edition is fixed (was `date.today().strftime('%B %Y')` → CI `handbook` job went red on 1 Sept from unchanged sources).
**Automation Hint:** regenerate; `git diff --quiet`.
**Source:** Part270 (`74a508a`)

### TC-P14-003
**Category:** Bug-Regression
**Test Name:** Sped-up clip narrates at the clip's speed
**Steps:**
1. Play a demo clip at 2x.
**Expected Result:** `voice.ts` `u.rate = BASE_RATE * rate`; `DemoVoice` reads `video.playbackRate` per cue; `hosted.ts` sets `playbackRate` — 0 of 10 lines cut off at 2x (was 8 of 10); 1x unchanged at 0.95.
**Automation Hint:** instrument `speechSynthesis`, count cut-off lines at 1x/2x.
**Source:** Part270 (`4ea631e`)

### TC-P14-004
**Category:** Architecture
**Test Name:** A defect only the instrumentation can see must be re-checked without it
**Steps:**
1. Observe a "phantom duplicate first cue" during instrumented playback.
**Expected Result:** It's the harness (`currentTime=0` after voice-select fires `seeking` → correct re-speak); confirmed by running once in real-viewer order — not a product defect.
**Automation Hint:** none (method).
**Source:** Part270

---

## Return-to-Position + Clip Audit + Recorder Bug (Part 271)

### TC-P14-005
**Category:** Feature
**Test Name:** Handbook offers a way back after a jump
**Steps:**
1. Rail-jump from deep in ch 31 to ch 1; press "Back"; then Enter through 3 search hits; then a short 670px jump.
**Expected Result:** One slot (not a stack); returns to the reading spot not the last look; `moved`/`landing` flags mean a <1.5-viewport jump shows no pill, and 4 screens of hand-scroll retires it.
**Automation Hint:** Playwright scripted jump/return checks.
**Source:** Part271 (`d3217eb`)

### TC-P14-006
**Category:** Bug-Regression
**Test Name:** Demo spotlight hides when its anchor unmounts (not freezes)
**Steps:**
1. Record a demo whose anchored element unmounts mid-step (e.g. `mmrag-add` dropzone after ingest).
**Expected Result:** `place()` sets `spot.style.display="none"` when `querySelector` is null (was: early-return left the ring frozen over where the element used to be — the filter chips).
**Automation Hint:** recorder self-test + frame review.
**Source:** Part271 (`dd67442`)

### TC-P14-007
**Category:** Architecture
**Test Name:** Record against the allowlisted origin port (3300)
**Steps:**
1. Record a demo that calls the Space.
**Expected Result:** Serve on `localhost:3300` (allowlisted in `origin_policy.py`); port 3200 → 403 on every browser call. curl works (no `Origin` header).
**Automation Hint:** none (procedure).
**Source:** Part271

### TC-P14-008
**Category:** Architecture
**Test Name:** text-to-sql talks to the separate ml-sql backend
**Steps:**
1. Record/run text-to-sql.
**Expected Result:** Needs `NEXT_PUBLIC_ML_SQL_URL` set (a schema fetch to the frontend 404s); ml-sql is its own Space with its own CORS.
**Automation Hint:** none (config).
**Source:** Part271

### TC-P14-009
**Category:** Architecture
**Test Name:** Watch the artifact (the clip), not the code that produced it
**Steps:**
1. Review recorded clips frame-by-frame at ~88%.
**Expected Result:** 2 of 3 (then 5 of 8, 7 of 11 overall) narrated claims the screen didn't support — invisible from source; `expect` proves a string IS present, never that a claim is unsupported.
**Automation Hint:** none (method).
**Source:** Part271

---

## text-to-sql Chart Bug + Three Shipped Backend Bugs (Part 272)

### TC-P14-010
**Category:** Bug-Regression
**Test Name:** Chart chooser rejects a heatmap built from two key columns
**Steps:**
1. Query returning `FirstName | LastName | Total Spending` (both categoricals ~100% distinct).
**Expected Result:** `detectViz` cardinality guard — heatmap requires both categorical axes distinctness ≤ 0.7 (a real grid tops out at 0.5); falls through to bars (was a 10×10 grid, 10 filled/90 zero). The tool's own insights already said "100% distinct — likely a key".
**Automation Hint:** unit test `detectViz` (pure) on 6 fixtures.
**Source:** Part272 (`3132301`)

### TC-P14-011
**Category:** Bug-Regression
**Test Name:** `/models` tolerates schema-less (Pipeline Builder) entries
**Steps:**
1. Register an Express-mode pipeline model (bare pipeline, no `schema`/`classes`); call `/models`.
**Expected Result:** Returns 200 — `_registry.py` gives it the AutoML shape AND `list_models` reads defensively (a malformed entry costs its title, not the endpoint). Was: one entry `KeyError` → 500 → took Drift down too.
**Automation Hint:** API test with a schema-less registered model.
**Source:** Part272 (`8899f58`)

### TC-P14-012
**Category:** Bug-Regression
**Test Name:** Drift uses the fitted scaler's real mean, not an invented baseline
**Steps:**
1. Run drift on a built-in model with a batch drawn from its real training distribution (2 of N columns shifted).
**Expected Result:** Baseline found by preprocessor TYPE (was `named_steps.get("prep")` — built-ins name it `"preprocessor"` → empty → `(fmin+fmax)/2` guess reported as `ref_mean`); only the shifted columns flag; every feature carries `ref_source` (`training`|`schema_range`).
**Automation Hint:** API test with a known-shift batch; assert correct flags + `ref_source`.
**Source:** Part272 (`8ec64dc`)

### TC-P14-013
**Category:** Bug-Regression
**Test Name:** CatBoost fits on the read-only Space filesystem
**Steps:**
1. Run AutoML/Ensemble/Pipeline Builder/Optuna with CatBoost in the lineup (reproduce via a `chmod 555` dir).
**Expected Result:** `allow_writing_files=False` at all 8 construction sites — CatBoost scores (e.g. 0.8288); was `CatBoostError: Can't create ... catboost_info` → dropped silently (Ensemble returned 4 of 5). `cv_results` now carries `failed_models`.
**Automation Hint:** fit from a read-only cwd.
**Source:** Part272 (`00c25de`)

### TC-P14-014
**Category:** Bug-Regression
**Test Name:** Return pill names the chapter at the reading line, with a working mark
**Steps:**
1. Jump 30→43, 43→30, 30→48, 48→43 mid-book.
**Expected Result:** Label read at 38% down (`READING_LINE`), not the top edge; a jump carries a group (`find:<query>` stays one trip, rail/contents always re-mark) so the mark doesn't freeze; a "Top" button appears past the first screen; Part ticks on the rail are clickable (chapter tick no longer swallows them).
**Automation Hint:** Playwright mid-book jump sequences.
**Source:** Part272 (`d383286`)

### TC-P14-015
**Category:** Bug-Regression
**Test Name:** email-auth checker renders the DMARC subdomain policy
**Steps:**
1. Check headers for a domain with `sp=reject` (GitHub).
**Expected Result:** The `subdomain_policy` row renders (API always returned it at `email_auth_check.py:167`; no component displayed it).
**Automation Hint:** API + UI assertion.
**Source:** Part272 (`bd3e744`)

### TC-P14-016
**Category:** Bug-Regression
**Test Name:** DNS-tunneling tool copy matches its own logic (2-of-3, entropy mandatory)
**Steps:**
1. Read the tool's intro/comment vs the flagging code.
**Expected Result:** Copy says "two of three signals, entropy mandatory" (was "all three must agree" while code flagged on two) — the clip was right, the tool was wrong.
**Automation Hint:** content vs logic review.
**Source:** Part272

### TC-P14-017
**Category:** Bug-Regression
**Test Name:** Recorder `select` action + `waitFor` visibility + data-wt pass-through
**Steps:**
1. Record a demo with a dropdown, an unmounting anchor, and a custom component anchor.
**Expected Result:** A `select` action (a click can't pick an option); `waitFor` distinguishes "never appeared" from "present but never visible (empty wrapper)"; custom components without rest-prop spread (RepulsionCard, NumericTransformsPanel, ActionBtn) declare `data-wt` explicitly; `display:contents` is not a valid anchor (measures zero).
**Automation Hint:** recorder self-tests.
**Source:** Part272

---

## Part 1 Complete + Coverage Count (Part 273)

### TC-P14-018
**Category:** Feature
**Test Name:** Pipeline Cinema shows a completion state (not empty)
**Steps:**
1. Run Pipeline Cinema with a file to the end.
**Expected Result:** A completion banner (inline SVG) above the controls with `cin-done` anchor; copy reads "Run Cinema"; `main` has bottom padding so the caption can clear the controls.
**Automation Hint:** Playwright run-to-end.
**Source:** Part273 (`712ed91`)

### TC-P14-019
**Category:** UI
**Test Name:** Transport controls use SVG icons (inherit color)
**Steps:**
1. Inspect Pause/Resume/Stop in Pipeline Cinema (live).
**Expected Result:** Inline SVG on `fill="currentColor"` (was `▶ ⏸ ⏹` glyphs that render as fixed-color emoji — the Stop mark stayed dark on a red button). The red Stop square is the visual proof.
**Automation Hint:** query live DOM for `<path d=…>`.
**Source:** Part273 (`c73ab2f`)

### TC-P14-020
**Category:** Architecture
**Test Name:** Real-Time Analytics records against live Vercel (empty local keys)
**Steps:**
1. Build locally; load the dashboard.
**Expected Result:** Renders "Dashboard not configured" locally (`SUPABASE_*` keys empty in `.env.local`) — this also explains the pipeline-builder `/api/track` 400s (same missing creds, every page, local only). Film against production.
**Automation Hint:** none (config/diagnosis).
**Source:** Part273 (`d9c9da2`)

### TC-P14-021
**Category:** Bug-Regression
**Test Name:** SHAP/Optuna AI panel gets real model names (not "undefined")
**Steps:**
1. Open the SHAP (and Optuna) page; inspect what the AI assistant is told.
**Expected Result:** `/train` returns `{algorithm, score, fold_scores}`; the page reads `c.algorithm`/normalizes (was `c.name` → "All model CV scores: undefined=0.8456").
**Automation Hint:** unit/integration on the normalization.
**Source:** Part273 (`06d2b18`) / Part274 (`a3a8b8e`)

### TC-P14-022
**Category:** Architecture
**Test Name:** Sample demo step frames at 88%, not 70%
**Steps:**
1. Extract a review frame for a short step.
**Expected Result:** 88% avoids the spotlight still in `transition: all .35s` flight; a 70% frame can show the previous step's ring mid-transition.
**Automation Hint:** none (method).
**Source:** Part273

---

## Part 2 Complete + the `expect`/`.value` Fix (Part 274)

### TC-P14-023
**Category:** Bug-Regression
**Test Name:** PDF comparison depends on page count (chunks are per-page)
**Steps:**
1. Reconcile a contract/invoice with multiple clauses.
**Expected Result:** `mm_ingest.py` builds chunks per page — a one-page doc is a single chunk (one finding max); one clause per page pairs rate-with-rate. Page count, not word count, decides comparison granularity.
**Automation Hint:** ingest a 1-page vs 4-page doc; assert chunk count.
**Source:** Part274 (`d11dd48`)

### TC-P14-024
**Category:** Bug-Regression
**Test Name:** Reconciliation doesn't drop near-identical passages before the judge
**Steps:**
1. Reconcile where the invoice repeats the contract's sentence verbatim.
**Expected Result:** A pair scoring above `_SIM_CEILING = 0.93` is dropped as "too similar" — a real discrepancy can hide behind verbatim repetition (must reword realistically to surface it).
**Automation Hint:** unit test the similarity ceiling.
**Source:** Part274

### TC-P14-025
**Category:** Bug-Regression
**Test Name:** Demo `expect` can see text typed into inputs/textareas
**Steps:**
1. Assert on text loaded into a field.
**Expected Result:** The guard reads `input/textarea.value` plus body text (was `innerText` only — a field's contents live in `.value`, so every type/load step was unassertable). Adds only to visibility; all 24 demos checked — none self-satisfies.
**Automation Hint:** recorder unit test on a field-load step.
**Source:** Part274 (`5322fc6`)

### TC-P14-026
**Category:** Architecture
**Test Name:** Withdraw a stale self-recommendation rather than defer it
**Steps:**
1. Review "verify Parts 269–272 on live Vercel" carried 4 sessions.
**Expected Result:** Dropped — never an owner request, no evidence anything's broken, owner uses the site daily; `feedback_withdraw_stale_recommendations`.
**Automation Hint:** none (process).
**Source:** Part274

---

## Recorder Rebuild + WebGL + Clip Shape (Part 275)

### TC-P14-027
**Category:** Architecture
**Test Name:** Recorder uses headed Chrome so WebGL renders
**Steps:**
1. Record a WebGL tool (Depth Parallax).
**Expected Result:** `chromium.launch({channel:"chrome", headless:false})` (headless draws WebGL blank); `DEMO_HEADLESS=1` restores old behavior. Part 3 was "blocked" on this one line, not effort.
**Automation Hint:** regression-record an existing clip first.
**Source:** Part275 (`e05dcd6`)

### TC-P14-028
**Category:** Feature
**Test Name:** Recorder can move a pointer (hover/drag/range) with real waits
**Steps:**
1. Record a pointer-driven mode (parallax/relief/bokeh).
**Expected Result:** `hover`/`drag`/`range` actions in both players; real waits between `mouse.move` samples (Playwright's intermediate moves fire too fast and render as one jump).
**Automation Hint:** canvas SSIM across a sweep.
**Source:** Part275

### TC-P14-029
**Category:** Bug-Regression
**Test Name:** Clips have a title card, aligned audio, timed actions, closing card
**Steps:**
1. Review a rebuilt clip end-to-end.
**Expected Result:** Title card covers the ~1.3s load; audio gets that lead; actions cue at ~1/3 in (capped 2.5s, `actAfter` override); closing card; dead air removed (`narrationLeft` math — Depth Parallax 224s→192s).
**Automation Hint:** first/last-frame + per-step review.
**Source:** Part275 (`d4dfa35`/`2c6cd16`/`7f67684`)

### TC-P14-030
**Category:** Bug-Regression
**Test Name:** In-app demo player speaks before acting
**Steps:**
1. Play a live handbook demo with uploads/clicks.
**Expected Result:** The line starts, then the action lands on-cue (was `await perform(s)` then speak — every action in silence); upload File type fixed (was stamped `text/csv` → `data:text/csv` won't decode as image).
**Automation Hint:** Playwright live-player timing.
**Source:** Part275

### TC-P14-031
**Category:** Feature
**Test Name:** Spotlight can enclose a control AND the element it changes (`with`)
**Steps:**
1. Drive a slider whose effect is elsewhere (Depth Parallax bokeh; AutoML target+task).
**Expected Result:** Optional `with` second anchor → ring is the bounding box of both (was: the ring dimmed the image the slider changed).
**Automation Hint:** frame review of the ring bbox.
**Source:** Part275 (`abc0ce2`)

### TC-P14-032
**Category:** Bug-Regression
**Test Name:** AutoML clip says "five algorithms" (Extra Trees included)
**Steps:**
1. Review AutoML clip step 5.
**Expected Result:** Narration matches the 5 chips (was "four compete"; `"four"`/`"XGBoost"` assertions proved nothing — not a page string / matched any leaderboard row). Ensemble arithmetic corrected (std 0.034 ≥ 0.03 "Variable").
**Automation Hint:** frame vs narration review.
**Source:** Part275 (`37145f3`/`54d8c33`)

---

## Free Clips Finished + the Provider Crisis (Part 276)

### TC-P14-033
**Category:** Bug-Regression
**Test Name:** Preprocessing results show a before→after for Missing
**Steps:**
1. Run preprocessing on data with missing values.
**Expected Result:** Missing card reads e.g. `29 → 0` (was hardcoded `"—"` while `analyzed.total_missing` was in scope).
**Automation Hint:** UI assertion.
**Source:** Part276 (`f69da15`)

### TC-P14-034
**Category:** Bug-Regression
**Test Name:** Pipeline Builder "Express mode" copy says 4 stages, not 7
**Steps:**
1. Read the Express-mode card; run it.
**Expected Result:** Runs 4 stages (Optuna/SHAP/Ensemble render LOCKED until those finish); copy no longer claims "all 7 at once".
**Automation Hint:** run + read stage grid.
**Source:** Part276 (`d60762f`)

### TC-P14-035
**Category:** Bug-Regression
**Test Name:** Reconciliation never reports a false all-clear on judge failure
**Steps:**
1. Reconcile while every judge call is rate-limited.
**Expected Result:** Failures counted as `judge_failures`; the false "No discrepancies found" is suppressed (was: `judge_fn` returns None on 429 → same branch as "judge cleared it" → confident all-clear on the tool whose job is catching discrepancies).
**Automation Hint:** `page.route()` a synthetic failure; assert no `recon-clean`.
**Source:** Part276 (`1603c9a`/`7b5d7d3`)

### TC-P14-036
**Category:** Architecture
**Test Name:** Gemini API key is redacted from logs (two leak paths)
**Steps:**
1. Trigger a Gemini error; read the log.
**Expected Result:** A root-logger redaction filter covers both httpx's request line AND our WARNING formatting the exception (Gemini takes its key as a URL query param; httpx logs whole URLs at INFO) — all 13 call sites.
**Automation Hint:** assert no key substring in captured logs.
**Source:** Part276 (`e5f47e7`)

### TC-P14-037
**Category:** Bug-Regression
**Test Name:** CI installs CPU torch (not the multi-GB CUDA wheel)
**Steps:**
1. Run CI install.
**Expected Result:** torch/torchvision from the CPU index first (nothing pins torch; `sam2`/`sentence-transformers` pulled the default CUDA build → "No space left on device"); unused runner toolchains dropped.
**Automation Hint:** CI green + install-size check.
**Source:** Part276 (`73362d4`)

### TC-P14-038
**Category:** Architecture
**Test Name:** Error body is read before theorizing a provider failure
**Steps:**
1. Diagnose a Gemini/Mistral 429.
**Expected Result:** `llm.py` logs the response body (429 can mean per-minute, per-day, no billing, or API-never-enabled — the body says which); a cold 429 after idle ≠ a rate problem (timestamp is the evidence).
**Automation Hint:** none (method; `172459b`).
**Source:** Part276

### TC-P14-039
**Category:** Architecture
**Test Name:** Mistral free tier is best-effort (no reserved capacity)
**Steps:**
1. Observe cold 429s on a fresh key, under the shown RPS/TPM.
**Expected Result:** Vendor-confirmed: free requests are rejected when paid traffic is busy, regardless of the Limits page; not an account block, cap, or dead key — unobservable from the client (succeeds at 3am, fails at 3pm).
**Automation Hint:** none (vendor fact).
**Source:** Part276 §15 / Part277

---

## The Provider Audit (Part 277)

### TC-P14-040
**Category:** Architecture
**Test Name:** Provider cascade is Cohere → Mistral → Gemini (paid last)
**Steps:**
1. Inspect `generation.py` cascade and `QueryRequest` default.
**Expected Result:** Cohere first (free/reliable), Mistral second (free when capacity exists), Gemini last (only paid key); default `cohere`/`command-a-03-2025` (was `mistral → gemini → cohere`, silently promoting paid Gemini when Mistral died).
**Automation Hint:** provider-cascade test.
**Source:** Part277 (`db8f2eb`/`51d6866`)

### TC-P14-041
**Category:** Bug-Regression
**Test Name:** Groq requests cap output tokens (OTPM 1000)
**Steps:**
1. Call a Groq model with no `max_tokens`.
**Expected Result:** `max_tokens` on the OpenAI-compat streamer, Groq capped at 900 (SDK's default 2048 > 1000 OTPM → "Request too large", rejected before generating → looks like a dead provider).
**Automation Hint:** API test on the cap.
**Source:** Part277 (`33acb43`)

### TC-P14-042
**Category:** Bug-Regression
**Test Name:** Retired Groq model names are replaced; a generic error hid two bugs
**Steps:**
1. Test each Groq model name live.
**Expected Result:** `llama-3.1-8b-instant`/`llama-3.3-70b-versatile` (404 retired), `gemma2-9b-it`/`mixtral-8x7b-32768` (decommissioned) removed; qwen3.6/3.8 added. "Something went wrong" covered a retired model AND an oversized request — only the raw body separated them. Claude's "not configured" proved Groq's key existed.
**Automation Hint:** live name test.
**Source:** Part277 (`94df800`)

### TC-P14-043
**Category:** Efficiency
**Test Name:** A dead provider costs one round trip, not six
**Steps:**
1. Run a reconciliation scan with a stubbed-dead primary.
**Expected Result:** One shared forward-only latch across judge+confirm + `max_retries=0` → 1 Mistral round trip (was 6: two chains × SDK's 2 retries); fallback count unchanged.
**Automation Hint:** stubbed-dead-primary count test.
**Source:** Part277 (`4cbbf59`/`51d6866`)

---

## Logging Spec Built (Part 278)

### TC-P14-044
**Category:** Architecture
**Test Name:** LLM telemetry is captured at one funnel, not per call site
**Steps:**
1. Make any LLM/backend call.
**Expected Result:** Frontend `trackedFetch` wraps 81 raw fetches; backend `instrument()` wraps the 4 `_stream_*_raw`; every caller recorded for free — no per-site instrumentation to forget.
**Automation Hint:** grep for raw `fetch(` in migrated files.
**Source:** Part278 (`2b2b7f8`)

### TC-P14-045
**Category:** Architecture
**Test Name:** The Space never holds a database key
**Steps:**
1. Make an LLM call; watch the log sink.
**Expected Result:** Space POSTs to Vercel `/api/llm-log` with `AIRAML_LOG_TOKEN` (no Supabase key on the Space — its logs leaked a Gemini key 2026-09-05); 404s if the secret is unset (fail closed); 200 only after the insert.
**Automation Hint:** integration: call → `POST /api/llm-log 200`.
**Source:** Part278

### TC-P14-046
**Category:** Bug-Regression
**Test Name:** Streaming calls log the real duration/outcome, not header-time success
**Steps:**
1. Stream an answer that takes 25s / dies mid-stream / is cancelled.
**Expected Result:** `trackedFetch({streaming:true})` records on stream end: finished→success w/ real duration, broke→error, cancelled→success `completed:false` (was: `fetch` resolves at headers → 25s logged ~800ms; an in-band `{type:"error"}` in a 200 SSE logged success).
**Automation Hint:** streaming telemetry test for each outcome.
**Source:** Part278 (`27bc14f`+)

### TC-P14-047
**Category:** Architecture
**Test Name:** Instrumented-caller list is derived, not eyeballed
**Steps:**
1. Enumerate LLM-spending callers.
**Expected Result:** Derived by grepping backend modules importing the LLM client → routes → frontend callers (an eyeballed batch missed `/ai-code-detect/judge`, `/siem-triage/judge`, and callers aliasing the backend as `API` incl. DriftRunner); and exclude timer pings like `KeepAlive`/`/health`.
**Automation Hint:** none (method; `feedback_status_claims_need_evidence`).
**Source:** Part278

### TC-P14-048
**Category:** Architecture
**Test Name:** Prove a verification harness can fail before trusting a pass
**Steps:**
1. Run a lint/type baseline comparison.
**Expected Result:** Inject a known error, confirm the checker reports exactly 1, remove it (a `0 vs 0` was zsh not word-splitting `$FILES` + `eslint -f unix` absent → the check never ran). Lint with CI's pinned version.
**Automation Hint:** none (method).
**Source:** Part278

### TC-P14-049
**Category:** Feature
**Test Name:** `security_log` records upload metadata, never the file
**Steps:**
1. Select a file on any tool; check the log; check the password tool.
**Expected Result:** Records filename/ext/size/mime/SHA-256/prompt-length/session/country, 30-day retention; one capture-phase `change` listener on every `input[type=file]` (catches both FormData and base64-JSON uploads); logs on select; password tool excluded in BOTH client and server.
**Automation Hint:** inject a File event on a tool vs the password page.
**Source:** Part278 (`8f38298`)

### TC-P14-050
**Category:** Architecture
**Test Name:** `security_log` is unreadable via two independent locks
**Steps:**
1. Try to read the table via the anon key; look for a GET handler.
**Expected Result:** RLS on with no policies (DB refuses) AND no GET route — the two fail separately, not backing each other up.
**Automation Hint:** anon-key read attempt.
**Source:** Part278 (`020d7ec`)

### TC-P14-051
**Category:** Architecture
**Test Name:** A comment must not assert a protection the code lacks
**Steps:**
1. Check the `security_log` write route's "origin-checked" claim.
**Expected Result:** The claim was false (only field-clamping existed) → the next reader stops looking. Real guards added (see TC-P14-053/054).
**Automation Hint:** none (review).
**Source:** Part278 (`c91dbd0`)

---

## Security-Log Hardening: Turnstile, CSP, IST (Part 279)

### TC-P14-052
**Category:** Bug-Regression
**Test Name:** Security-log rate limit lives in the database, not a module Map
**Steps:**
1. Fire >60/min from one caller across serverless instances.
**Expected Result:** `log_security_event()` counts the last minute in-DB (every instance sees it) and returns false (a module-level `Map` was per-instance → bypassable); a salted-HMAC `ip_hash` identifies the caller, never the raw IP.
**Automation Hint:** flood test; assert 429 at the limit.
**Source:** Part279 (`abfc7a1`/`52cf37f`)

### TC-P14-053
**Category:** Feature
**Test Name:** Turnstile blocks scripted writes, fails open unconfigured
**Steps:**
1. POST via curl (forged Origin) vs a real browser upload.
**Expected Result:** curl → 403 "Failed verification"; real browser → logged; no secret configured → fails open (opt-in). Proof-of-work was rejected (a native attacker out-hashes a browser).
**Automation Hint:** curl 403 + manual browser row.
**Source:** Part279 (`d3a7a3f`)

### TC-P14-054
**Category:** Bug-Regression
**Test Name:** CSP allows the Turnstile iframe (`frame-src`)
**Steps:**
1. Load a page with Turnstile; read the console.
**Expected Result:** `frame-src 'self' https://challenges.cloudflare.com` (no `frame-src` → fell to `default-src 'self'` → iframe blocked, console said so on the first run; script loaded + `window.turnstile` existed but no token).
**Automation Hint:** console-error assertion.
**Source:** Part279 (`704710c`)

### TC-P14-055
**Category:** Architecture
**Test Name:** Turnstile cannot be verified by an automated browser (600010)
**Steps:**
1. Try to record/verify the Turnstile happy path with Playwright.
**Expected Result:** Error `600010` — Turnstile rejects automated/restricted browsers by design; the happy path is verified manually in real Chrome, not machine-testable here.
**Automation Hint:** none (recognize the limit).
**Source:** Part279

### TC-P14-056
**Category:** Architecture
**Test Name:** IST views use `security_invoker=true` (don't bypass RLS)
**Steps:**
1. Create `security_log_ist`/`llm_calls_ist`/`events_ist`.
**Expected Result:** Each carries `security_invoker=true` — a view runs as its OWNER by default, so a plain view over `security_log` would let the anon key read through it, undoing the RLS; storage stays UTC. (`security_invoker` needs PG 15+, so creation-without-error proves support.)
**Automation Hint:** anon read through the view → denied.
**Source:** Part279 (`86907ac`)

### TC-P14-057
**Category:** Architecture
**Test Name:** Fail-closed logging means the log is a floor, not a complete record
**Steps:**
1. Upload with an ad-blocker blocking Cloudflare.
**Expected Result:** Upload still works; its log row is skipped (no token) — the security log records what most visitors uploaded, not provably all. Documented, not discovered later.
**Automation Hint:** none (documented behavior).
**Source:** Part279

### TC-P14-058
**Category:** Bug-Regression
**Test Name:** Site chatbot + tool chats default to a free provider; Groq hides reasoning
**Steps:**
1. Open the homepage chat and a tool chat; select Groq.
**Expected Result:** Default Cohere in `/api/chat` AND `Chatbot.tsx` initial state (both needed — UI sends `provider` explicitly); Groq uses `reasoning_format:"hidden"` + `stripThinking()` + 900 max_tokens (was leaking `<think>` with the answer truncated).
**Automation Hint:** live chat reply assertions.
**Source:** Part279 (`0cc69e4`/`be8fd4f`)

### TC-P14-059
**Category:** Bug-Regression
**Test Name:** ml-sql default provider swapped off a retired Groq model
**Steps:**
1. Call ml-sql `/sql/sample-questions` with `provider=groq`.
**Expected Result:** Uses `groq/compound` (not a reasoning model — output parsed as SQL); deployed to ml-sql's OWN HF Space (`wram1708/ml-sql`, same account token). Verify via the no-fallback endpoint — `/sql/query` silently cascades groq→mistral→gemini→cohere.
**Automation Hint:** live call to the isolating endpoint.
**Source:** Part279 (`9eadc44`)

### TC-P14-060
**Category:** Bug-Regression
**Test Name:** Analytics-only values aren't "fixed" and silent fallbacks are surfaced
**Steps:**
1. Inspect `PROVIDER_MODEL` in `useQueryRunner.ts`; run a query that falls back; name an unknown provider.
**Expected Result:** `PROVIDER_MODEL` is analytics-only (body sends `provider`, never `model`) — mirrors the backend registry so the chart stops naming uncalled models; `generate_sql()` returns `(sql, provider_used, model_used)` + `fell_back_from`, canonicalizing an unknown name to its real provider (was labeled with the name asked for).
**Automation Hint:** telemetry assertion on a fallback + unknown-provider run.
**Source:** Part279 (`6dd9e8a`/`6867b43`/`2cdff28`)

### TC-P14-061
**Category:** Feature
**Test Name:** SQL suggestion chips are cleaned to real questions
**Steps:**
1. Fetch sample questions via a chatty provider (`groq/compound`).
**Expected Result:** `_clean_suggestions()` (shared by both parsers) requires a trailing `?` — drops headers/preambles like `**Five analyst-focused questions**`.
**Automation Hint:** unit test the cleaner.
**Source:** Part279 (`d2a352d`)

---

## Cross-cutting / Process (Parts 270–279)

### TC-P14-062
**Category:** Architecture
**Test Name:** Status words require a command showing them, in the same turn
**Steps:**
1. Report "done"/"fixed"/"deployed"/"passing".
**Expected Result:** Backed by a command output; fix the CLASS (grep + count before fixing), prove a check can fail, disambiguate a 404/empty/silent response with a control (e.g. a 405 proved a route deployed). `feedback_status_claims_need_evidence`.
**Automation Hint:** none (standing feedback).
**Source:** Part278

### TC-P14-063
**Category:** Architecture
**Test Name:** Verify a failure path by faking the response, not buying one
**Steps:**
1. Prove the reconciliation false-all-clear fix.
**Expected Result:** `page.route()` intercepts the one paid call with a synthetic reply; both branches render on the live deploy with zero API spend; `recon-clean` confirmed absent from the DOM.
**Automation Hint:** none (method).
**Source:** Part276

### TC-P14-064
**Category:** Architecture
**Test Name:** A schema default only applies to callers that omit the field
**Steps:**
1. Trace which provider real visitors use.
**Expected Result:** `useRagChat.ts`/`Chatbot.tsx` send `provider` explicitly (`useState("gemini")`), so the backend default never fired for them — the diagnostic probe was the only caller exercising it. Verify after the rebuild, not during it.
**Automation Hint:** none (method).
**Source:** Part276/Part277

### TC-P14-065
**Category:** Architecture
**Test Name:** Check template-literal/prop-passed anchors before declaring one missing
**Steps:**
1. Grep for a `data-wt` anchor and find nothing.
**Expected Result:** It may be built as a template literal or passed through a prop (`eauth-dns`, `ra-newest-export`, `recon-chip-0`) — don't announce "the anchor doesn't exist" from a literal grep.
**Automation Hint:** none (method).
**Source:** Part276

### TC-P14-066
**Category:** Architecture
**Test Name:** Files kept under 400 lines by splitting, not pinning
**Steps:**
1. Track files that crossed the limit during this stretch.
**Expected Result:** `QueryResultPanel.tsx` (420→375, SSE loop → `sqlExplainStream.ts`), `useTextToImageRunner.ts` (413→398), `Chatbot.tsx` (429→390), plus demo/recorder/doc splits — split, not pin-raise; `.md` not gated.
**Automation Hint:** `check-file-length.sh`.
**Source:** Parts272–278

---

**Total: 66 test cases, Parts 270–279.**
