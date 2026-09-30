# Part 302 — Observability (error tracking), full upload/LLM security hardening, and a Testwright deep-fix pass

Continues [Part 301](Session_2026-09-29_The502RootCauseAndFullFeatureTrackingBuild_Part301.md).
2026-09-30. Started from two user concerns — **"how do we find the cause of a
glitch/exception?"** and **"how do we detect & block malicious uploads?"** — which
drove an error-tracking build and a full security-hardening arc. Then a long
**Testwright (QA Run)** investigation and fix pass. Through-line, again:
**measure live; the evidence beat the plan more than once.**

---

## 1. Error tracking (observability)

User wanted root-cause visibility for glitches. The frontend `error` event logged
only a class name; the FastAPI backend had **no global exception handler** (errors
reached only the Space's ephemeral stdout). Built TWO complementary systems, both
content-free (LOGGING_SPEC §6), full detail in `docs/ERROR_TRACKING.md`:

- **DIY first-party error store (PRIMARY).** `ml-portfolio/supabase/errors.sql`
  (`errors` table + `error_groups` RPC, GROUP BY fingerprint=`source:kind:route`);
  one shared `/api/error` endpoint (POST ingest from browser AND backend, GET
  grouped read). Backend posts there (default `SITE_URL`), so **no Supabase creds
  on the public Space**. Frontend `useErrorTracking` sends kind/message/stack/route/
  session_id (password page excluded, query stripped). Backend
  `error_capture_dispatch` middleware (innermost) catches unhandled router
  exceptions, best-effort posts, then **re-raises** so Sentry + default 500 still
  apply. `AnalyticsErrors.tsx` dashboard panel. User ran errors.sql (with RLS on —
  service_role bypasses it, anon locked out). **Verified live:** injecting doc →
  stored + grouped, query stripped; backend path re-raises correctly.
- **Sentry (optional bonus).** `@sentry/nextjs` via Next 16 **native** hooks (no
  `withSentryConfig` — v11 doesn't export it cleanly; only needed for source-maps).
  `sentry-sdk[fastapi]` on the backend. No Session Replay, no tracing, `beforeSend`
  strips user/IP + request bodies. User set both DSNs; **frontend verified live**
  (test error reached Sentry 200); backend wired, not independently forced.

**Bug caught by verification:** my `needs_setup` detection matched only "does not
exist"/message; Supabase actually says "Could not find … in the schema cache" with
the code in `error.code`. Fixed to check `error.code` (PGRST205/202) + message, in
both `/api/error` and `/api/feature-usage` (`325b82b`).

## 2. Security hardening — uploads + LLM input (COMPLETE)

Full surface, detail in memory `project_upload_malware_gate`:

- **Malicious file uploads — block everywhere (`4517b09`, 36 files HF-uploaded).**
  Before: ~30 routers *scanned* (advisory log) but only ONE (`mm_ingest`) actually
  **blocked**; 8 upload routers scanned nothing. Added `gate_or_raise()` to
  `security/file_gate.py` (scan + `blocking_matches` → 400 on EICAR/embedded-PE/
  webshell; advisory heuristics like entropy still only log, so legit files never
  falsely rejected). Converted 27 advisory callers → blocking; gated the 8
  unscanned (document, rag/ingest, shap model+csv, vision/classify, core
  inference/monitoring, drift, eda). Left alone: `mm_malware_image` (must accept
  suspicious samples) and `mm_ingest`. **Verified live:** EICAR .txt → 400; benign
  → passes.
- **Prompt-injection detection — flag + log, never block (`549624e`, `4afab46`).**
  `security/prompt_gate.py` reuses `prompt_injection_check.detect_heuristics`
  (strong categories only), logs content-free `prompt_injection_flagged`. Wired
  into rag/ingest, document/analyze, mm-ingest (the text→LLM choke points). User
  chose flag+log over blocking (a legit doc can contain such phrasing). **Verified
  live:** injecting doc → flagged {direct_override,jailbreak} yet still processed;
  benign → clean.
- **Decompression bombs + consistent size caps (`dd19f1c`, `aa9a56d`).**
  `security/decompression.py` `zip_bomb_check()` (a .docx IS a zip) rejects 413 on
  huge uncompressed/ratio/entry-count; wired into document/analyze. `app.py` caps
  PIL/OpenCV pixels (~64MP) before routers import cv2/PIL → all image paths at once.
  Fixed a real inconsistency: mm-ingest declared 20MB but the global 10MB gate
  shadowed it → added `/rag/mm-ingest`=20MB to body_size route caps. **Verified
  live:** 20KB bomb.docx (20MB/ratio~1000) → 413; app booted clean with the pixel cap.
- **Prompt-hardening (`073843a`).** `citations.build_system_prompt` leads the
  retrieved-chunk block with an untrusted-data rule (commands inside are data, not
  instructions); `document/_llm` classify+extract carry the same clause. The deeper
  defense pairing with the flag+log detection. Deploy health-verified.

## 3. Testwright (QA Run) — investigation + fixes

User: runs slow (esp. 2nd), no stop button, self-heal seems ineffective. Full
plan: `docs/TESTWRIGHT_IMPROVEMENT_PLAN.md`. Detail in memory
`project_testwright_run_perf`.

**How Run works:** `/qa/run/execute` fires a `workflow_dispatch` at the public
`ramleo/ml-qa-runner` repo; frontend polls `/qa/run/status` while GitHub Actions
runs the test on a fresh runner. Nothing runs in the Space/browser.

**Root causes (measured live):**
- **Slow:** a trivial sample = ~68s wall-clock but the **test itself ran ~0.9s** —
  ~99% is CI setup. The workflow reinstalled npm + `playwright install --with-deps
  chromium` (~150MB + apt) **every run**, no cache/container.
- **No stop:** no Stop button; `reset()` only stopped the client poll, not the GH
  job; no cancel endpoint.
- **Self-heal DOES re-run** (RunRunner.tsx:72) = a 2nd full cold cycle, and it
  **hallucinated a locator**: healed to `getByPlaceholder('Search all 58 tools')`
  when the real placeholder is `Search 58 tools — try …` → still failed.
- **A "why is it failing" question, root-caused live:** the AI's first-draft test
  used `getByRole('link', {name:'Tools'})` which matches **6 links** on the homepage
  → Playwright **strict-mode violation** on `.click()`; and `getByPlaceholder('Search
  tools...')` doesn't exist. The test was wrong (guessed locators), not Testwright.

**Shipped + verified:**
- **Container workflow** (`ml-qa-runner 5ee9264`): official Playwright image, dropped
  the browser install + setup-node. **MEASURED modest: ~68s → ~50-56s, NOT the
  ~10-20s I predicted** — GitHub-hosted runners are ephemeral and re-pull the ~2GB
  image every run, so it replaces the download rather than removing the floor. Speed
  is download-bound; the real lever is a warm/self-hosted runner.
- **Stop/cancel** (`970d8f3` backend HF + `3bb1be3` frontend): `cancel_run()` →
  GitHub cancel API; `POST /qa/run/cancel/{id}`; Stop button that cancels the GH job,
  not just the poll. Verified button appears during a run.
- **Execution-time** (`3bb1be3`): result shows `test 0.9s · total 55.8s`.
- **Self-heal grounding** (`21fc8c6` HF): HEAL_SYSTEM now hard-requires every locator
  string be copied VERBATIM from the ARIA snapshot; a search box uses
  `getByRole('searchbox'/'textbox',{name:<exact>})` not a guessed placeholder.
  **Verified end-to-end:** reproduced the failing case → heal → re-run **PASSED**.
- **Progress polish** (`acf5d04`): live elapsed timer, phase caption, "~40-60s
  first-run setup" note, Open-on-GitHub during the run, honest timeout message.
- **Auto-naming** (`2d78f6e`): `deriveTestName()` names runs/saves from the test's
  `describe`/`test` title when the Test name field is blank, instead of "Untitled
  test."

**Still pending (per the plan, my recommendation in parens):** warm/self-hosted
runner for seconds-fast runs (**skip** — cost + security for a free portfolio);
P4b confirm-before-rerun so a bad heal doesn't auto-spend a ~50s cycle (**worth
doing, cheap**); browser-cache/lockfile (parked, comparable to container); queue
note (minor). The plan doc's §5 is slightly stale (lists P4a/P5 as "Later" though
they shipped).

