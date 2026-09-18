# Part 292 — Two more security tools, and the registrations I forgot

Continues [Part 291](Session_2026-09-18_ThreeToolsAndWhatVerifyingCaught_Part291.md).

2026-09-19. Two cybersecurity tools shipped and live-verified (Exploit /
Attack-Payload Detector, Network Intrusion Classifier), then the user caught
that I'd shipped **five** tools this week missing side-registrations — blank
card thumbnails, then wrong breadcrumbs — and told me plainly that polished
apologies don't help. The through-line: **finishing the code is not finishing
the tool**, and honesty means fixing the whole class and reporting flatly.

---

## 0. The usage-limit question

The user's Account modal showed "Session (5hr) 100% · Resets in 0m" while a
banner said "resets 8:50pm". Not a conflict: **same limit, two displays** — a
rounded countdown ("0m" = imminent) vs the absolute clock time. Also flagged the
separate weekly caps (general + a distinct Opus cap; rolling 7-day window, not a
calendar reset), and that this is Anthropic-subscription behaviour I can only
reason about generally, not from the codebase.

---

## 1. Exploit / Attack-Payload Detector — client-side signature WAF

`/tools/exploit-payload-detector`, client-side, zero cost. 33 signatures over
**12 attack classes** (SQLi, XSS, command injection, path traversal, SSRF, SSTI,
Log4Shell/JNDI, NoSQL, XXE, LDAP, CRLF, unsafe deserialization). The point of
difference: a **deobfuscation pass** — each line is URL-, HTML-entity- and
Base64-decoded (incl. double-encoding) before matching, and a hit found only
after decoding is chip-tagged "Obfuscated · <how>". Honest framing: it's a
signature detector (ModSecurity CRS / Snort idea), evadable and can
false-positive; a finding ≠ a successful exploit.

Verified: 13/13 sample payloads caught, **10/10 benign inputs clean** (normal
SQL, `&&` git, single `../`, `--` in prose), live browser run confirmed. Caught
a real gap mid-build (`admin'--` auth-bypass unmatched) and fixed the SQLi rules
before shipping. Commit `4ecea04`.

**Side effect:** `security.ts` was already 450 lines (over the 400 gate). Split
it into `security.ts` (core, 238) + `securityMore.ts` (250), concatenated so
render order and the default export are unchanged. Confirmed the handbook /
thumbnail scripts glob every `*.ts` in the dir, so a split is safe.

---

## 2. Network Intrusion Classifier — real NSL-KDD, honest scorecard

`/tools/intrusion-detection`, live-engine. A real scikit-learn RandomForest
classifies **NSL-KDD** connections into normal / DoS / Probe / R2L / U2R.

Mirrors the Log Anomaly Detector's honesty pattern: **the caller owns the
labelled data, the backend does the ML.** Offline prep (`scratchpad/nsl/prep.py`)
downloads NSL-KDD, ordinal-encodes the 3 categoricals, maps fine labels to the 5
standard classes, and writes a compact 378 KB bundle (train + natural-proportion
held-out test) to `public/data/`. New backend endpoint
`routers/intrusion_detection.py` — dataset-agnostic `POST
/intrusion-detection/classify`, fits RF on the caller's train rows, predicts the
test rows, returns per-row class + confidence + feature importances. Frontend
shows a live reveal feed + confusion matrix + per-class precision/recall/F1 +
importances.

The numbers are the honest lesson: **74.8%** overall (matches the full-set RF
ceiling of 74.4%), DoS/Probe strong (F1 0.84/0.78), and **R2L recall stuck at
0.15** — the famous NSL-KDD hard problem (R2L looks like normal logins). The
scorecard shows that plainly instead of averaging it away.

Deployed: backend `26c4c2f` + HF upload (both `.py`) + **verified live** (raw
curl to the Space returned HTTP 200 with a valid response — new code serving,
not just RUNNING). Frontend `5ea1812`.

---

## 3. The registrations I forgot (twice)

The user screenshotted the new cards and asked why they had **no thumbnails**,
then — after that fix — screenshotted the tool pages and asked why the
breadcrumb showed only "Home" instead of "Home > Security & Trust". Both hit the
**same five tools** (secret-scanner, jwt-analyzer, anomaly-detection,
exploit-payload-detector, intrusion-detection), the recent ones.

