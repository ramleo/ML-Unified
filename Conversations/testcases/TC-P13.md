# TC-P13 — Parts 260–269

**Prefix:** TC-P13
**Parts covered:** 260–269 (10 sessions)
**Status:** ✅ Complete
**Method:** Inline — no subagents; full line-by-line re-read of all 10 session logs.

Covers: the cybersecurity-tools sprint (password audit, DNS tunneling, SIEM triage, phishing classifier, TLS/headers, malicious-package, attack-surface, keystroke biometric, YARA, SAST merge); the app-safeguard `security/` layer (CORS/rate-limit/budget/body-size/file-gate/events) and its three live bugs; the site design audit + product/CV split + tool-description rewrite; the tools-section rebuild (ranked search, mobile cards, tag chips), the `globals.css` split and the 400-line CI gate; the area-page + photo-thumbnail redesign; the handbook built as a typeset book with 50 deep chapters, read-aloud, guided demos, phone PDF edition, search + chapter rail; and the critical `mm-ingest` entropy-rejection bug.

---

## Cybersecurity Tools Sprint (Part 260)

### TC-P13-001
**Category:** Feature
**Test Name:** Password audit uses zxcvbn-ts + HIBP k-anonymity (5-char prefix only)
**Steps:**
1. Enter `password123` then a random 20-char password.
**Expected Result:** Weak → "Very weak"/`pwned:true` (~2.27M hits); strong → "Very strong"/`pwned:false`; only the 5-char SHA-1 prefix is sent; nothing persisted.
**Automation Hint:** Playwright network assert (only prefix) + verdicts.
**Source:** Part260 (`127abea`)

### TC-P13-002
**Category:** Feature
**Test Name:** DNS tunneling detector requires entropy AND a second signal
**Steps:**
1. Feed a clean log, a tunneling burst, and a legit long CDN-subdomain log.
**Expected Result:** Flags a parent only when entropy (>4.0) AND length/volume cross together; the 48-char CDN log with low entropy stays unflagged.
**Automation Hint:** unit test on the heuristic with 3 fixtures.
**Source:** Part260 (`6728727`)

### TC-P13-003
**Category:** Feature
**Test Name:** SIEM triage groups client-side, judges server-side
**Steps:**
1. Paste a 13-line alert log.
**Expected Result:** `alertGrouping.ts` normalizes (IP→`<IP>`, digits→`#`) to top-20 groups; backend `siem_triage.py` returns priority+reasoning+action per group; suggestions phrased as "investigate", never "blocked".
**Automation Hint:** unit test grouping + API test judge.
**Source:** Part260 (`a1e0265`/`f1f17c0`)

### TC-P13-004
**Category:** Bug-Regression
**Test Name:** Alert grouping normalizes digit runs embedded in words
**Steps:**
1. Group 50 brute-force lines with varying users (`admin0`, `admin1`).
**Expected Result:** One group of 50 (the `\b\d+\b` word-boundary requirement was dropped), not 50 one-line groups.
**Automation Hint:** unit test with embedded-digit usernames.
**Source:** Part260

### TC-P13-005
**Category:** Feature
**Test Name:** Phishing classifier (Naive Bayes) scores + shows contributing words
**Steps:**
1. Classify a Nigerian-prince phishing email and an Enron business email.
**Expected Result:** 100% phishing (words: fund/deposited/nigeria) vs 0% safe (role/eric/mark); 90.95% held-out accuracy; model verdict + rule flags shown separately.
**Automation Hint:** TS scoring test vs the 154KB JSON artifact.
**Source:** Part260 (`2122861`)

### TC-P13-006
**Category:** Bug-Regression
**Test Name:** Phishing TS tokenizer exactly mirrors the Python trainer
**Steps:**
1. Tokenize 20 held-out emails in TS and Python.
**Expected Result:** Zero token/prediction mismatches, including reproducing one genuine misclassification; TS must not merge words across a stripped digit run.
**Automation Hint:** parity test TS vs Python tokenizer.
**Source:** Part260

### TC-P13-007
**Category:** Feature
**Test Name:** TLS/headers scanner does a real handshake + 6-header audit
**Steps:**
1. Scan `github.com` and `expired.badssl.com`.
**Expected Result:** github → TLS 1.3, verified, 5/6 headers (missing Permissions-Policy); expired → caught as "critical issues"; cert subject/issuer left unset when verification fails.
**Automation Hint:** API test on `tls_headers_check.py`.
**Source:** Part260 (`d6a0746`)

