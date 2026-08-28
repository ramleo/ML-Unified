# Session 2026-08-28 (Part 260) — Cybersecurity tools sprint: 6 new tools shipped

Continues directly from Part 259, which ended with the deferred-items
grouping (#11/#12/#21 + not-buildable cybersecurity items consolidated
into one section of `project_pending_master_list.md`) and the initial
cybersecurity research shortlist. This session built and shipped the
first six items from that research: Password Strength & Breach Checker,
DNS Tunneling Detector, SIEM Alert Triage Agent, Phishing Email Body
Classifier, TLS/Security-Headers Scanner, and Malicious Package Scanner —
plus a seventh item (Attack-Surface Scanner) picked up from a deeper
follow-on triage of a user-pasted idea list partway through the session.

Every item followed the same discipline: EnterPlanMode with a written
plan before any code, real-technique research/verification before
committing to an approach, unit-verification of pure logic before any UI
was touched, and live Playwright verification against the actual deployed
backend (not just local mocks) before calling anything done.

## 1. Password Strength & Breach Checker

New standalone, fully client-side tool `/tools/password-audit` (zero
backend, zero API key). User explicitly chose real `zxcvbn-ts` (Dropbox's
pattern-matching algorithm) over a hand-rolled entropy heuristic via
AskUserQuestion — character-class entropy is a known-misleading metric
(`Password1!` scores deceptively high despite being a common weak
pattern), and NIST SP 800-63B specifically favors the pattern-matching
approach. Breach lookup uses Have I Been Pwned's Pwned Passwords
k-anonymity range API — confirmed via research it needs no API key and is
purpose-built for direct browser calls, a deliberate documented deviation
from this codebase's only prior precedent (QR Phishing Detector proxies
its reputation checks through the backend specifically because those need
a secret key). Password is SHA-1 hashed locally (Web Crypto — HIBP's own
API requirement, not a general recommendation) and only a 5-character hash
prefix ever leaves the browser; nothing is persisted (no scan history,
unlike QR Phishing Detector, since a password is sensitive by nature).

Real bug caught via live Playwright verification: a JSX line-break
whitespace collapse (`password{s} —\nthis password`) rendered as
"passwords— this" with a missing space — fixed with an explicit `{" "}`
token. Verified live: `password123` correctly scored "Very weak" and
returned `pwned: true` with a real ~2.27M-hit count; a random 20-char
password scored "Very strong"/"centuries" and returned `pwned: false`;
network tab confirmed only the 5-character prefix (`CBFDA`) was ever sent.
ml-portfolio commit `127abea`.

## 2. DNS Tunneling / Exfiltration Detector

New standalone, fully client-side tool `/tools/dns-tunneling-detector`.
Real, published heuristics (MITRE ATT&CK T1071.004 detection literature,
CyberDefenders, Splunk/SNORT-based frameworks): subdomain length (>50
chars), Shannon entropy (>4.0 bits/char), and query volume/repetition per
parent domain. Deliberately flags a parent domain only when entropy AND
at least one other signal cross threshold together — never a single
heuristic alone, since length or entropy in isolation both false-positive
on ordinary long CDN-style subdomains (verified directly: a synthetic
`cloudfront.net` log with 10 unique 48-char subdomains correctly stayed
unflagged since its entropy sat below threshold). Parent-domain extraction
uses the same "small curated multi-part-TLD list, disclosed as not
exhaustive" pattern as the QR Phishing Detector's typosquat list.

Unit-verified against 3 synthetic cases via a `tsx` script before any UI
was touched (clean log → 0 flags; injected tunneling burst → correctly
flagged with real matched-signal numbers; legitimate long CDN subdomain →
correctly NOT flagged), then re-verified identically live via Playwright.
ml-portfolio commit `6728727`.

## 3. SIEM Alert Triage Agent

