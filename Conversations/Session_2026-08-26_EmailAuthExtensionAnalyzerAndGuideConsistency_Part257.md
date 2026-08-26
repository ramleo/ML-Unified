# Session 2026-08-26 — Part 257: Email Auth Checker, Extension Permission Analyzer, User Guide + AI Chat Consistency

Continuation of the same day as Part 256 (new conversation after context
compaction). Part 256 ended with a combined CV+cybersecurity pending list
and an open invitation to pick the next item. This session picked up there,
shipped the two remaining low-effort cybersecurity items (#54, #56), then
did a consistency pass across all Security & Trust tools.

## 1. Email Header Authentication Checker (pending-list #54)

**Scope decision (headers-only, no body-based DKIM crypto verification):**
Researched the real technique first. True DKIM signature verification
needs the full raw message body to recompute the body hash — most users
won't have or paste that correctly. Instead of a fragile "paste the whole
.eml" flow, built two honest, real things:
1. Parses the `Authentication-Results` header most mail providers already
   stamp at delivery (real spf=/dkim=/dmarc= verdicts) — relayed, not
   re-verified.
2. Independent, live DNS TXT lookups against the sending domain's real SPF
   record, `_dmarc.<domain>` record, and DKIM selector key — reporting
   policy strictness (SPF `-all`/`~all`/`+all`, DMARC `p=none/quarantine/
   reject`) plus a From:-domain alignment check.

**Backend**: new `services/ml-api/routers/email_auth_check.py` (~240 lines),
standalone `APIRouter(prefix="/email-auth")` following the vision/document
no-`/rag`-prefix pattern (not the `mm_*` pattern). New dependency:
`dnspython`. Explored first via an Explore agent to confirm the pattern
(`mm_qr_phishing_reputation.py`'s sync-httpx/timeout/TTL-cache/fail-to-None
contract) and confirm `dnspython`/`dkimpy`/`cryptography` weren't yet
project dependencies.

**Real bug found and fixed during local verification**: this machine's
default DNS resolver timed out on a plain `google.com` TXT lookup (network
flakiness, not a code bug) — added a public-DNS (8.8.8.8/1.1.1.1) fallback,
but only on genuine network failures, not on authoritative
NXDOMAIN/NoAnswer (to avoid doubling latency on the common "no record"
case, which is the majority path).

**Verification**: fully testable locally since `dnspython` has no GPU/
model-weight dependency — ran `check_spf_record`/`check_dmarc_record`/
`check_dkim_dns` against real public domains (confirmed GitHub's actual
live SPF `~all` + DMARC `p=quarantine` records) before ever deploying.
Synthetic fixtures verified a passing-aligned case and a misaligned-spoof
case. Deployed to HF Space (`app.py` + `requirements-base.txt` +
`email_auth_check.py` uploaded via `api.upload_file()`), polled until
`RUNNING`, confirmed live via `curl` against the real endpoint (returned
GitHub's actual DNS records, not a stale proxy). Frontend
`/tools/email-auth-checker` (paste-headers textarea UI, "Load sample
headers" button, badge/Section/Row components) built, eslint/tsc/build
clean, Playwright-verified on the live Vercel site for both the
sample-headers pass case ("Likely legitimate") and a hand-typed
weak-signal case ("Weak authentication," not overclaimed as "phishing").
Zero console errors either path.

Backend commit `e1530f4`, frontend commit `a5e3bd4`. Pending-list #54
marked done.

## 2. Browser Extension Permission Risk Analyzer (pending-list #56)

Entirely **client-side only** — pure JSON parsing + a static documented
Chrome/Edge extension permission-risk taxonomy, no backend, no network
calls, no ML. New file `permissionRisk.ts` (~200 lines): `PERMISSION_RISK`
table (debugger/nativeMessaging/webRequestBlocking/cookies/history/etc.,
each with a real risk level and plain-language why), broad-host-access
detection (`<all_urls>`/`*://*/*`/wildcard-TLD patterns), and a fixed list
of documented dangerous **combinations** (e.g. broad host access +
network interception + cookie access = session-hijack capability; broad
host access + content-script injection = arbitrary JS on any page).

**Real bug found and fixed during synthetic-data unit verification**
(before any UI was touched): `<all_urls>` inside a Manifest V2-style
`permissions` array wasn't detected as broad host access at all — the
candidate filter required a `"://"` substring that the literal string
`<all_urls>` doesn't contain. Fixed the filter, re-verified the exact MV2
combo case (`<all_urls>` + `webRequestBlocking` + `cookies` → correctly
flagged high-risk) afterward.

Verified via `npx tsx -e` against: a low-risk manifest (no combos, low
overall), the high-risk MV2 combo, `debugger` alone (high on its own, no
combo needed), MV3 `host_permissions` + `scripting` (broad-host +
injection combo), malformed JSON (clean error, no crash), and an empty
object (low risk, one warning). Frontend `/tools/extension-permission-
analyzer` (textarea paste UI, "Load sample manifest" button, risk badges,
combo callouts) built, eslint/tsc/build clean, Playwright-verified live on
Vercel for both the high-risk sample (correct "High risk" + combo
callout) and a hand-typed low-risk manifest (correctly drops to "Low
risk," proving the tool isn't just always alarming). Zero console errors.

ml-portfolio commit `a1b0572`. Pending-list #56 marked done. Both
low-effort cybersecurity items from the Part 256 research round are now
shipped.

## 3. "Add user guides to all Security & Trust tools"

User asked for User Guides (what it does / purpose / example / etc.) added
across the Security & Trust domain. Investigated first: 10 tools total in
that domain; 4 already had the pattern (`qr-phishing-detector`,
`adversarial-robustness-lab`, `face-cloak`, `style-cloak` — each a
`<Tool>UserGuideModal.tsx` + `userGuide.ts` pair, wired into `page.tsx` via
a header button). The other 6 — all built earlier this session or in Part
256 — had nothing: `captcha-hardening-lab`, `malware-image-triage`,
`face-deanonymization-demo`, `video-keystroke-inference`,
`extension-permission-analyzer`, `email-auth-checker`.

**Scope decision**: the existing 4 guides also feed `ToolsAIChat` (the
site's floating AI help-chat widget), but that widget was wired on only
21/33 tools sitewide, including none of these 6 — and the user asked
specifically for "user guides," not a chat assistant. Scoped this pass to
the guide modal only, explicitly noting the `ToolsAIChat` gap as an
out-of-scope, pre-existing pattern rather than silently also fixing it.

Wrote each guide directly from that tool's own actual runner/hook code and
this session's own real verification numbers — not generic filler. For
example: the email-auth-checker guide's worked example cites the real
GitHub SPF/DMARC records fetched live during that tool's own verification;
the face-deanonymization-demo guide cites the actual measured 99%→-77%
similarity swing found when that tool was built and tested. Each guide
followed a consistent structure: What this tool does, Purpose, How to use
it, A worked example, Reading the result, Notes & limits. Replicated the
exact modal shell/markdown-styling from `QrPhishingUserGuideModal.tsx`
(only accent, title, and guide-constant changed per tool) and added the
"User Guide" header button to each `page.tsx`.

Verified: eslint/tsc/`next build` clean across all 6 tools (46 total
routes built). Playwright-verified live on Vercel for two representative
tools (`email-auth-checker`, `extension-permission-analyzer`) — modal
opens with full real content, closes via both the × button and Escape,
zero console errors.

ml-portfolio commit `3b44d75` (18 files: 6× `userGuide.ts` + 6×
`<Tool>UserGuideModal.tsx` + 6× `page.tsx` edits).

## 4. "Is there a reason ToolsAIChat isn't in Security & Trust tools?"

Answered directly (no action taken, as asked): not a deliberate
domain-based decision. The 4 older Security & Trust tools DO have it; the
6 missing it are exactly the ones built this session/Part 256. The gap
isn't Security-&-Trust-specific either — other non-security tools built
around the same time (`movement-form-comparison`, `pose-vj-visuals`,
`pipeline-builder`/`pipeline-cinema`/`rag-analytics`) are missing it too.
Sitewide it's 21/33 tools with it. Conclusion: chronological gap in the
newer-tool build checklist, not an intentional exclusion.

## 5. "Add ToolsAIChat to them, it should be consistent"

Wired `ToolsAIChat` into all 6 of the same tools from step 3, reusing each
tool's just-written `userGuide.ts` `GUIDE`/`SUGGESTIONS` exports as the
chat's scoped knowledge source (`context={{ accent, tool, summary, guide,
suggestions }}`, matching the exact `qr-phishing-detector`/`face-cloak`
wiring pattern) — no content duplication, the chat answers from the same
real, already-verified guide text. Added one new `TOOL_SUMMARY` constant
per tool page.

Verified: eslint/tsc/`next build` clean. Playwright-verified live on
Vercel: the floating "AI Assistant" button opens correctly scoped to the
tool name, shows the exact suggestion chips from that tool's `userGuide.ts`
(confirmed on `email-auth-checker`), and the button is present and
correctly rendered on a second tool (`extension-permission-analyzer`) too.
Zero console errors. One transient hiccup during verification: an
automated polling `curl` loop briefly tripped Vercel's bot-protection
"Security Checkpoint" page on the live site — resolved itself after a
short pause, not a real deploy issue.

ml-portfolio commit `ecfa03b` (6 `page.tsx` edits).

## Pending-list status after this session

- `#54` (Email header authentication checker) — **Done**, see
  `project_pending_master_list.md`.
- `#56` (Browser extension permission risk analyzer) — **Done**, see
  `project_pending_master_list.md`.
- All 10 Security & Trust tools are now consistent: User Guide modal + AI
  Assistant chat widget on every one.
- Remaining unclaimed pending items are Medium/High effort: `#53` (LLM
  prompt injection detection playground — recommended next, not yet
  feasibility-researched), `#55` (AI-generated code detector — flagged
  with an overclaiming-risk caveat), and the Computer Vision backlog
  (`#32` crime scene reconstruction/SfM, `#33` gait analysis, `#45`
  Gaussian Splat scanner, `#46` SAM3 rotoscope, `#49` wildlife
  re-identification, `#52` astrophotography anomaly CV).
- Session ended here — no build started on any of those; next session
  should confirm with the user which item to pursue, or whether to extend
  the User Guide + ToolsAIChat consistency pass to other domains
  (Computer Vision, NLP, etc.) sitewide.