## Key decisions

- **DIY error store is primary, Sentry a bonus** — first-party, on infra we already
  run at $0, survives Space restarts; Sentry adds grouping/alerts but is a 3rd party.
- **Malware uploads: block everywhere; prompt injection: flag+log, don't block** —
  malware signatures are false-positive-safe to reject; injection phrasing can appear
  in legit docs, so blocking would break real use. User made both calls.
- **Container kept despite modest gain** — cleaner, no regression, slightly faster;
  but honestly re-labeled as NOT the speed fix (warm runner is).

## Lessons

- **Measure; don't trust the blog.** The container "Docker layer caching handles the
  pull" claim is false for ephemeral GitHub-hosted runners — they re-pull the ~2GB
  image. My ~10-20s prediction was wrong; live runs showed ~50s. Corrected the plan +
  memory. [[feedback_status_claims_need_evidence]]
- **Verification catches your own bugs.** The `needs_setup` schema-cache detection
  and the self-heal hallucination were both found by live testing, not review.
- **A failing test can be the correct outcome** — the strict-mode "Tools" link and
  the wrong placeholder were the AI-draft test's fault; Testwright reporting the
  failure is it working, and Heal (now grounded) fixes it.
- **Grounding beats "don't hallucinate."** The heal prompt already said "don't invent"
  yet guessed a placeholder (placeholders aren't in the ARIA snapshot). The fix was
  to force verbatim-from-snapshot + role locators, and it verified as passing.

## Commits

| Repo | Commits |
|---|---|
| ml-portfolio | `e9458f8` (Sentry FE) · `d715db1` (DIY store) · `325b82b` (needs_setup fix) · `4afab46`/`aa9a56d` (privacy) · `3bb1be3` (Stop+exec-time) · `acf5d04` (progress) · `2d78f6e` (auto-name) |
| ML-Unified (backend, HF-uploaded) | `f24193a` (Sentry BE) · `40a6f53` (error capture) · `4517b09` (malware gate ×36) · `549624e` (prompt-injection) · `dd19f1c` (decompression) · `073843a` (prompt-hardening) · `970d8f3` (cancel) · `21fc8c6` (heal grounding) |
| ML-Unified (docs) | `c7ada53` (Testwright plan) · `0cfd4fa` (plan corrected w/ measured evidence) |
| ml-qa-runner | `5ee9264` (container workflow) |

## State after this session

- **Observability:** DIY error store + Sentry live; both content-free.
- **Security:** upload/LLM-input surface COMPLETE (malware block, decompression
  bombs, size caps, prompt-injection detect + hardening) — all verified live.
- **Testwright:** stoppable, shows timing, honest progress, self-heals with grounded
  locators, auto-named runs, modestly faster; no regressions. Only real speed lever
  left is a warm runner (recommended skip). P4b confirm-before-rerun is the one cheap
  worthwhile open item.
- Related: [[project_sentry_error_reporting]], [[project_upload_malware_gate]],
  [[project_testwright_run_perf]], [[reference_logging_spec]].
