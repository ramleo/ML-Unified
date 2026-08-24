# Session 2026-08-19/20 — Plant Growth Exports/Guide, New QR Phishing Tool (Part 242)

Direct continuation of Part 241 after a context compaction. Opened by resuming the "save the
conversation" task that was in progress at compaction time, then the user asked "what next?" and
picked features one at a time from the standing pending list, closing out Plant Growth Quantification
entirely before moving to a brand-new tool.

## 1. Plant Growth: CSV export, growth-rate projection, time-lapse GIF export

The last three items on the plant-growth free/local feature brainstorm, each proposed individually,
confirmed, built, live-Playwright-verified, and committed/pushed one at a time (not batched) — user
explicitly picked CSV export first, then growth-rate projection, then GIF export.

- **CSV export** (`PlantGrowthCsv.tsx`): client-side Blob download for growth/compare/group results —
  label, area_fraction, growth_pct/relative_pct, leaf_pixel_count, greenness_index, leaf_count,
  low_confidence, +area_cm2 when calibrated. Verified live: downloaded file's numbers matched the
  actual measured `leaf_pixel_count` values exactly (5145/15597 → 203.1% growth).
- **Growth-rate projection** (`PlantGrowthProjection.tsx`): linear extrapolation —
  `projected = last + (last/(n-1)) × stepsAhead` — user-editable steps-ahead input, rendered as a
  dashed point+label on `GrowthChart` (new optional `projectedPct` prop; chart layout unchanged when
  absent, so existing views weren't affected). Explicitly labeled an assumption-based extrapolation,
  not a forecast. Verified live with a real 3-photo run at both steps=1 (+304.7%, matching the formula
  exactly against real measured 203.1% growth) and steps=3 (+507.8%), including a live input-change
  recalculation.
- **Time-lapse GIF export** (`PlantGrowthGif.tsx`): new dependency `gifenc` (MIT, zero deps, no
  worker) — letterboxes each photo onto a fixed 480×480 canvas (contain-fit, centered, dark
  background) so mixed aspect ratios don't distort, per-frame 256-color palette, 700ms/frame. Ships
  its own `src/types/gifenc.d.ts` since the package has no types. Works directly off the pending
  upload sequence — no measurement run required — and wired into each group's proposed photo order in
  the unordered-batch review screen. Verified live: real downloaded GIF confirmed via PIL as valid
  GIF89a, 3 frames, 480×480, 700ms/frame duration, in both growth mode and group mode.

All three tested by temporarily pointing local `.env.local` at the deployed HF Space (no local backend
running at the time), then restoring it and cleaning up scratch files afterward each round.

Commits: ml-portfolio `aafadf6` (CSV) → `9f11054` (projection) → `781d85c` (GIF). No backend changes,
so no HF upload needed for any of the three.

## 2. Plant Growth: User Guide

User asked "where can I find features added today?", which surfaced that this tool — unlike several
other complex tools in the app (multimodal-rag, document-intelligence, text-to-sql) — had no User
Guide modal. Followed the existing pattern exactly: `userGuide.ts` (markdown, covers both modes, every
measurement/export feature, and known limitations) + `PlantGrowthUserGuideModal.tsx` (copied from
`DocUserGuideModal.tsx`'s shape) + a header "User Guide" button wired into `page.tsx`, also fed into
`ToolsAIChat`'s `guide` prop so the floating AI Assistant answers from it in guide-only mode. Verified
live: full guide renders with correct markdown formatting (headings, bold, lists, inline code), opens
and closes cleanly.

Commit: ml-portfolio `174d6f6`.

## 3. A real UI confusion, resolved without a code change

User uploaded a single image (a multi-plant illustration) into "Unordered batch — figure it out" mode
and reported "nothing happened" after clicking "Group 1 photo". This was the UI working exactly as
designed — the button is disabled below `GROUP_MIN_PHOTOS` (2), and the on-screen text already said
"Add at least 2 photos" — but the user hadn't connected that message to the disabled button. Explained
the actual distinction (unordered-batch mode clusters across separate photo *files*; a single photo
with multiple plants belongs in the other mode's auto-detect/compare path instead) rather than
changing any code, since nothing was actually broken.

## 4. Backlog pick: QR Phishing Detector (new standalone tool)

Asked to pick something from `project_pending_master_list.md`'s broader backlog. Recommended item #43
("Malicious QR code / visual phishing detection") over the runner-up (#40, adversarial examples demo)
for being self-contained, genuinely useful, and not needing a live webcam or heavy new model. User
approved.

**Scope deliberately narrowed before building**: the original brainstormed idea had two halves — (a)
QR decode + URL structural-risk heuristics, and (b) screenshot-vs-known-brand-page perceptual-hash
comparison to catch visual impersonation. Only (a) was built. (b) was explicitly dropped: it needs a
maintained reference database of real brand-page screenshots that doesn't exist in this environment
and shouldn't be fabricated for real institutions (PayPal, banks, etc.) — a case of shipping the
well-defined, verifiable half of an idea rather than either skipping it entirely or faking the harder
half.

**Backend** (`routers/rag/mm_qr_phishing.py`, new): zero new dependencies —
`opencv-python-headless>=4.9.0` was already pinned; `cv2.QRCodeDetector().detectAndDecodeMulti()`
decodes with no `pyzbar`/`libzbar` needed. Scores each decoded URL against structural signals:
IP-literal host, punycode/homograph domain, `"@"` auth-trick URLs, known URL shorteners, suspicious
TLDs, plain HTTP, and typosquatting against a curated brand-domain list via Levenshtein edit distance
(root/eTLD+1 comparison so real brand subdomains never false-flag). Never fetches the decoded URL —
pure text analysis. Follows the Watermark tool's convention: never raises for "nothing found," returns
`{found: false, qr_codes: []}`. Verified against 8 hand-crafted synthetic cases (clean, IP-literal,
punycode, typosquat, shortener, legit-brand, suspicious-TLD, @-trick) before any live/UI test — every
one landed at the exact expected risk level and reason.

**Frontend** (`src/app/tools/qr-phishing-detector/`, new): followed the Face Liveness tool's simple
single-purpose shape (not plant-growth's heavier multi-mode shape), but kept the `userGuide.ts` +
modal + homepage-registration pattern going. Used a wide `max-w-6xl` container, not face-liveness's
narrow `max-w-3xl`, per the standing "don't cramp layout" rule. Registered in
`src/data/capabilities.ts`.

Commits: ML-Unified `972e50c` (backend, HF-uploaded + verified live same response); ml-portfolio
`ebdc88c` (initial tool).

## 5. Multi-file upload added same day, second round

User asked "can I upload all of them at once?" after testing with 4 separate QR images through a
single-file input. Rebuilt `useQrPhishingScan.ts` from a single-result hook into a batch hook
(`entries: ScanEntry[]`, each with its own `scanning`/`result`/`error` state), scanning all selected
files in parallel so each result card renders as soon as its own scan finishes rather than waiting for
the slowest file. `QrPhishingRunner.tsx` rebuilt to render one card per file with a filename+thumbnail
header. Verified live: 4 real QR photos selected in one file-chooser dialog, scanned in parallel, each
landed on its exactly-expected risk level.

Commit: ml-portfolio `77c0f99`.

## 6. Google Safe Browsing reputation check

User asked what "the link is never actually visited" meant, and separately whether an ML model would
make the tool more robust. Explained the distinction (structural text analysis vs. an actual page
fetch) and recommended AGAINST an ML classifier — a lexical phishing-URL model wouldn't meaningfully
beat tuned heuristics for this narrow task and adds training/maintenance burden — in favor of a
**Google Safe Browsing reputation lookup** instead: a hash-prefix check against Google's own
known-malicious-site database, which preserves "never visits the link" (it's a lookup, not a fetch)
while adding real detection power heuristics fundamentally can't reach (a site already known bad,
regardless of how clean its URL text looks).

**Real credential-setup detour**: the user's existing `GEMINI_API_KEY` turned out to be a Google
AI-Studio **service-account-bound key**, which Google Cloud explicitly restricts to only
Vertex/Gemini APIs — confirmed directly from a Cloud Console screenshot's own warning text, not
guessed. Walked the user through the correct fix: locate the underlying GCP project
(`gen-lang-client-0032162127`, found via the project-details dialog), enable the Safe Browsing API on
that project, then create a **separate**, ordinary (non-service-account-bound) API key restricted to
just Safe Browsing API — confirmed via a second screenshot that the new key's restriction UI correctly
offered Safe Browsing API as a selectable option, unlike the original key.

**Backend**: `_check_safe_browsing()` in `mm_qr_phishing.py` — a `threatMatches:find` POST against
`safebrowsing.googleapis.com`, reading a **separate** `SAFE_BROWSING_API_KEY` env var (never touches
`GEMINI_API_KEY`). Returns `None` (not `{}`) when the key is unset or the lookup fails for any reason,
so the caller can tell "checked, nothing found" apart from "didn't check" — the whole scan degrades
gracefully to heuristics-only rather than failing. New top-level `reputation_checked` field on every
response (including the early-return error paths, for shape consistency). A Safe Browsing match
inserts its reason first and force-elevates risk to `"high"`.

**Verified in stages, each with real evidence, not guesses**:
1. A direct `curl` against the real Safe Browsing endpoint with the new key, using Google's own
   official test URLs (`testsafebrowsing.appspot.com/s/malware.html` and `/phishing.html`) — both
   correctly matched; a clean Wikipedia URL correctly did not.
2. The same test through the actual `scan_qr_codes()` Python function locally — correct risk
   elevation, correct reason text, `reputation_checked: true`.
3. Graceful-degradation paths verified separately: no key set → `reputation_checked: false`, heuristics
   still returned; an intentionally invalid key → real Google 400 caught and logged, scan still
   completes normally rather than erroring out.
4. Full live UI flow via Playwright against a local backend running with the real key — malware test
   QR correctly showed "High risk" with the Safe Browsing reason and the "Also checked against Google
   Safe Browsing" note; clean QR showed "Low risk" with the same note.
5. After deploy: the new `SAFE_BROWSING_API_KEY` secret was set on the HF Space via
   `HfApi().add_space_secret()` (separate from the existing `GEMINI_API_KEY` secret), the Space
   rebuild was polled to `RUNNING`, and only then was a real `curl` against the deployed
   `wram1708-ml-unified.hf.space` endpoint used to confirm the live backend actually returns
   `reputation_checked: true` and correctly flags the real test malware URL — not just that the Space
   reported `RUNNING`, per the project's two-failure/verify-before-done rule.

**Guide updated same round, in a follow-up "update user guide" request**: the "What this is (and
isn't)" section was sharpened to describe two signals instead of one, and a new "Notes & limits"
bullet was added specifically about Safe Browsing's coverage limit (it only knows about
already-crawled-and-classified sites, so a brand-new, not-yet-indexed phishing domain can still pass
both checks clean) and its graceful-degradation behavior.

Commits: ML-Unified `07ca07f` (Safe Browsing backend, HF-uploaded + secret set + verified live) →
ml-portfolio `d9a24d9` (surface `reputationChecked` in UI) → ml-portfolio `d030861` (guide sharpening).

## 7. Session close: log written, then a duplicate-request check

User asked "how to verify?" for the Safe Browsing addition — answered with concrete UI steps (upload
a test QR, look for the new "Also checked against Google Safe Browsing" note, open the User Guide) and
offered to generate a QR for Google's own official test malware URL so the user could see a real
Safe Browsing match without needing an actual malicious site.

User then said "update user guide" — re-checked the guide file first rather than assuming nothing had
changed since the last push, found the Safe Browsing content was already there from `d9a24d9` but the
"What this is (and isn't)" section still read as heuristics-only. Sharpened it to describe both
signals together, added a Safe-Browsing-specific limits bullet, verified the rendered markdown live via
Playwright, then committed and pushed as `d030861` (see commits list above).

This session log (`Conversations/Session_2026-08-19_PlantGrowthExportsQrPhishingTool_Part242.md`) was
then written and memory updated (`project_plant_growth_tool.md`, `project_qr_phishing_tool.md`,
`MEMORY.md`) per the user's "save above conversation to Conversations/" instruction — at that point
`d030861` had already been pushed, so the log's commit line above reflects the real final state rather
than a "pending" placeholder.

Two follow-up messages arrived after the log was first written: "commit and push" (re-checked
`ml-portfolio` git status — nothing new since `d030861`, nothing to do; confirmed the unrelated
pre-existing modified/untracked files in `ML-Unified` — `CLAUDE.md`, `ml-sql`/`ml-vision` changes,
`ci-test-*` model files, test fixtures — were left untouched, same as every prior session, since none
of them were created or modified by this session's work) and then a literal quote of the assistant's
own prior "ready to commit and push" message, asking to commit and push it — answered directly that
this was already done as `d030861` moments earlier, rather than re-running the same commit or
fabricating a new one to match the request.

## 8. Free RDAP domain-age check — a third signal, plus a real production bug

User asked how to make the QR Phishing Detector more robust "for free," explicitly requesting web
research rather than an off-the-top-of-the-head answer. Research ruled out VirusTotal (free-tier ToS
discourages live-product use, plus 4 req/min) and PhishTank (new API key registration closed since
2020 — a dead end), and identified RDAP — WHOIS's free, keyless, ICANN-mandated (since Jan 2025)
successor — as the strongest pick: it catches a brand-new phishing domain registered days ago, exactly
the gap Safe Browsing has (it only knows sites it has already crawled).

Built `_check_domain_age()` — free, no key, small in-memory TTL cache, <30 days registered → high
risk, 30-180 days → a medium-risk note, silent skip on any failure or unsupported TLD. Verified first
via synthetic mocks (fresh/medium thresholds, exact message text) and real network calls against known
old domains before any deploy.

**Two real bugs found only after deploying — via direct Space log evidence, not guessed**, consistent
with the project's two-failure/root-cause rule: a real-world positive-signal test (`fable5.ai`, found
by locally RDAP-querying a handful of plausible recent AI-product domain name guesses until one came
back under 180 days old — 72 days) returned "low risk, no reasons" on the deployed backend despite
working correctly locally. Pulled the real HF Space run logs directly (`/api/spaces/.../logs/run`,
using a bounded `curl --max-time` after the raw streaming endpoint hung once) and found two distinct,
real causes: (1) the lookup was querying the full hostname including subdomains
(`en.wikipedia.org`), which RDAP registries reject with a 400 — the registrable root domain
(`wikipedia.org`) was needed instead, meaning almost any real `www.`/subdomain URL was silently
getting no age signal at all, not just an edge case; (2) the original 6s timeout was fine on a local
machine but too tight for the Space's real network latency on RDAP's redirect-to-registry hop —
`fable5.ai`'s lookup timed out in production while succeeding instantly locally. Fixed both (use
`_registrable_domain()` at the call site; bumped timeout to 12s), then re-deployed and re-verified
against the REAL deployed endpoint with the same `fable5.ai` case (now correctly medium risk, "72 days
ago") and the Wikipedia subdomain case (now correctly resolves via its root domain, no false
positive) — not just re-checking `stage: RUNNING`.

Commits: ML-Unified `34f111e` (initial RDAP check) → `45f13af` (subdomain + timeout fix, both
HF-uploaded and re-verified live) → ml-portfolio `2ebaa6e` (guide update for the third signal).

## 9. RDAP explained, guide follow-up, and a small documentation gap

User asked "did you add about RDAP?" and separately "what is purpose of RDAP?" — confirmed the guide
already documented it across four sections (added in section 8's guide-update round) and explained
RDAP's role plainly: it answers "how old is this domain," which is the one thing neither structural
heuristics nor Safe Browsing can tell you, and it survives GDPR WHOIS-redaction because registries hide
registrant contact info, not the registration date itself.

A follow-up "update user guide" request turned up one real, small gap: the RDAP content itself was
already accurate, but the AI Assistant's suggested-question chips (`QR_PHISHING_SUGGESTIONS`) had never
been updated to include a domain-age question. Added one ("How does the domain-age check work?"),
verified live that all four chips render. Commit: ml-portfolio `ca03a8d`.

## 10. Feature brainstorm, then "Check a URL directly" built

Asked "anything else we can add as feature?" — offered a short list by effort: a direct URL-check input
(near-zero new detection logic, reuses the whole existing pipeline), handling non-URL QR payloads
(WiFi/vCard/crypto addresses currently get no analysis at all), URLhaus and Certificate Transparency as
additional free signals, and quality-of-life items (scan history, CSV export). User picked the
URL-check input as the strongest value-per-effort choice.

**Backend**: refactored the Safe Browsing + domain-age enrichment logic (previously inline inside
`scan_qr_codes`) into a shared `_enrich_with_reputation_and_age()` function, then added `scan_url()` and
a new `POST /rag/mm-qr-phishing/scan-url` endpoint that runs the exact same three-signal pipeline on a
pasted URL — no QR decode step at all. Sharing the enrichment code was deliberate: two independent copies
of the same Safe Browsing/domain-age logic would have been a real risk of the two paths silently
drifting apart over time.

**A real bug found while testing the new path, not before**: feeding plain non-URL text
("just some random text") into the new free-text input returned `is_url: true` with the entire garbage
string as the "host" — because `_analyze_url`'s `urlparse(f"http://{raw}")` fallback happily treats any
string as a hostname without validating it looks like one. This bug existed in the original QR-image
path too (a QR code can encode arbitrary text, not just URLs) but was unlikely to be hit there; a
free-text input box makes it trivial to trigger. Fixed with a new `_looks_like_hostname()` regex/IP
validator gating `_analyze_url`'s early return. Re-verified every existing URL-shape test case
(IP-literal, punycode, typosquat, `@`-trick, bare domain without scheme, a real fresh domain) still
scored identically after the fix, plus the QR-image path's regression case, before touching the
frontend.

**Frontend**: `useQrPhishingScan.ts` gained a `checkUrl()` action and a `scanUrl()` fetch function
mirroring `scanOne()`'s shape; `ScanEntry.preview` became nullable since a direct-URL check has no
image. `QrPhishingRunner.tsx` got a text input + "Check URL" button (Enter-to-submit) below the existing
photo upload, reusing the identical result-card rendering — and a small UX fix along the way: the
"Also checked against Google Safe Browsing" note was suppressed when the input wasn't a URL at all
(previously it would have shown a confusing "reputation check unavailable" note for garbage text), and
a dedicated "This doesn't look like a URL — nothing to check" message added for that case instead. Guide,
page summary, and runner docstring all updated to describe the dual input mode.

**Verified live end-to-end**: a real fresh domain (`fable5.ai`) through the new URL input returned the
correct medium-risk result with no image involved; garbage text correctly showed "Not a URL" with the
new message; the original file-upload path re-tested and confirmed unaffected by the refactor. After
deploying, hit the real `/scan-url` endpoint on the deployed HF Space directly with both a real fresh
domain and garbage text — both matched local behavior exactly, not just `stage: RUNNING`.

Commits: ML-Unified `94d8f68` (scan-url endpoint + shared enrichment refactor + hostname-validation
fix, HF-uploaded and verified live) → ml-portfolio `7f6ce54` (URL input UI, guide/summary updates).

This final section was added afterward to keep the saved log accurate through the end of the actual
conversation.

## How to apply going forward

- **A brainstormed security/detection idea with two conceptually different halves** (a well-defined
  structural/heuristic half vs. a half that needs a maintained reference dataset) can be shipped as
  just the well-defined half, with the dropped half named explicitly — better than skipping the whole
  idea or fabricating data for real institutions to cover the harder half.
- **A tool's first version doesn't need to anticipate every UX follow-up** — shipping single-file
  upload first, then upgrading to batch once the user actually asked for it, kept each change small
  and independently verifiable, rather than over-building speculative capacity up front.
- **Google API keys are not universally interchangeable across APIs even within one project** —
  specifically, AI-Studio-issued Gemini keys can be *service-account-bound*, which Google hard-restricts
  to a small allowlist of APIs (Vertex/Gemini only) regardless of what's enabled on the project or what
  restriction UI shows elsewhere. A different, ordinary API key is needed for any other Google API.
  Confirmed this from the Cloud Console's own explanatory text rather than assuming key scope.
- **For any external reputation/threat-intel API integration**, gracefully degrading to
  heuristics-only (not erroring the whole feature) when the key is missing or the call fails is the
  right default — and returning a explicit "was this check even attempted" field (`reputation_checked`)
  lets the frontend be honest about which mode actually ran, rather than silently showing fewer results
  with no explanation.
- **Verifying a newly-added external-API-backed backend feature after deploy** means hitting the real
  deployed endpoint with a real payload designed to trigger the new code path (Google's own official
  test malware/phishing URLs, in this case) — `stage: RUNNING` on the Space alone was never treated as
  suf­ficient evidence, consistent with this project's standing rule.
- **A "low risk, no reasons" result from any gracefully-degrading feature is ambiguous** — it can mean
  "checked, found nothing" or "silently failed." Proving a deployed integration actually works needs a
  real POSITIVE test case (a genuinely-young domain, a genuinely-malicious test URL), not just a clean
  negative case that would look identical either way.
- **Domain-reputation lookups (RDAP, and likely similar APIs) expect the registrable root domain, not
  an arbitrary hostname** — strip subdomains before querying, or most real-world `www.`/service-
  subdomain URLs will silently fail the lookup with no error surfaced to the user.
- **A timeout tuned to local-machine latency can be wrong for the deployed environment** — cost a full
  extra deploy-and-verify cycle here. When a call involves a redirect/bootstrap hop, size the timeout
  with real headroom rather than the fastest locally-observed round-trip.
- **A new input surface can expose a validation gap that an existing surface never triggered** — the
  QR-image path could theoretically encode arbitrary non-URL text too, but a free-text input box makes
  hitting that path trivial rather than incidental; test the new surface's edge cases explicitly instead
  of assuming existing coverage transfers.
- **Sharing enrichment/analysis logic between two entry points to the same feature (QR-image scan vs.
  direct-URL check) up front, via one refactor, is cheaper than letting two copies exist and drift** —
  done here specifically to keep the Safe Browsing/domain-age logic from silently diverging between
  paths in the future.