### TC-P13-008
**Category:** Architecture
**Test Name:** Live-network tools refuse internal addresses (SSRF guard)
**Steps:**
1. Scan `127.0.0.1` and `169.254.169.254`.
**Expected Result:** Both refused (private/loopback/link-local/reserved check); `github.com` allowed. Guard later extracted to shared `security_shared.py` and re-verified identical.
**Automation Hint:** unit test the IP classifier.
**Source:** Part260 (`bd830a0`)

### TC-P13-009
**Category:** Bug-Regression
**Test Name:** TLS verification uses certifi's CA bundle (not OS store)
**Steps:**
1. Verify a valid GitHub cert on macOS Python.
**Expected Result:** Succeeds via `ssl.create_default_context(cafile=certifi...)` (OS store falsely failed "unable to get local issuer").
**Automation Hint:** integration test on a valid cert.
**Source:** Part260

### TC-P13-010
**Category:** Feature
**Test Name:** Malicious package scanner flags install hooks + typosquats + code signals
**Steps:**
1. Scan a `package.json` with a postinstall hook + `lodahs` dependency; scan JS with `eval(atob(...))` + C2 URL.
**Expected Result:** install-script hook (content shown), Levenshtein typosquat vs ~150 known names, dynamic-exec/high-entropy/embedded-URL signals all flagged as evidence (not scored).
**Automation Hint:** unit test on 6 synthetic fixtures.
**Source:** Part260 (`fa64840`)

### TC-P13-011
**Category:** Feature
**Test Name:** Attack-surface scanner matches file content, not status codes
**Steps:**
1. Scan `github.com` for exposed `.git/.env/.DS_Store`, dir listing, CMS tag, open ports.
**Expected Result:** Flags a path only on 200 AND matching magic bytes/`ref: refs/`; WordPress detected on wordpress.org via `<meta generator>`; port 22 open on github (accurate); SSRF refusal on `127.0.0.1`.
**Automation Hint:** API test on `attack_surface_check.py`.
**Source:** Part260 (`bd830a0`)

### TC-P13-012
**Category:** Efficiency
**Test Name:** Attack-surface port check is parallelized
**Steps:**
1. Run the common-port check against a host with firewall-dropped ports.
**Expected Result:** ~6s via `ThreadPoolExecutor` (was ~18s sequential at 2s/port), identical results.
**Automation Hint:** timing assertion.
**Source:** Part260

---

## Keystroke Biometric, YARA, SAST Merge, App Safeguard (Part 261)

### TC-P13-013
**Category:** Feature
**Test Name:** Keystroke biometric uses scaled Manhattan distance
**Steps:**
1. Enroll a phrase 3×, then retype matching vs much slower.
**Expected Result:** Matching ≈ 0.13 (Low), slow ≈ 28.88 (High); raw distance shown, never a fabricated %.
**Automation Hint:** unit test on the distance scorer.
**Source:** Part261 (`f4686c1`)

### TC-P13-014
**Category:** Bug-Regression
**Test Name:** Keystroke dwell pairing finalizes on keyUp, not onChange
**Steps:**
1. Complete the phrase; capture the final character's dwell.
**Expected Result:** Finalization deferred to `onKeyUp` via `pendingFinalizeRef` — no negative dwell values (the completing `input` event fires before `keyup`).
**Automation Hint:** Playwright typing test asserting all dwell values positive.
**Source:** Part261

### TC-P13-015
**Category:** Feature
**Test Name:** YARA scanner runs built-in + custom rules with evidence
**Steps:**
1. Scan an EICAR file (built-in) and a user rule with a marker.
**Expected Result:** `/yara-scan/builtin` matches `EICAR_Test_File`; `/yara-scan/custom` matches at offset with hex; a broken rule surfaces `yara.SyntaxError` as a 400, no crash.
**Automation Hint:** API test on `yara_scan.py`.
**Source:** Part261 (`b71859b`)

### TC-P13-016
**Category:** Data
**Test Name:** YARA scanner enforces size/rule/timeout caps
**Steps:**
1. Submit >5MB file, >20KB rule, and a pathological regex.
**Expected Result:** 5MB file cap, 20KB rule cap, 5s match timeout all enforced.
**Automation Hint:** API tests for each cap.
**Source:** Part261

### TC-P13-017
**Category:** Feature
**Test Name:** SAST checks (secrets/SQLi/deserialization) merged into package scanner
**Steps:**
1. Scan code with `AKIA...`, an f-string SQL query, and `pickle.loads`/`yaml.load`.
**Expected Result:** CWE-798 (masked value, placeholder denylist), CWE-89, CWE-502 flagged; `cursor.execute(..., (user_id,))` and `yaml.safe_load` stay clean.
**Automation Hint:** unit test on 21 fixtures.
**Source:** Part261 (`288a519`)

