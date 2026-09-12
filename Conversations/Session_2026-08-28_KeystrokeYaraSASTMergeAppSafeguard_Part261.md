# Session 2026-08-28 (Part 261) — Keystroke demo, YARA scanner, SAST merge, and a full app-safeguard pass

Continues directly from Part 260, which closed the original 6-item cybersecurity
shortlist plus the Attack-Surface Scanner. This session closed the remaining
2026-08-28 deeper-triage backlog (Keystroke Biometric Auth-Risk Demo, YARA File
Scanner, AI-Powered SAST Scanner), then pivoted to a much bigger ask: the user
wanted to actually safeguard the live app itself from real attacks, self-built
now with an explicit design requirement that upgrading to paid tools later must
be a smooth swap, not a rearchitecture. That safeguard work surfaced three real,
live bugs — one deploy-breaking, two silent — all found via hands-on verification
against the actual deployed backend, not assumed from code review.

## 1. Keystroke Biometric Auth-Risk Demo

New standalone, fully client-side tool `/tools/keystroke-biometric-auth-risk`
(zero backend). Real, published technique confirmed via web search before
building: **scaled Manhattan distance** (per-feature absolute deviation from an
enrolled mean, normalized by that feature's own std dev) is a top-performing,
published classifier for keystroke-dynamics anomaly detection (CMU's Killourhy
& Maxion benchmark, ~0.09 EER reported in follow-on work) — not invented for
this project. User types a fixed phrase ("the quick fox") 3 times to enroll a
per-character dwell-time (keydown→keyup) and flight-time (keyup→next keydown)
profile, then retypes once more to get a live Low/Medium/High risk band plus
the raw scaled-distance number — never a fabricated percentage confidence.

**Real bug caught via live Playwright verification, the same class of subtlety
this project has hit before with timing-sensitive DOM code**: the browser's
native `input` event (which drives React's `onChange`, checking whether the
typed value matches the phrase) fires *before* `keyup` for the character that
completes the phrase — true in real browsers generally, not a test-script
artifact. Finalizing the attempt directly in `onChange` (the original design)
left that final `keyup` to land in the *next* attempt's event buffer instead,
shifting every subsequent dwell pairing by one index and producing garbage
negative dwell values (a live test showed dwell values like -73ms alongside
plausible ~240ms flight values — flight is computed from the downs array alone
so it stayed correct, which was the tell that pinpointed the bug to dwell
pairing specifically, not general capture). Fixed by deferring finalization
from `onChange` to `onKeyUp`, using a `pendingFinalizeRef` flag checked once
down/up counts are actually balanced again. Re-verified live after the fix: a
matching-style retype scored 0.13 (Low) with all 13 dwell (~95ms) and 12 flight
(~72ms) values positive and accurate; a deliberately much-slower retype scored
28.88 (High); phrase-mismatch/typo retypes correctly rejected and re-prompted.
Guide honestly discloses this is a single-session concept demo (thresholds set
from a handful of test typings), not a population-calibrated production
authenticator. ml-portfolio commit `f4686c1`.

## 2. YARA File Scanner

New standalone tool `/tools/yara-file-scanner`. Runs the real, industry-standard
**YARA** pattern-matching engine via `yara-python` — verified hands-on before
committing to it (not assumed from the library's reputation): installed 4.5.4
in a scratch venv, compiled a rule matching the EICAR test string, confirmed it
matched a real EICAR buffer and correctly missed random bytes, and confirmed
PyPI ships prebuilt manylinux wheels (no libyara compile step needed on the
Space's Linux x86_64 Docker target).

Two backend endpoints (`services/ml-api/routers/yara_scan.py`, new top-level
router convention matching this session's `tls_headers_check.py`/
`attack_surface_check.py`, not the older `routers/rag/mm_*` convention):
- `/yara-scan/builtin` — a small, **self-authored** 7-rule educational set
  (EICAR signature, PowerShell `-EncodedCommand`/base64 LOLBin pattern, PHP
  webshell `eval`+`base64_decode`+`$_POST`/`$_GET`, Office macro `AutoOpen`/
  `Document_Open`+`Shell`/`CreateObject`, embedded-PE-in-non-exe smuggling via
  the real `"This program cannot be run in DOS mode"` marker, Python
  reverse-shell `socket`+`subprocess`+`connect()`, and a genuine YARA
  `math.entropy()` module rule flagging >7.5 bits/byte) — explicitly disclosed
  as a demo set, NOT a pulled third-party threat-intel feed whose licensing
  wasn't verified, same "curated, disclosed as not exhaustive" pattern as the
  QR Phishing Detector's brand list.
- `/yara-scan/custom` — compiles and runs a **user-supplied** YARA rule against
  the uploaded file, judged the more important half of the tool since testing
  a hand-written detection rule against a real sample is YARA's actual
  everyday use case, not just running a fixed scanner.

Hardening: 5MB file cap, 20KB rule-source cap, YARA's own 5-second match
timeout (guards a pathological custom regex). All 7 built-in rules
unit-verified locally before any FastAPI code existed — each fired on a
hand-crafted positive sample and stayed silent on a shared benign-text negative
control, zero false positives. Custom-rule path verified too: a deliberately
broken rule (`condition tru` — missing colon) correctly raised
`yara.SyntaxError`, surfaced as a real compiler-message 400; a valid custom
rule correctly matched its target with real offset/hex evidence. Deployed and
verified live via direct curl against the HF Space before any frontend work:
built-in scan against a real EICAR payload correctly matched; the broken-syntax
and valid-custom-rule cases reproduced identically. Frontend built with a mode
toggle (Built-in rules / Write your own rule, pre-filled with a working example)
and verified live end-to-end via Playwright: uploading a real EICAR test file
showed 1 matched rule with full evidence; the pre-filled custom rule matched
correctly; the broken-syntax rule surfaced the real compile error inline with
no crash. Backend `services/ml-api` commit `b71859b`; frontend `ml-portfolio`
commit `1db26a9`.

## 3. AI-Powered SAST Scanner — merged into Malicious Package Scanner, not built standalone

User's explicit choice (asked via AskUserQuestion) after I laid out that this
backlog item substantially overlapped with the Malicious Package Scanner's
existing source-code-scan mode. Added 3 genuinely new, well-documented
vulnerability classes to `packageScanHeuristics.ts` rather than building a
separate tool page:
- **Hardcoded secrets** (CWE-798) — recognizable real secret-format prefixes
  (AWS `AKIA...`, GitHub `ghp_`/`github_pat_`, Slack `xox...`, PEM private-key
  blocks) plus a generic `api_key`/`password`/`token = "..."` assignment
  pattern, with a placeholder denylist (`changeme`, `your-password`, etc.) to
  cut noise from docs/config examples. Matched values shown partially masked.
- **SQL-injection-shaped query building** (CWE-89) — a SQL keyword combined
  with an f-string, template-literal, string-concatenation, or `%`-format
  interpolation, rather than a parameterized placeholder.
- **Insecure deserialization** (CWE-502) — Python's `pickle.loads`/
  `marshal.loads`, and `yaml.load(` used without `SafeLoader` on the same line
  (PyYAML's own documented fix).

Deliberately did NOT add an LLM-judge layer (the "AI-Powered" half of the
original idea): every other check in this tool is a plain heuristic with real
matched evidence, never a fabricated verdict, and adding an LLM opinion to only
3 of 8 checks would have been an inconsistent half-built feature — noted as a
possible uniform future addition, not part of this merge. All 3 new checks
unit-verified against 21 synthetic positive/negative cases with zero false
positives (placeholder passwords, a parameterized `cursor.execute(...,
(user_id,))` query, and `yaml.safe_load` all correctly stayed clean) before
touching the UI; re-verified live via Playwright — the existing "Try a
suspicious example" sample was extended to demonstrate all 6 checks in one
pass, and a separate clean snippet correctly showed "No suspicious findings."
ml-portfolio commit `288a519`. **This closed the entire 2026-08-28
cybersecurity deeper-triage backlog.**

## 4. "Can I use these tools to safeguard my own app?" — direct answer, no build

User asked whether the 10 cybersecurity tools built across this session and
Part 260 could protect the app itself. Answered directly without building
anything: TLS/Security-Headers Scanner and Attack-Surface Scanner are directly
usable by pointing them at the live domains; Malicious Package Scanner (with
the merged SAST checks) is directly usable by pasting the repo's own
`package.json`/source files; Email Auth Checker and Prompt Injection Playground
apply if relevant; YARA File Scanner could be wired into real upload paths as
actual protection rather than a manual demo. Most others (Password Audit, DNS
Tunneling Detector, Keystroke demo, Phishing Classifier, SIEM Triage, QR
Phishing Detector) don't apply to protecting this app's own infrastructure.
Flagged the honest caveat: these are manual/on-demand tools with disclosed
heuristic limits, not a substitute for a real pentest or enterprise scanner.

## 5. The App Safeguard Plan — self-built now, smooth swap to paid later

User's actual ask: build something that safeguards the app now, self-built,
structured so a later swap to paid tools is smooth, not a rearchitecture.
Entered plan mode; before designing anything, spawned an Explore agent to
audit the ACTUAL current security posture rather than assume gaps. Real,
confirmed findings (not hypothetical):
- **CORS wide open**: `allow_origins=["*"]` on the FastAPI backend.
- **Zero rate limiting anywhere** — no library, no hand-rolled throttling,
  across all 54 routers.
- **Zero authentication on every route** — the entire backend is public.
- **No global request-body-size cap** — only a handful of routers cap uploads
  individually at 5MB.
- **A real, confirmed cost-abuse vector**: `siem_triage.py`,
  `prompt_injection_check.py`, `ai_code_detector.py`, and `contradictions.py`
  all fall back to the project's own server-side `MISTRAL_API_KEY` when a
  caller doesn't supply one — meaning any anonymous visitor could run up the
  project owner's Mistral bill with zero limit, the same failure mode
  `_image_gen_budget.py` already guards against for Gemini image generation
  (built after a real prior incident — see that file's own docstring).
- **No security headers at all on the frontend** (`next.config.ts` had no
  `headers()`).
- **No Dependabot/renovate, no secret-scanning CI** in either repo.
- Secrets themselves were handled correctly (env vars only, nothing
  committed, `.gitignore` correct) — confirmed not a gap.

Verified `slowapi` (the real, standard FastAPI/Starlette rate-limiting
library) installs cleanly as a pure-Python wheel (0.1.10, no native compile)
and, in a scratch FastAPI app, correctly returned 200×3 then 429×2 against a
3/minute-limited route — the concrete tool the plan used, not invented from
scratch. Also confirmed `limits` (slowapi's backing package) genuinely
supports a Redis storage backend (`storage_uri`), the documented swap point
for running multiple instances later.

**Core design principle for "smooth transition to paid"**: every safeguard
concern gets one small module with one stable function signature, called from
exactly one place, with its *implementation* chosen by an env var — routers
never call a specific vendor/library directly. New `services/ml-api/security/`
package, one file per concern:
- `origin_policy.py` — CORS allowlist (real Vercel domain + localhost) plus a
  regex for Vercel preview-deployment subdomains, replacing the `["*"]`
  wildcard.
- `rate_limit.py` — wraps `slowapi.Limiter` with `default_limits` (blanket
  coverage on all undecorated routes via `SlowAPIMiddleware`) plus a stricter
  `@limiter.limit(...)` tier for LLM-judge routes.
- `budget.py` — generalizes the already-proven `_image_gen_budget.py`
  daily-cap pattern, applied to the 4 confirmed server-key-fallback routers.
- `body_size.py` — global 10MB request-body cap, defense-in-depth beneath the
  per-router upload caps.
- `file_gate.py` — wraps the already-shipped YARA built-in ruleset as a real
  pre-processing gate other routers can call, turning the standalone scanner
  into actual wired-in protection.
- `events.py` — one `log_security_event()` function emitting fixed-schema JSON
  lines to stdout (HF Spaces already captures stdout as logs, free today) —
  the swap point for a future paid log drain (Datadog/Sentry/Better Stack).

A concrete "paid-upgrade table" was written into the plan mapping each concern
to its free-now implementation and its later paid replacement (Cloudflare/AWS
WAF for rate limiting, VirusTotal/ClamAV for file scanning, Snyk/Socket.dev for
dependency scanning, GitGuardian for secrets, Datadog/Sentry for logging,
Lakera Guard for prompt-injection defense) — in every case the "what changes"
column is one module's internals or a DNS/proxy config change, never the ~50
routers or the frontend pages. User approved building all 8 items in one pass
rather than a smaller first cut.

### Implementation

- Wired `origin_policy`/`rate_limit`/`body_size` into `app.py` as global
  middleware ahead of the existing request-timing `_monitor` middleware.
- Applied `@limiter.limit(LLM_LIMIT)` + `budget.check_and_record_call(...)` to
  all 4 confirmed cost-abuse routers (`siem_triage.judge_alerts`,
  `ai_code_detector.judge_code`, `prompt_injection_check.check_prompt_injection`,
  `contradictions.check_contradictions`/`check_reconciliation`) — each needed a
  `request: Request` parameter added since slowapi's decorator requires it.
- Wired `file_gate.scan_upload_bytes()` into `mm_ingest.py` (the main RAG
  upload pipeline) as a **hard block** — none of its accepted content types
  (PDF/image/CSV/video/audio) should ever contain an embedded executable/EICAR
  pattern, so a match there is high-confidence and worth rejecting outright —
  and into `mm_malware_image.py` as an **advisory log only**, since that
  tool's whole purpose is analyzing potentially-malicious-looking files, so
  blocking would defeat it.
- Added `.github/dependabot.yml` to both repos (pip ecosystems for all 4
  ML-Unified services, npm for ml-portfolio, plus github-actions in both) and
  a `gitleaks` secret-scanning job to both repos' existing CI workflows.
- Added `next.config.ts` `headers()` setting the same 6 headers this project's
  own TLS/Security-Headers Scanner checks for — deliberately a **permissive
  CSP baseline**, not a hardened lockdown, since a full audit of every one of
  ~60 tool pages' external resource usage (MediaPipe CDN, backend API domains,
  Supabase, etc.) wasn't done in this pass; tightening it further is future
  work, not silently overclaimed as done. Permissions-Policy explicitly
  **allows** camera/microphone for the origin (not blocks), since 5 real tools
  (face-liveness, pose-vj-visuals, video-keystroke-inference, etc.) need them.

### Verification — and three real, live bugs found

Every module was first verified functionally in a scratch venv importing the
*actual* project files (not reimplemented copies): CORS allowlist/regex
correctly distinguished the real Vercel domain, a Vercel preview subdomain,
and a random disallowed origin; the strict LLM rate-limit tier correctly
allowed 10 requests then 429'd; the budget cap correctly allowed 3 then
blocked; the body-size middleware correctly 413'd a 15MB payload; the file
gate correctly flagged a real EICAR buffer and stayed clean on ordinary text.
The frontend build was verified with `tsc`/`eslint`/`next build` clean, and a
live Playwright pass confirmed the new headers actually appear on responses.

**Bug #1 — real, deploy-breaking, found immediately on first deploy attempt**:
after pushing and uploading the changed `.py` files to the HF Space, the Space
entered `RUNTIME_ERROR`: `ModuleNotFoundError: No module named 'security'`.
Root-caused via the Space's own real error log (not guessed): the
`services/ml-api/Dockerfile` copies each top-level source directory
*explicitly* (`COPY routers/ routers/`, `COPY shared/ shared/`, etc.) rather
than the whole build context, and had no line for the brand-new `security/`
directory, so it never made it into the built image. Fixed with one added
`COPY security/ security/` line, committed (`ed01afc`), re-uploaded, redeployed
— confirmed `RUNNING` with a real `/health` 200 and the Space's git SHA
matching the fix.

**Bug #2 — real, silent, found only because the user pushed back on a
premature "all good" claim**: after the successful redeploy, a live CORS test
(`curl` with `Origin: https://evil-scraper.example.com` against `/health`)
showed the origin echoed back in `Access-Control-Allow-Origin` — meaning the
restriction wasn't taking effect. Rather than accept this, direct evidence was
gathered: a request with **no** `Origin` header at all still returned
`Vary: origin, access-control-request-method, ...` — and Starlette's actual
`CORSMiddleware.__call__` source (read directly, not recalled) shows it exits
immediately and touches nothing when `origin is None`. That proves those
headers cannot be coming from the app's own middleware; they're injected by
Hugging Face Spaces' own front-door proxy (visible via `x-proxied-host`/
`x-proxied-replica` response headers present on every request), which applies
its own permissive CORS policy in front of the container regardless of what
the app sends. **Conclusion, stated honestly rather than papered over**:
app-level CORS restriction does not achieve real access control on this
specific hosting platform — it's a genuine platform limitation, not fixable
from the app side. The practical implication: CORS was never going to stop a
direct script/curl call anyway (it only affects browser-based cross-origin
JS); the rate limiter and budget caps are the safeguards that actually matter
against real abuse, since neither depends on Origin headers.

**Bug #3 — real, silent, found via the same live-testing discipline**: firing
65 rapid requests at the live `/health` endpoint returned 65×200, zero 429s,
even though the identical middleware composition had just been proven correct
in a local repro (200×3-then-429 on an undecorated route). Root-caused
directly from the Space's own request logs (not guessed): the `GET /health`
lines showed roughly 8 different source IPs (`10.16.28.33`, `10.16.35.205`,
`10.16.7.21`, `10.16.44.122`, etc.) across those 65 requests from one real
client — `request.client.host` (what slowapi's `get_remote_address` reads) is
just the last TCP hop before uvicorn, and on this platform that's a rotating
pool of Hugging Face's own internal proxy IPs, not the real caller. This
scattered what should have been one rate-limit bucket across ~8 buckets that
each stayed under the 60/minute threshold. Fixed with a `get_client_ip()`
function reading the first entry of `X-Forwarded-For` (the real client IP any
reverse proxy forwards), falling back to the raw peer address only if that
header is absent — standard practice on any platform-as-a-service, not
HF-specific. Verified locally before redeploying: a consistent
`X-Forwarded-For` value across 5 requests correctly rate-limited after 3;
different values per request (simulating the observed bug) correctly let all
5 through — exactly reproducing, then fixing, the live failure mode. Fix
committed (`3981e86`), uploaded to the Space; redeploy verification was
in progress (rebuild triggered, re-running the live 65-request test to confirm
429s now appear) when this session was compacted — **this is the one
unfinished thread**, see Session-end state below.

### Real discipline notes from this segment

- The user explicitly pushed back twice ("check it...there is error" and
  "check again...dont hallucinate") when a status claim wasn't yet backed by
  fresh, direct evidence — both times the correct response was to re-verify
  from scratch via the platform's actual API/logs rather than defend the
  earlier claim, which is exactly how bugs #2 and #3 were caught instead of
  being silently missed.
- A screenshot showing the HF Space dashboard's log-viewer panel stuck on
  "Starting..." / "Error: Failed to fetch" was correctly diagnosed as a
  browser-side widget failure on that one HF dashboard page, NOT the actual
  container state — confirmed by cross-checking the Space's REST API
  (`stage: RUNNING`) and the app's own `/health` endpoint (`200`) directly,
  two independent sources agreeing, neither of which routes through that
  dashboard widget at all.

## Session-end state

**Fully shipped and verified**: Keystroke Biometric Auth-Risk Demo (`f4686c1`),
YARA File Scanner (backend `b71859b`, frontend `1db26a9`), SAST-merge into
Malicious Package Scanner (`288a519`).

**App Safeguard Plan — mostly shipped, one verification thread open**:
- Backend committed and deployed: `c0ab0a2` (the full `security/` module +
  wiring + CI/Dependabot), `ed01afc` (Dockerfile fix for the missing
  `security/` COPY line), `3981e86` (rate-limiter IP-keying fix, uploaded to
  the Space, rebuild triggered but not yet confirmed RUNNING at session end).
- Frontend (`next.config.ts` headers + CI/Dependabot for ml-portfolio) was
  built and locally verified (headers present live, zero new console errors
  across spot-checked pages including a camera-using tool) but **not yet
  committed/pushed** — was holding for the backend rate-limit fix to fully
  land first.
- **Next step on resume**: confirm the Space rebuild from `3981e86` reached
  `RUNNING`, re-run the 65-request live test against `/health` (or a
  non-GET-cacheable route) and confirm 429s now appear after the limit,
  then commit+push the ml-portfolio frontend changes, then update
  `project_pending_master_list.md` with final commit hashes and the real
  verification numbers for the whole safeguard pass.