New standalone tool `/tools/siem-alert-triage` — the highest-reuse pick
on the shortlist, chosen specifically because it could lean on the exact
fixed-server-key Mistral LLM-judge pattern already shipped twice
(`ai_code_detector.py`, `prompt_injection_check.py`). Two-layer design
mirroring how AI Code Detector splits stylometry (client) from the LLM
opinion (backend, needs the secret key): (1) `alertGrouping.ts` — pure
client-side dedup, normalizing each pasted alert line into a template
(IPv4→`<IP>`, digit runs→`#`) and grouping near-identical lines, capped
at the top 20 groups by count before ever reaching the backend; (2) new
backend router `services/ml-api/routers/siem_triage.py` receives only the
already-grouped summary and returns a priority (critical/high/medium/low/
noise) + reasoning + suggested action per group — the system prompt
explicitly forbids phrasing suggestions as actions already taken
("investigate the source IP", never "blocked the IP"), since this project
has no real firewall/EDR/AD integration to actually act on anything.

Real bug caught and fixed during unit verification, before it ever
reached the backend: `\b\d+\b`'s word-boundary requirement doesn't match
a digit run embedded in a word (`admin0`, `admin1`), so 50 varying-user
brute-force-style lines produced 50 separate one-line groups instead of
one group of 50 — fixed by dropping the boundary requirement (safe since
IPs are stripped first). Backend deployed and verified live via direct
curl against the deployed HF Space BEFORE any frontend work touched it: a
real brute-force cluster scored "high" with a correct "investigate the
source IPs" suggestion, a new-admin-account alert scored "critical" —
both genuinely generated by Mistral, not scripted. Frontend then verified
live end-to-end via Playwright against that same deployed backend
(temporarily pointing local `.env.local` at the HF Space, then restored):
the sample log (13 lines → 6 real groups) rendered every priority tier
correctly sorted with real grouped data and real judge output, zero new
console errors. Backend `services/ml-api` commit `a1e0265`; frontend
`ml-portfolio` commit `f1f17c0`.

## 4. Phishing Email Body Classifier

New standalone, fully client-side tool `/tools/phishing-email-classifier`
— the genuinely novel pick: the three prior phishing/security tools all
inspect URL/DNS/header structure, none read the email's actual body text.
Found and verified a real, ungated dataset (confirmed `{"gated": false}`
via direct HF API check, not just a search result) —
`zefang-liu/phishing-email-dataset`, combining the real Nazario phishing
corpus with real Enron ham — downloaded and confirmed 18,650 real emails
(11,322 safe / 7,328 phishing) before committing to it.