### TC-P13-018
**Category:** Bug-Regression
**Test Name:** Dockerfile copies the new `security/` directory
**Steps:**
1. Deploy with the new `security/` package.
**Expected Result:** `COPY security/ security/` added (the explicit-per-dir Dockerfile had omitted it → `ModuleNotFoundError: security` → `RUNTIME_ERROR`); fixed `ed01afc`.
**Automation Hint:** Dockerfile grep + deploy smoke test.
**Source:** Part261

### TC-P13-019
**Category:** Bug-Regression
**Test Name:** Rate limiter keys off X-Forwarded-For, not the rotating proxy IP
**Steps:**
1. Fire 65 rapid requests from one client through HF's proxy.
**Expected Result:** `get_client_ip()` reads the first `X-Forwarded-For` entry; requests bucket to one client → 429 after the limit (was scattered across ~8 rotating `10.16.*` proxy IPs → no 429).
**Automation Hint:** unit test with consistent vs varying XFF.
**Source:** Part261 (`3981e86`)

### TC-P13-020
**Category:** Architecture
**Test Name:** App-level CORS cannot restrict access on HF Spaces (platform proxy)
**Steps:**
1. Request `/health` with a disallowed `Origin`.
**Expected Result:** Origin echoed back — HF's front-door proxy injects its own permissive CORS regardless of app config (`x-proxied-host` present). Documented honestly: rate-limit + budget caps are the real safeguards (Origin-independent).
**Automation Hint:** none (platform limitation, documented).
**Source:** Part261

### TC-P13-021
**Category:** Feature
**Test Name:** LLM-fallback routers enforce per-day budget + rate limit
**Steps:**
1. Call siem-triage/prompt-injection/ai-code/contradictions past the cap.
**Expected Result:** `@limiter.limit(LLM_LIMIT)` + `budget.check_and_record_call(...)` block anonymous cost-abuse of the server `MISTRAL_API_KEY`; body-size middleware 413s a 15MB payload.
**Automation Hint:** API tests for 429/413/budget-block.
**Source:** Part261 (`c0ab0a2`)

### TC-P13-022
**Category:** Architecture
**Test Name:** `file_gate` hard-blocks RAG ingest, advisory-logs malware triage
**Steps:**
1. Ingest an EICAR-laced file via `mm_ingest`; scan one via `mm_malware_image`.
**Expected Result:** `mm_ingest` rejects outright; `mm_malware_image` only logs (its purpose is analyzing suspicious files).
**Automation Hint:** API tests both paths.
**Source:** Part261

---

## Site Design Audit, Product/CV Split, Tool Descriptions (Part 262)

### TC-P13-023
**Category:** Bug-Regression
**Test Name:** Light-mode gradient headings meet AA contrast (all 4 palettes)
**Steps:**
1. Measure heading contrast against `#f0f4f8` in each palette, light mode.
**Expected Result:** All four were failing (emerald 1.51:1); after darkened hue-matched stops all ≥4.5:1; dark mode was always fine.
**Automation Hint:** computed-contrast assertion per palette.
**Source:** Part262 (`cb98bc0`)

### TC-P13-024
**Category:** Data
**Test Name:** Unverifiable performance claims removed sitewide
**Steps:**
1. Grep the site for hardcoded accuracy/confidence figures.
**Expected Result:** 96.7%, 100% Explainable, 91%/90.95%, 98.6%→1.1%, ASL 79%, PPE 0.72–0.88, wildlife 0.60/1.00 all removed; counts derived from `capabilities.length`/`registry.length`.
**Automation Hint:** grep assertion for stale figures.
**Source:** Part262 (`d33597d`)

### TC-P13-025
**Category:** Bug-Regression
**Test Name:** Homepage has no horizontal scroll on a true 390px viewport
**Steps:**
1. Cold-load `/` at 390×844 (CDP device emulation).
**Expected Result:** 0px overflow — `overflow-x: clip` on `#timeline` (framer `useIsMobile()` returned false on first render, applying desktop ±40px offsets on phones).
**Automation Hint:** Playwright device emulation; assert no overflow on cold load.
**Source:** Part262 (`0e53101`)

### TC-P13-026
**Category:** Bug-Regression
**Test Name:** Tool pages don't overflow on mobile (StepIndicator wraps)
**Steps:**
1. Load AutoML/Preprocessing/Feature-Eng/SHAP at 390px.
**Expected Result:** 0px overflow (was 285/173/72/11px) — non-active step labels hidden (403px→~90px), `.tool-header-row` wraps incl. nested breadcrumb.
**Automation Hint:** Playwright overflow check across tool pages.
**Source:** Part262 (`9c93c79`)

