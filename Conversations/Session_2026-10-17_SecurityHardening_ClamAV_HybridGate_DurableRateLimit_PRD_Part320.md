# Part 320 — Security hardening (ClamAV full-AV, 50 MB cap, hybrid gate, durable rate limit) + the product PRD

A security-led session that started as Q&A ("is the site guarded against dangerous
uploads / RCE?") and turned into four concrete hardening ships plus a product
requirements doc. Theme throughout: **answer honestly first, verify with evidence,
and treat the project's deliberate trade-offs (free-tier, login-less, availability)
as the design constraints they are — not bugs.**

Builds on Part 319 (click audit + dashboard). All backend work is on the HF
**Docker Space** (`sdk: docker`), which is what made ClamAV feasible at all.

## Arc 0 — security Q&A (text-only, no code)
Four questions, answered from the real code rather than memory:
- **"Dangerous file upload — are we guarded?"** Yes: `security/file_gate.py`
  `gate_or_raise` is wired into 35 upload routers (YARA block + size/zip/image-bomb
  caps + skops model-load allowlist). Honest gap named: it's signature/heuristic,
  not a full AV engine.
- **"What is an AV engine?"** Plain explanation (antivirus scanner; full engines =
  millions of auto-updated signatures vs our ~6 YARA rules).
- **"Guarded against RCE?"** Audited the real sinks: no `eval`/`exec` on user input;
  subprocess calls are arg-list (no `shell=True`) with server-generated paths; the
  one model-upload deserialization path was already closed with **skops** (type
  allowlist, no `builtins`/`os`/`subprocess`). Website (Next.js) sinks all benign
  (static theme script; `mdToHtml` escapes-first; map SVG is a first-party asset).
  Verdict: **no server RCE path.**
- **"RCE = which two attacks?"** = **Arbitrary Code Execution + Remote delivery**;
  in practice reached by chaining an injection/deserialization flaw with a
  remotely-reachable input.

## Arc 1 — ClamAV full-AV engine + 50 MB document cap
Chosen via AskUserQuestion: **ClamAV with the DB baked at build**, and **50 MB** doc
cap. Feasibility first confirmed the Space is a Docker Space (so `apt install` works)
on free CPU-basic (~16 GB RAM — enough).
- New `security/clamav_scan.py` (clamd TCP client, fails open). `gate_or_raise` now
  runs YARA (instant) + ClamAV (deep). Dockerfile: install clamav/daemon/freshclam,
  strip the Debian `Example` line, `freshclam` at build (fail-soft), minimal
  `clamd.conf` (TCP 3310, 60 MB limits), `clamd &` before uvicorn.
- Doc cap 10→50 MB: **both** `body_size.py` `_ROUTE_CAPS["/document/analyze"]` **and**
  `routers/document/router.py` `MAX_FILE_BYTES` had to move together (the 10 MB
  global otherwise shadows the route). UI "10 MB" strings → "50 MB".
- Detection survives the bigger cap: malware/ClamAV scan every byte; zip-bomb keys
  off *declared* uncompressed size (150 MB/200:1), independent of the upload cap.
- **Verified live:** EICAR→400, 30 MB→200, 55 MB→413.

### The verification lesson (Arc 1b)
First deploy used `freshclam --quiet` → build logs couldn't confirm the DB
downloaded, and clamd logs to a *file* not stdout, so run logs didn't show it
either. Rather than guess, added a **`/health` ClamAV probe** (`clamav_status()`
pings clamd, returns its version string incl. the DB revision) and shipped it as a
fast cached rebuild. Result: `clamav.reachable:true, "ClamAV 1.4.3/28156/..."` —
positive proof the engine is up with today's DB. **Lesson: when a daemon's health
can't be seen in logs, add a probe; don't use `--quiet` on a build step you need to
verify.**

## Arc 2 — the XSS false alarm (recommendation withdrawn)
Earlier I'd flagged `dangerouslySetInnerHTML` as a likely live XSS. On actually
reading all three usages: theme script is hardcoded; `mdToHtml` escapes `&<>`
before formatting and emits only its own tags; the analytics map injects a
first-party static SVG with data rendered via normal JSX. **No XSS bug** — withdrew
the recommendation rather than invent a fix. (Lesson reinforced: a grep hit is a
lead, not a finding — read the implementation.)

## Arc 3 — the product PRD (`docs/prd/`, local-only)
Asked: "create a PRD from the website; can I replicate the product from it?" Built a
6-file PRD (overview, architecture, cross-cutting systems, the **58-tool catalog**
extracted from `capabilities/*.ts`, a Document Intelligence deep-dive) under
`docs/prd/`. The honest replication answer: a PRD gets you a product that *meets the
requirements* (~70–85%), not a byte replica — the missing part (exact models,
prompts, thresholds, infra, hard-won fixes) lives in code + docs + Conversations.
- Caught a gap on review: **the 5 platforms** (ML Unified, EDA, Vision, Testwright,
  Text-to-SQL, from `registry.json`) were referenced but not listed — added a
  Platforms section.
- **Not pushed:** ML-Unified is a PUBLIC repo; a PRD consolidates soft spots + is a
  replication recipe, so it's an internal artifact. Added `docs/prd/` to
  `.gitignore` (kept local-only; the `.gitignore` edit itself left uncommitted —
  no need, since the files are already ignored).

## Arc 4 — closing the honest gaps
The PRD naming of soft spots prompted "why do these gaps exist, can you fill them?"
Explained all three are deliberate trade-offs (cost / login-less / availability),
then fixed two:
- **Gap 3 — scanner fails open → hybrid.** `gate_or_raise` now: **YARA mandatory /
  fail-closed** (in-process, no daemon; can't-run → 503, never a silent pass) +
  **ClamAV enforced once ready** (new `clamav_scan()` returns `(scanned, matches)`;
  a `clamd.ping()` separates the 20–30 s warmup, where it falls back to YARA, from a
  ready daemon, where a detection *or* a scan error blocks). Advisory path
  (`scan_upload_bytes`, used by mm_malware_image/mm_ingest) kept fail-open. 4 tests
  added; verified live (EICAR→400, benign→200, clamd reachable).
- **Gap 1 — per-instance rate limit → durable.** Found the project already had a
  DB-backed limiter (`security_log`'s `log_security_event`), so mirrored it rather
  than add Upstash. New `supabase/rate_limit.sql` — reusable
  `rate_limit_hit(bucket, ip_hash, max, window)` + RLS-locked counter table +
  15-min purge. Audit route keeps the in-memory map as a cheap first pass and adds
  `dbRateLimited()` as the authority (salted IP HMAC via `AIRAML_LOG_TOKEN`, same
  scheme as security_log; **fails open** if the SQL isn't applied). **No auth
  needed** — rate limiting keys off IP, not identity (that was Gap 2's requirement).
  User ran the SQL; verified the function flips `true,true,true,false,false` at
  cap 3.
- **Gap 2 — forgeable audit ids** left open by design: only real fix is server-side
  auth, which conflicts with the login-less showcase.

## Arc 5 — keeping the docs in sync
- **Handbook:** rebuilt (`build-handbook.py`) — the only user-facing change was the
  50 MB doc text; the security work is internal infra, not tool-guide content.
  Re-ran later → no diff → confirmed in sync.
- **PRD:** updated `02-cross-cutting-systems.md` after the gap fixes (the gate is no
  longer "fails open"; the rate limit is no longer "in-memory per-instance"). Local
  edit only (gitignored).

## Lessons (2026-10-17)
- **Answer security questions from the code, not memory** — every "are we guarded?"
  was verified by grep + reading the sink before answering.
- **A grep hit is a lead, not a finding** (the XSS false alarm). Read the impl; be
  willing to withdraw a recommendation.
- **Verify daemons with a probe, not log-greps** — clamd logs to a file; `--quiet`
  hid freshclam. The `/health` field is the durable proof.
- **Reuse the project's own patterns** — Gap 1 mirrored the existing
  `log_security_event` DB-limiter instead of a new vendor; consistent + no new
  secret.
- **Fail-open vs fail-closed is a per-concern choice:** YARA (reliable, in-process)
  → fail-closed; ClamAV (daemon, warmup) → enforce-once-ready; read paths that
  expose data → fail-closed; a limiter that could break capture → fail-open.
- **Honest gaps are design, not debt** — named the trade-offs; fixed the two cheap
  ones; left Gap 2 (needs auth) explicitly open.

## Setup state (production, as of 2026-10-17)
- **ClamAV** live on the Space (Docker Space; DB baked at build; clamd on TCP 3310).
  `/health` reports `clamav.reachable` + DB revision. Falls back to YARA if clamd
  is down.
- **Document upload cap = 50 MB** (`body_size.py` route cap + `MAX_FILE_BYTES`).
- **Durable rate limit:** run `supabase/rate_limit.sql` once (done). Audit route
  uses it; fails open if absent. Salt = `AIRAML_LOG_TOKEN`.
- **PRD** lives at `docs/prd/` — **local-only, gitignored, never pushed** (public
  repo).

## Commits
**ML-Unified** (backend + docs):
- `5a415e5` — ClamAV deep-scan + 50 MB cap (Dockerfile, gate, body_size, router, deps)
- `646eb4e` — live ClamAV status on `/health`
- `a3a4644` — hybrid gate (fail-closed YARA + enforce-once-ready ClamAV) + 4 tests
- `87cb497` — docs: durable rate limit note (CLICK_AUDIT.md)

**ml-portfolio** (frontend + SQL):
- `cbacc26` — UI 10→50 MB (document-intelligence)
- `9a77c0b` — handbook regenerate (10→50 MB)
- `e00dc65` — durable cross-instance rate limit (route + `supabase/rate_limit.sql`)

**HF Space uploads:** 3 rounds — full rebuild for `5a415e5` (torch layer cached,
~6 min), cached for `646eb4e` and `a3a4644` (~3 min each). No upload for Gap 1
(ml-portfolio/Vercel, no `ml-api` change).

**Not committed:** `docs/prd/*` (gitignored, local-only); the `.gitignore` edit
itself (unnecessary — files already ignored).