Root cause: adding a card to `capabilities/*.ts` is **not** the whole job. A new
`/tools/*` tool has separate hand-maintained registrations:
1. `public/thumbs/<id>.webp` — missing ⇒ **blank white card**. Fixed via
   `scripts/thumbnails.py add` (Pexels photo + treatment). Commit `3b5f264`.
2. `AREA_OF` in `src/lib/toolNav.ts` — missing ⇒ **no area breadcrumb**. Commit
   `63d3434`.

After the second catch I stopped guessing and **grepped every file that lists a
sibling tool id** to find the whole class: only those two were real; `demos/*`
(handbook-only, ~37/58 tools) and `securityLogExclusions` (password-type only)
correctly don't include these. Saved as
[[feedback_new_tool_needs_thumbnail]] (now a 3-step new-tool checklist).

**The tone note, verbatim:** *"when you say... 'You were right to call that
out'... do you think it will placate my frustration? polished way of english
will not work on users."* Lesson: fix the class up front, report flatly, don't
dress a miss in apology.

---

## 4. QA plan — root-cause grouping, and two honest audits

Updated [docs/QA_AUTOMATION_AND_LOGGING_PLAN.md] (commit `0c54d52`):

- **Phase 5 — root-cause failure grouping + bulk fix** (a real testRigor
  feature): cluster failures by a deterministic signature (locator / step /
  error kind / URL), show "1 issue, affecting N tests" instead of N reds, an LLM
  labels the cause, then fix all in one click (shared locator / find-replace,
  re-run to confirm) or one-by-one. **Safeguard:** each group also offers "this
  looks like a real bug" so a one-click *test* edit can't silently mask a real
  app regression — "fix" edits the test, not the app.
- **testRigor feasibility audit** — mapped their whole public feature set to our
  free / Playwright-TS / own-site stack in three buckets (feasible / partial /
  not-feasible). Core value is reproducible free for our own site; platform
  breadth (mobile/desktop/mainframe), paid device-farm scale, and comms /
  compliance are not.
- **Katalon** added two feasible ideas: record-and-playback via Playwright
  `codegen`, and importing API tests from OpenAPI / Postman.

**Two honesty moments the user pushed on:**
- Asked if I'd actually gone through testrigor.com. I hadn't — earlier I'd used
  web-search snippets, not the app. Said so, then verified the specific claims
  from the public pages before writing them.
- `app.testrigor.com` is **login-gated** and returned nothing to a fetch; I
  wrote that caveat into the doc rather than imply hands-on inspection. (Katalon's
  public landing page fetched fine.)

---

## Commits

| Repo | Commit | What |
|---|---|---|
| ml-portfolio | `4ecea04` | Exploit / Attack-Payload Detector + split security.ts |
| ML-Unified | `26c4c2f` | intrusion-detection endpoint (RandomForest); HF-uploaded |
| ml-portfolio | `5ea1812` | Network Intrusion Classifier tool + NSL-KDD bundle |
| ml-portfolio | `3b5f264` | thumbnails for the 5 recent security tools |
| ml-portfolio | `63d3434` | breadcrumb (AREA_OF) for the 5 recent tools |
| ML-Unified | `0c54d52` | QA plan: root-cause grouping + testRigor/Katalon audit |

---

## Lessons

- **Finishing the code is not finishing the tool.** A new tool needs three
  hand-maintained registrations (card, thumbnail, breadcrumb); I shipped five
  tools missing two of them. Grep a sibling id for the full set.
- **Fix the class, not the instance.** When a miss is caught, find every place
  it occurs before reporting, so there isn't a third round.
- **Plain over polished.** "Polished English will not work on users" — report a
  mistake flatly and fix it; don't apologise in flourish.
- **Verify against reality, again.** Stub-server + Playwright proved the
  intrusion tool end-to-end before deploy; a raw HTTP 200 from the Space proved
  the new code was actually serving (a Python probe's SSL error was the probe's
  fault, not the endpoint's — use curl for TLS).
- **Don't claim inspection you didn't do.** "Did you go through the site?" — the
  honest answer was no; say it, then verify from sources you *can* reach, and
  record what was login-gated.
- **Honest ML beats a highlight reel.** NSL-KDD R2L recall 0.15 is shown, not
  hidden — the benchmark's real lesson.