### TC-P13-027
**Category:** UI
**Test Name:** Product/CV split — `/` is product, `/about` is person
**Steps:**
1. Load `/` and `/about`.
**Expected Result:** `/` = hero/platforms/toolkit/architecture/pipeline/news; `/about` = about/skills/timeline/contact + Resume button (only on that route); nav leads with Tools; no "Home" link (logo is home).
**Automation Hint:** Playwright presence checks per route.
**Source:** Part262 (`24d74f7`/`67afafa`)

### TC-P13-028
**Category:** Bug-Regression
**Test Name:** Privacy page corrects misleading "runs locally" claims
**Steps:**
1. Read Face Liveness and Depth Parallax privacy descriptions.
**Expected Result:** Reworded — both POST to `/rag/mm-liveness`/`/rag/mm-depth` ("locally" meant our server); Multimodal RAG's persistent index called out as the real exception.
**Automation Hint:** content assertion.
**Source:** Part262 (`f6923ee`)

### TC-P13-029
**Category:** Bug-Regression
**Test Name:** Hash-only nav links resolve from any page
**Steps:**
1. Click a nav/footer section link from `/about`.
**Expected Result:** Full-path anchors (not bare `#capabilities`, which no-ops off-page); logo `href` goes home, not reloads the current page.
**Automation Hint:** Playwright nav from `/about`.
**Source:** Part262

### TC-P13-030
**Category:** Architecture
**Test Name:** A missed Vercel webhook is diagnosed via the deployments API
**Steps:**
1. Push a commit; confirm production serves it.
**Expected Result:** When CI is green but no deploy fired (missed webhook), re-fire with an empty commit — don't retry blindly; check the deployments API.
**Automation Hint:** none (deploy/process).
**Source:** Part262 (`f45e91e`)

---

## Tools-Section Rebuild + CSS Split + CI Gate (Part 263)

### TC-P13-031
**Category:** Bug-Regression
**Test Name:** Tool search matches title + tags + description, ranked
**Steps:**
1. Search "malware", "scanner", "security", "pdf", "zzz".
**Expected Result:** 2 / 4 / 22 / 2 / 0 results (was 0/0/0/0/0 — title-prefix only); `toolSearch.ts` ranks exact-title > title-contains > tag > description; terms <3 chars match word-starts only (`DEEP_MATCH_MIN_LENGTH`); multiple terms ANDed.
**Automation Hint:** unit test on the matcher.
**Source:** Part263 (`39c0828`)

### TC-P13-032
**Category:** Bug-Regression
**Test Name:** Mobile tool cards show the description (flip gated on hover)
**Steps:**
1. Load the tools grid at 390px.
**Expected Result:** Flip gated on `@media (hover:hover) and (min-width:769px)`; without hover the front carries description/tags/"Open ↗"; 0px overflow; tap navigates.
**Automation Hint:** Playwright mobile card check.
**Source:** Part263

### TC-P13-033
**Category:** Feature
**Test Name:** Tag filter chips derived from data (≥3 tools, domain-deduped)
**Steps:**
1. Inspect the chip row.
**Expected Result:** Local Compute 17, Client-Side 5, LLM 4, NLP 3, Privacy 3, RAG 3, Security Research 3, Static Analysis 3; single-select; combines with search+domain.
**Automation Hint:** Playwright assert chips + counts.
**Source:** Part263

### TC-P13-034
**Category:** Architecture
**Test Name:** `globals.css` split into ordered parts with no behavior change
**Steps:**
1. Reassemble the 10 parts and compare compiled CSS.
**Expected Result:** 833 lines → manifest + 10 numbered parts; identical content/order; compiled CSS byte-identical (75,264 bytes); same chunk hash. Load order is the contract (`09-mobile-late` must stay last).
**Automation Hint:** build + byte-compare.
**Source:** Part263 (`067fc83`)

### TC-P13-035
**Category:** Architecture
**Test Name:** CI fails the build on files over 400 lines
**Steps:**
1. Add a 401-line file; grow a pinned file; drop a pinned file under 400.
**Expected Result:** `check-file-length.sh` → FAIL new violation, FAIL pinned-grown, NOTE remove-entry; baseline is a debt register (pin-and-shrink), covers `.py/.ts/.tsx/.js/.jsx/.mjs/.css/.html` (not `.md`); runs on bash 3.2.
**Automation Hint:** run the gate against all 3 probe cases.
**Source:** Part263 (`03eae60`/`d9f46fc`)