Technique: Multinomial Naive Bayes over a chi-squared-selected ~3,000-word
bounded vocabulary — chosen over a heavier transformer specifically so it
ships as a small (154KB) static JSON artifact scored via plain-TS
bag-of-words math (same "static artifact + hand-rolled scoring" pattern
as ASL Fingerspelling's k-NN prototypes), and because Naive Bayes is
naturally interpretable (real top-contributing-words shown as evidence).
One-time local training (scikit-learn) measured a real **90.95% accuracy
on a genuine 2,795-email held-out split (2542/2795)** — reported honestly,
not tuned toward a target. Two independent signals shown side by side:
the trained model's verdict + its actual top contributing words, plus a
small transparent rule-based flag list (urgency phrasing, generic
greetings) — never fused into one black-box score.

Exact-reproduction discipline followed before any UI was touched: the TS
tokenizer had to precisely mirror Python's `string.punctuation`-strip-
then-regex-match behavior — a subtle mismatch was caught and fixed
(naively stripping digits in TS could wrongly merge two words across a
removed digit run, e.g. `"word1word2"`, where Python's approach leaves
digits as natural token boundaries) — verified against 20 real held-out
examples with zero token or prediction mismatches, including exactly
reproducing one of the model's genuine misclassifications. Verified live
via Playwright: the real held-out phishing example (a classic Nigerian-
prince 419 scam) scored 100% phishing with real contributing words (fund,
deposited, nigeria, security); the real held-out safe example (an Enron
business email) scored 0% with real business-language words (role, eric,
mark, contribute). ml-portfolio commit `2122861`.

## 5. TLS / Security-Headers Scanner

New standalone tool `/tools/tls-security-headers-scanner` — a real
Mozilla-Observatory-/SSL-Labs-style live check, following
`email_auth_check.py`'s exact "live network check, honest qualitative
verdict + warnings list" shape (read directly before writing new code).
New backend `routers/tls_headers_check.py` does a real TLS handshake
(stdlib `ssl`/`socket` only, zero new ML dependency) to check certificate
chain verification, expiry, and deprecated-protocol status, plus a live
`httpx` GET checking the 6 standard Mozilla Observatory security headers.

Two real issues caught and fixed before this was considered done: (1) a
genuine SSRF gap identified proactively — unlike every prior live-network
tool here (DNS TXT lookups only), this one opens a real socket to a
user-supplied host, so a hostname-resolution + `ipaddress` private/
loopback/link-local/reserved check was added, refusing to connect to
internal addresses (verified live: `127.0.0.1` and `169.254.169.254` both
correctly refused, `github.com` correctly allowed); (2) the OS default CA
store proved unreliable for real verification — a validly-signed GitHub
certificate initially failed with "unable to get local issuer
certificate," a known macOS Python quirk, not a real finding — fixed by
explicitly wiring `certifi`'s CA bundle into
`ssl.create_default_context(cafile=...)`, plus adding `certifi` explicitly
to `requirements-base.txt`. When a certificate fails verification,
subject/issuer/expiry are deliberately left unset in the response (never
shown for an unvalidated chain) — the verification failure itself is the
finding.

Verified live end-to-end: real HTTP calls to the deployed HF Space
matched local results exactly for `github.com` (TLS 1.3, verified,
expires in 33 days, 5/6 headers present, correctly missing only
Permissions-Policy) and `expired.badssl.com` (correctly caught the real
expired-certificate error and returned "critical issues"); Playwright on
the local dev site reproduced both the successful scan and the
SSRF-refusal path through the actual UI. Backend `services/ml-api`
commit `d6a0746`; frontend `ml-portfolio` commit `3b0932a`.

### Deeper triage of a user-pasted cybersecurity idea list

Partway through the session the user pasted a large external cybersecurity
project list (from another AI conversation, spanning Application
Security, Endpoint/OS Security, Identity/Access/Crypto, Cloud/
Infrastructure, and SOC/Orchestration domains). Rather than treating it at
face value, every item was triaged against this specific project's real
constraints — hosted, stateless, CPU-only HF Space, no persistent local
agent, no live cloud credentials, never executes untrusted files — and
sorted into three groups: genuinely buildable now (Keystroke Biometric
Auth-Risk Demo, DNS Tunneling Detector, SIEM Alert Triage Agent, Phishing
Email Body Classifier, AI-Powered SAST Scanner), needs a scope change to
fit a hosted demo (Malware PE Header Classifier, Crypto/TLS Downgrade
Detector, Supply Chain Dependency Predictor, Malicious PR Detector, IAM
Least-Privilege Optimizer, Honeytoken Deployer, Network IDS, Automated
Incident-Response Playbook), and not buildable in this architecture at all
(Ransomware Canary, Process Injection Detector, UEBA Engine, Adaptive
Risk-Based Auth Engine — each needs a persistent local agent or live
enterprise telemetry this hosted setup structurally can't have). The
user then asked to group the not-buildable items together with #11/#12/
#21 (the CV-backlog items ruled out the prior session) into one explicit
"Deferred" section of `project_pending_master_list.md` — done immediately,
and also appended to Part 259's log as its own retroactive section.

## 6. Malicious Package Scanner (npm/PyPI)

New standalone, fully client-side tool `/tools/malicious-package-scanner`
— the sixth and final pick of the original shortlist, closing it
entirely. Real technique confirmed via research: Datadog's GuardDog
pattern-matches common attacker techniques rather than comparing against
known-malware signatures, which is what lets this style of check catch
never-before-seen malicious packages. Two independent modes: (1) manifest
scan (`package.json`/`requirements.txt`) — flags npm lifecycle
install-script hooks (`preinstall`/`install`/`postinstall`, a real
repeatedly-abused supply-chain vector) with the actual script content
shown, plus dependency-name typosquats via a hand-rolled Levenshtein-
distance function against a curated ~150-name list of well-known real
npm/PyPI packages; (2) source-code scan (JS/TS/Python) — flags suspicious
dynamic-execution calls (`eval`, `new Function`, `child_process.exec`,
Python `exec`/`subprocess`/`os.system`), obfuscated high-entropy string
literals (reusing the same Shannon-entropy technique already built for
the DNS Tunneling Detector), and embedded URLs shown as evidence to
review, not scored.

Unit-verified against 6 synthetic cases before any UI was touched (clean
`package.json`/`requirements.txt` → zero flags; a postinstall-hook +
typosquatted-dependency `package.json` → both correctly flagged; a
typosquatted `requirements.txt` → correctly flagged; clean JS source →
zero flags; an `eval(atob(...))`-plus-embedded-C2-URL JS snippet → all 3
signals correctly flagged), then re-verified identically live via
Playwright including the mode-toggle UI. ml-portfolio commit `fa64840`.

**This closed the original 6-item cybersecurity shortlist entirely**:
Password Checker, DNS Tunneling Detector, SIEM Alert Triage Agent,
Phishing Email Body Classifier, TLS/Security-Headers Scanner, and this
one.

## 7. Attack-Surface / Exposed-Path Scanner

Picked up next from the deeper triage's "buildable" list. New standalone
tool `/tools/attack-surface-scanner` — real, entirely passive recon (no
active exploitation), same live-network-check category as the Email Auth
Checker and the just-shipped TLS/Security-Headers Scanner. New backend
`routers/attack_surface_check.py` runs four checks: (1) exposed sensitive
paths (`.git/HEAD`, `.git/config`, `.env`, `.DS_Store`, `.svn/entries`,
`backup.zip`, `.aws/credentials`) — only flagged on a real 200 **and**
content that actually matches the expected file (real ZIP/DS_Store magic
bytes, `.git/HEAD`'s `ref: refs/` pattern), avoiding false positives from
sites that 200 every path with a custom error page; (2) Apache/nginx
directory-listing detection; (3) passive CMS fingerprinting via the
standard `<meta name="generator">` tag (verified live: correctly detected
`WordPress 7.2-alpha-63368` on wordpress.org, correctly returned nothing
for example.com); (4) a short common-port TCP-connect check — open/closed
only, no banner grab.

A real architectural decision made proactively: extracted the SSRF guard
out of `tls_headers_check.py` into a new shared `routers/security_shared.py`
module, since this tool has the identical risk profile (opens real
sockets to a user-supplied host) — one implementation to review/fix
instead of two duplicated copies of security-critical logic. Re-verified
`tls_headers_check.py` behaves identically after the extraction (same
`github.com`/`127.0.0.1` checks as when it first shipped) before adding
any new code on top. A real performance issue was caught and fixed during
local verification, not assumed away: the sequential port-check loop
measured **~18 seconds** against a real host (some ports were
firewall-dropped rather than actively refused, each hitting its full 2s
timeout) — fixed by parallelizing with a `ThreadPoolExecutor`, cutting it
to **~6 seconds** with identical results.

Verified live end-to-end: real HTTP calls to the deployed HF Space
matched local results exactly for `github.com` (correctly clean on
paths/listing/CMS, correctly showing port 22/SSH open — accurate, since
GitHub genuinely runs SSH for git operations, not a false positive) and
for the SSRF guard (`127.0.0.1` correctly refused); Playwright on the
local dev site reproduced both the successful scan and the refusal path
through the actual UI. Backend `services/ml-api` commit `bd830a0`;
frontend `ml-portfolio` commit `f0b5dad`.

## Session-end state

Seven items shipped this session, all real-technique tools with either a
genuine measured accuracy number (Phishing Email Body Classifier's
90.95%) or an explicit disclosed limitation where perfect accuracy/
certainty wasn't achievable. Every backend change followed the mandatory
batch-deploy discipline: commit/push, HF Space upload, wait for rebuild,
verify the new code is actually serving (not just `stage=RUNNING`) via a
direct API call, before any frontend work touched it. All commit hashes
recorded in `project_pending_master_list.md`.

Remaining candidates from the deeper triage, not yet built: YARA File
Scanner, Keystroke Biometric Auth-Risk Demo, AI-Powered SAST Scanner
(overlaps with the Malicious Package Scanner's source-code-scan half —
merge rather than duplicate if picked up later).