### TC-P13-036
**Category:** UI
**Test Name:** Corner radii all resolve to the token scale (14/10px)
**Steps:**
1. Inspect card-sized elements on `/` and `/about`.
**Expected Result:** Every one is `--radius-card` (14) or `--radius-sm` (10); 13 literals across 8 components corrected; nav/footer logo both 10px.
**Automation Hint:** grep served HTML for literals (expect 0) + token usages.
**Source:** Part263 (`2ddde2c`)

---

## Area Pages, Photo Thumbnails, Handbook-as-Book (Part 264)

### TC-P13-037
**Category:** UI
**Test Name:** Home shows area section tiles, not 50 tool cards
**Steps:**
1. Load `/`; load each of 4 area routes.
**Expected Result:** Home = 1 big + 1 wide + 2 small tiles, zero tool cards; `/tools/ml-pipeline|language|computer-vision|security` return 200; bogus slug 404s; all 51 tool routes still 200.
**Automation Hint:** Playwright route checks.
**Source:** Part264 (`06a7d65`)

### TC-P13-038
**Category:** Feature
**Test Name:** Every tool card has a photograph thumbnail
**Steps:**
1. Load the Security area (21 cards).
**Expected Result:** 21 images, 0 broken, 21 unique URLs; all 50 thumbnail files 200.
**Automation Hint:** Playwright image-load assertion.
**Source:** Part264 (`e7777b2`)

### TC-P13-039
**Category:** UI
**Test Name:** One shared card surface across all card types
**Steps:**
1. Compare computed style of platform cards, pipeline stages, architecture stages, domain tiles.
**Expected Result:** Identical fill `rgba(17,24,39,0.6)`, border, 14px radius, shadow; accents ≥4.01:1 both themes.
**Automation Hint:** computed-style signature compare.
**Source:** Part264 (`72bf215`/`d9fd111`)

### TC-P13-040
**Category:** Feature
**Test Name:** Handbook is a typeset book generated from app data
**Steps:**
1. Run `build-handbook.py`; open `/handbook`; download PDF.
**Expected Result:** 4 parts/36→41 chapters/appendix, ~106 pages; content from `capabilities.ts`/`registry.json`/`userGuide.ts`; CI `handbook` job fails if the `.md` is stale.
**Automation Hint:** build + contents-resolve check.
**Source:** Part264 (`edf9d48`/`e1e99ef`)

### TC-P13-041
**Category:** Bug-Regression
**Test Name:** Handbook tables render (remark-gfm)
**Steps:**
1. Open a chapter with a facts table.
**Expected Result:** Renders as a table, not literal pipes (remark-gfm added).
**Automation Hint:** DOM assert `<table>` present.
**Source:** Part264

### TC-P13-042
**Category:** Bug-Regression
**Test Name:** Deep-chapter file names key off capability id, not route
**Steps:**
1. Confirm `docs/chapters/featureeng.md` (not `feature-engineering.md`).
**Expected Result:** Generator keys off `capabilities.ts` id; "Find it at" uses `internalLink` (two ids differ from route — `/tools/featureeng` would 404).
**Automation Hint:** grep chapter filenames vs ids.
**Source:** Part264 (`eeb085a`)

### TC-P13-043
**Category:** Bug-Regression
**Test Name:** "Where it runs" reflects client-side tools
**Steps:**
1. Check the At-a-glance row for Preprocessing and Feature Engineering.
**Expected Result:** "In the browser" — both carry a `Local Compute` tag now (`preprocessCSV`/`applyTransforms` have no network call); previously printed "On the server".
**Automation Hint:** book content + tag-chip assertion.
**Source:** Part264

---

## 50 Deep Chapters + Handbook Reading (Parts 265–266)

### TC-P13-044
**Category:** Architecture
**Test Name:** All 50 tools have a deep chapter (coverage audit)
**Steps:**
1. Compare ids in `capabilities.ts` to `docs/chapters/*.md`.
**Expected Result:** 50/50, missing NONE; each follows the 7-point template ending in "Likely interview questions".
**Automation Hint:** coverage script.
**Source:** Part265

### TC-P13-045
**Category:** Data
**Test Name:** Deep chapters record the real (sometimes surprising) mechanics
**Steps:**
1. Spot-check the Feature-Selection, Ensemble, Drift, Text-to-Image, Face-Liveness chapters.
**Expected Result:** FS "mutual information" is `-0.5*log(1-r^2)` (linear only); Ensemble page doesn't ensemble (voting/stacking is Pipeline Builder); Drift baseline is scaler mean/std, not training data; Text-to-Image `seed` does nothing; Face-Liveness returns a score not a verdict — all written from code, card marked wrong where it disagrees.
**Automation Hint:** manual content review.
**Source:** Part265

### TC-P13-046
**Category:** Bug-Regression
**Test Name:** Handbook reading page shows chapter titles and table headers
**Steps:**
1. Open a chapter.
**Expected Result:** Titles visible (`.hb-body h1{display:none}` removed), em-phrases not uppercased, table headers present (`thead{display:none}` removed).
**Automation Hint:** DOM assert headings/thead.
**Source:** Part265 (`7fed136`)

### TC-P13-047
**Category:** UI
**Test Name:** Phone PDF edition typesets at 90×150mm
**Steps:**
1. Download the phone-edition PDF.
**Expected Result:** 90×150mm, 11pt → effective ~8.3pt on a 68mm screen (vs A4's 3.3pt); one override after `book.css`; 1,165 pages.
**Automation Hint:** measured page geometry.
**Source:** Part266 (`41cddfc`)

### TC-P13-048
**Category:** Bug-Regression
**Test Name:** "Back to the handbook" exit from the typeset view
**Steps:**
1. Click "Download as PDF", then exit.
**Expected Result:** A portalled (to `<body>`) exit button removes `bk-paginated` and empties `#bk-pages` (print CSS hides its natural parent); next PDF typesets fresh.
**Automation Hint:** Playwright click-through.
**Source:** Part266 (`fa200a4`)

### TC-P13-049
**Category:** Bug-Regression
**Test Name:** Paged.js stylesheet doesn't repaint the live site
**Steps:**
1. Request a PDF while in dark theme; sample body background during typesetting.
**Expected Result:** Stays `rgb(10,15,30)` throughout, restored on exit — `book.css` document-level rules scoped to `.pagedjs_page` (@media print is NOT a guard; Paged.js hoists print rules).
**Automation Hint:** sample background during typeset.
**Source:** Part266 (`973509e`)

### TC-P13-050
**Category:** Bug-Regression
**Test Name:** Contents folios align right (flex, not float)
**Steps:**
1. Render the contents at 78mm width.
**Expected Result:** All rows share a right edge, every row has its folio (right floats dropped lines; a flex item cannot leave its line).
**Automation Hint:** measure folio x-positions.
**Source:** Part266

### TC-P13-051
**Category:** Architecture
**Test Name:** Never `git add -A` (49MB wrong-repo push lesson)
**Steps:**
1. Commit work with explicit pathspecs + `git -C <abs path>`.
**Expected Result:** No `chroma.sqlite3`/untracked files swept in; bash cwd drift does not cause a wrong-repo commit; artifacts gitignored.
**Automation Hint:** none (process; `feedback_never_git_add_all`).
**Source:** Part266

---

## Read-Aloud, Guided Demos, and the Ingest Bug (Part 267)

### TC-P13-052
**Category:** Feature
**Test Name:** Handbook read-aloud speaks continuously (queue 3 deep)
**Steps:**
1. Start the Listen bar on a chapter.
**Expected Result:** Utterances queued ahead so there's no gap between sentences; em-dashes→commas etc. so it doesn't hard-stop mid-clause; tables/code skipped; best installed voice chosen (novelty voices filtered, 41→22).
**Automation Hint:** Playwright — assert speaking + block highlight, tables skipped.
**Source:** Part267 (`122175a`)

### TC-P13-053
**Category:** Feature
**Test Name:** Guided demo drives the real tool from one JSON script
**Steps:**
1. Click "Watch this work" on AutoML.
**Expected Result:** Same-origin iframe; spotlight over the real control via `data-wt` anchors; reaches Config (240 rows, 10 cols, target churned); never presses a paid button or restyles the demoed page.
**Automation Hint:** Playwright live demo assertion.
**Source:** Part267 (`a8bad14`)

### TC-P13-054
**Category:** Architecture
**Test Name:** Narration presenter is swappable (browser/BYO-TTS any provider)
**Steps:**
1. Configure a custom TTS endpoint (URL, header, body, audio dot-path).
**Expected Result:** `getPresenter()` abstraction; any provider is data (prefilled presets are not privileges); PCM gets a WAV header; key in memory only, settings (not key) remembered.
**Automation Hint:** config an invented endpoint; assert request shape + no key persisted.
**Source:** Part267 (`127e6b7`/`ffad41b`)

### TC-P13-055
**Category:** Bug-Regression
**Test Name:** `mm-ingest` no longer rejects every compressed file
**Steps:**
1. Ingest an ordinary PDF/JPEG/WebP; then one with EICAR appended.
**Expected Result:** Compressed files pass (the `High_Overall_Entropy` >7.5 rule is `ADVISORY_RULES`, checked via `blocking_matches()`); EICAR still rejected. (Bug live 29 Aug–31 Aug rejected every real file.)
**Automation Hint:** API test both directions.
**Source:** Part267 (`6974290`)

### TC-P13-056
**Category:** Architecture
**Test Name:** Advisory YARA rules never block any caller
**Steps:**
1. Audit all file_gate callers.
**Expected Result:** 31 other sites log-and-continue; only `mm_ingest` blocks, and only on non-advisory matches.
**Automation Hint:** grep callers + unit test `blocking_matches()`.
**Source:** Part267

### TC-P13-057
**Category:** Bug-Regression
**Test Name:** Demo recorder fails loudly and asserts rendered state
**Steps:**
1. Record a demo where a backend call fails mid-run.
**Expected Result:** Actions no longer wrapped in `.catch(()=>{})`; an `expect` step asserts on-screen content (caught a real `Failed to fetch`); locator matches the anchor whether it IS or CONTAINS the field; audio padded to measured step length.
**Automation Hint:** recorder self-test with a failing step.
**Source:** Part267 (`ddc3a0e`)

---

## More Guided Demos + Recorder Faults (Part 268)

### TC-P13-058
**Category:** Bug-Regression
**Test Name:** `expect` reads page content excluding the demo caption
**Steps:**
1. Run a step whose `say` text contains its own `expect` string.
**Expected Result:** Assertion reads `body.children` minus `#__demo_cap`/`#__demo_spot` — a caption can't satisfy its own check; step-4 tightened to the exact rule name.
**Automation Hint:** recorder unit test.
**Source:** Part268 (`1fbcd74`)

### TC-P13-059
**Category:** Bug-Regression
**Test Name:** Recorder preflight blames the backend, not the demo
**Steps:**
1. Record against a dead backend.
**Expected Result:** Preflight (`requestfailed` + `response>=500` listeners) aborts in ~1.1s naming the URL/errno — not a 2-minute run ending in a misleading "expected X on screen"; checked before `expect`.
**Automation Hint:** recorder self-test, backend down.
**Source:** Part268 (`b216582`)

### TC-P13-060
**Category:** Bug-Regression
**Test Name:** Spotlight re-measures after scroll/settle/action
**Steps:**
1. Record a demo where a clicked panel shifts layout.
**Expected Result:** `place()` called after a 600ms settle, after `waitFor`, and after any action — box frames the right element (async `scrollIntoView` had frozen it). (Later fully fixed so a vanished anchor hides the box — `dd67442`.)
**Automation Hint:** extracted-frame review.
**Source:** Part268 (+Part271 correction)

### TC-P13-061
**Category:** Bug-Regression
**Test Name:** Demo assertions compare text case-insensitively
**Steps:**
1. Assert a label styled `text-transform: uppercase`.
**Expected Result:** Compare case-insensitively (`innerText` returns the rendered uppercase; the JSX doesn't say so).
**Automation Hint:** recorder unit test.
**Source:** Part268

### TC-P13-062
**Category:** Architecture
**Test Name:** Rebuild requires a server restart before recording
**Steps:**
1. Rebuild then record without restarting `next start`.
**Expected Result:** Must restart (`lsof -ti:PORT | xargs kill`) — `next start` serves the `.next` from launch time; a stale build served an old bundle.
**Automation Hint:** none (procedure).
**Source:** Part268

---

## Handbook Search + Chapter Rail (Part 269)

### TC-P13-063
**Category:** Feature
**Test Name:** Handbook search walks the DOM and paints via CSS Highlight API
**Steps:**
1. Search "entropy"; then download the PDF.
**Expected Result:** Reports hits-per-chapter; highlights via `CSS.highlights` (zero `<mark>` in `.hb-body`, so the PDF isn't polluted — `makeBook()` feeds `.hb-body.innerHTML` to Paged.js).
**Automation Hint:** assert 0 `<mark>`, N ranges painted.
**Source:** Part269 (`2c10e82`)

### TC-P13-064
**Category:** Bug-Regression
**Test Name:** Search bar is visible below the fixed navbar
**Steps:**
1. Scroll deep; hit-test the search bar's center.
**Expected Result:** `elementFromPoint` returns the input, not NAV — bar pins at `top: var(--hb-nav-h)` (was painted over at `top:0`); page wrapper uses `overflow-x: clip` (not `hidden`, which kills descendant `position: sticky`).
**Automation Hint:** `elementFromPoint` at multiple scroll depths.
**Source:** Part269

### TC-P13-065
**Category:** Bug-Regression
**Test Name:** Substring + contents indexing in handbook search
**Steps:**
1. Search "curity", "security & trust", "security and trust".
**Expected Result:** `curity` → 66 hits/23 chapters (opt-in substring flag on `wordsMatch`); contents is indexed/labelled `Contents`; `and`/`or` are skippable, `&` handled; part groups read "Part 4 · Security & Trust".
**Automation Hint:** query-count assertions.
**Source:** Part269

### TC-P13-066
**Category:** Feature
**Test Name:** Chapter rail scrubs/jumps a 387,000px page
**Steps:**
1. Click the Chapter 50 tick; press 25% down the rail.
**Expected Result:** 44px full-height rail, 54 ticks (50 chapters + 4 parts), amber current marker; click puts the heading at top:0; 25% press scrolls to ~96,396px; inset to clear the navbar.
**Automation Hint:** Playwright rail interaction.
**Source:** Part269

### TC-P13-067
**Category:** Bug-Regression
**Test Name:** Search field undo works (manual history, controlled input)
**Steps:**
1. Type "entropy", clear via ×, press Cmd-Z / Ctrl-Z.
**Expected Result:** Restores "entropy" + 106 highlights (a controlled React input loses the native undo stack); 50-step history, snaps to the 150ms debounce, undo isn't itself recorded; redo via Ctrl+Shift+Z/Ctrl+Y; works on Windows too.
**Automation Hint:** keyboard history test both platforms.
**Source:** Part269 (`4894b39`)

### TC-P13-068
**Category:** Bug-Regression
**Test Name:** `color-mix()` is flattened by this build — use literal rgba
**Steps:**
1. Inspect the current-hit highlight color.
**Expected Result:** Literal `rgba(251,191,36,0.32)` / solid `#fbbf24` (a `color-mix()` resolved to its first arg, so every hit painted at full strength and the current one was indistinguishable).
**Automation Hint:** computed highlight color check.
**Source:** Part269

---

## Cross-cutting / Process (Parts 260–269)

### TC-P13-069
**Category:** Architecture
**Test Name:** The 400-line rule applies to every extension (CSS included)
**Steps:**
1. Check `globals.css` and generator scripts against the gate.
**Expected Result:** No code-vs-CSS exemption; `globals.css` split before further edits; `build-handbook.py` split (`handbook_sources.py`) when `wrap_sections` pushed it over; split FIRST, don't ship-then-flag; `.md` is not gated.
**Automation Hint:** `check-file-length.sh`.
**Source:** Parts263–268

### TC-P13-070
**Category:** Architecture
**Test Name:** Never delete untracked user files with a wildcard rm
**Steps:**
1. Clean up session-created screenshots.
**Expected Result:** Only files created this session, named individually, are removed (a batch `rm -f` destroyed an untracked `bbox_fix_comparison.html`); `feedback_never_delete_user_files`.
**Automation Hint:** none (process).
**Source:** Part262

### TC-P13-071
**Category:** Architecture
**Test Name:** Verify UI visibility with hit-testing/headed Chrome, not geometry alone
**Steps:**
1. Validate a sticky/fixed element.
**Expected Result:** `getBoundingClientRect` proving position is not visibility; use `elementFromPoint` and headed real Chrome (`channel:"chrome", headless:false`) — local headless returns blank on this machine.
**Automation Hint:** none (method; `feedback_sticky_must_clear_navbar`).
**Source:** Parts268–269

### TC-P13-072
**Category:** Architecture
**Test Name:** A guided demo is the strongest end-to-end test of a tool
**Steps:**
1. Record a demo for a shipped tool.
**Expected Result:** Exercises ingest/compute/render as a user would — this is how the 2-day `mm-ingest` outage was found; narration describes mechanism, not one run's model output.
**Automation Hint:** none (method).
**Source:** Part267

### TC-P13-073
**Category:** Architecture
**Test Name:** Verify a claim/number against a live source before narrating it
**Steps:**
1. Write demo narration citing a figure.
**Expected Result:** Figure fetched live first (HIBP counts, header presence, YARA offsets) — zero batch-2 recordings failed on content; a negative security test that passes may be a broken test (malformed EICAR printf).
**Automation Hint:** none (method).
**Source:** Part268

---

**Total: 73 test cases, Parts 260–269.**
