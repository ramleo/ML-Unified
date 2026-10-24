# Test Cases — ML-Unified + ml-portfolio

**Last updated:** 2026-10-24  
**Total test cases:** ~1798, covering Parts 1–330 (full range, no gaps).
**Open gaps:** none currently known — see "Coverage Gaps" below for pre-existing
narrower gaps unrelated to Part ranges. **Next open range, if the project continues
past Part 330:** any parts beyond 330 have no coverage yet — check `Conversations/`
for new session logs before assuming this index is current.

---

## Edge Cases (standing list, separate from TC files)

Tracked separately at [EDGECASES.md](testcases/EDGECASES.md) — a running list of
edge cases as they're noticed, each of which also gets a numbered TC entry in
the relevant TC-*.md file. **All 8 items from this pass are now resolved,
none open.** Real findings closed: stale visualAction dropdown across
document switches (commit `9dd24be`); vision-captioner collage hallucination
(commits `9814f79`+`a14d356`); AI Sharpen's error message fixed and its
persistence-across-switch design confirmed intentional via code reading
(commit `8e985ce`); video timestamp citation jump verified correct across a
document switch (built synthetic fixture); contradiction-check detection
verified working end-to-end once its Groq-dependency was fixed (its original
citation-click test design turned out to test a feature that doesn't exist);
Groq dropped entirely from every automatic/default path across `ml-api` and
`ml-eda` per explicit instruction, after two earlier attempts (a unilateral
`openai/gpt-oss-*` swap that was reverted, then `groq/compound` which hit
real rate-limit/payload errors) — commit `9747241`, `ml-eda`'s copy deployed
separately (`wram1708/ml-eda` Space), pending only a `MISTRAL_API_KEY` secret
the user needs to add manually. Plus 3 verified no-bug fixes.

---

## Test Case Files

| File | Prefix | Parts Covered | Count | Status |
|------|--------|--------------|-------|--------|
| [TC-DOC.md](testcases/TC-DOC.md) | TC-DOC | E2E docs, README, Vision | 75 | ✅ |
| [TC-PEND.md](testcases/TC-PEND.md) | TC-PEND, TC-BUG, TC-ARCH | Pending features, EDA bugs, Architecture | 47 | ✅ |
| [TC-EARLY.md](testcases/TC-EARLY.md) | TC-EARLY | Early May sessions | 60 | ✅ |
| [TC-P1.md](testcases/TC-P1.md) | TC-P1 | Parts 1–15 | 92 | ✅ |
| [TC-P2-A.md](testcases/TC-P2-A.md) | TC-P2 | Parts 16–24 | 75 | ✅ |
| [TC-P2-B.md](testcases/TC-P2-B.md) | TC-P2 | Parts 25–33 | 83 | ✅ |
| [TC-P3.md](testcases/TC-P3.md) | TC-P3 | Parts 34–50 | 150 | ✅ |
| [TC-P4.md](testcases/TC-P4.md) | TC-P4 | Parts 51–65 | 90 | ✅ |
| [TC-P5.md](testcases/TC-P5.md) | TC-P5 | Parts 66–90 | 72 | ✅ |
| [TC-P6.md](testcases/TC-P6.md) | TC-P6 | Parts 91–110 | 64 | ✅ |
| [TC-P7.md](testcases/TC-P7.md) | TC-P7 | Parts 111–124 (AutoML + Optuna) | 52 | ✅ |
| [TC-HIST.md](testcases/TC-HIST.md) | TC-HIST | Parts 107–112 | 44 | ✅ |
| [TC-REC.md](testcases/TC-REC.md) | TC-REC | Parts 113–116 | 24 | ✅ |
| [TC-P8.md](TC-P8.md) | TC-P8 | Parts 125–157 (RAG, Chat AI, Drift, AutoML, Feature Eng, Ensemble, SHAP, Optuna, KB) | 90 | ✅ |
| [TC-P9.md](TC-P9.md) | TC-P9 | Parts 173–200 (Text-to-SQL feature sprint, Real-Time Analytics dashboard, index.html split + HF tracking, Vision fixes, Document Intelligence) | 128 | ✅ |
| [TC-P10.md](TC-P10.md) | TC-P10 | Parts 201–249 (Document Intelligence provider cascade, Multimodal RAG + MMRAG-01→28 backlog, CV forensics, Inpainting, Sharpen/Deblur, homepage redesign, Adversarial Robustness Lab, Face Cloak, Style Cloak, adversarial training, sitewide theme sweep, CI fix, theme toggle, 2026-08-24 multi-doc edge-case pass) | 103 | ✅ |
| [TC-P11.md](TC-P11.md) | TC-P11 | Parts 158–172 (RAG tiered retrieval + web override, drift data versioning, EDA microservice deploy, full Text-to-SQL Agent build: guardrails, 4-engine DB support, ERD diagram, pagination, MSSQL, NL filter, saved queries, chart build-out-then-removal, follow-up suggestions) | 99 | ✅ |
| [TC-P12.md](TC-P12.md) | TC-P12 | Parts 250–259 (logging/silent-exception audit, homepage search-bar scroll bug, sitewide theme audit, FFT steganography/moiré shipped + AI-splice rejected, stegomalware payload ID, PRNU, EC-001→008 multi-doc edge-case pass, Groq removal, deepfake A/V, domain NER, face deanonymization, keystroke inference, movement/gait comparison, email auth, extension analyzer, prompt-injection playground, AI-code detector, crime-scene SfM, Grounded-SAM rotoscope, astrophotography, wildlife re-ID, PPE, ASL fingerspelling) | 94 | ✅ |
| [TC-P13.md](TC-P13.md) | TC-P13 | Parts 260–269 (cybersecurity sprint: password audit/DNS-tunneling/SIEM-triage/phishing-classifier/TLS-headers/malicious-package/attack-surface/keystroke-biometric/YARA/SAST-merge; app-safeguard security/ layer + CORS/rate-limit/budget bugs; site design audit + product/CV split + 50 tool-description rewrite; tools-section rebuild (ranked search, mobile cards, tag chips); globals.css split + 400-line CI gate; area pages + photo thumbnails; handbook-as-book + 50 deep chapters, read-aloud, guided demos, phone PDF, search + rail; the mm-ingest entropy-rejection bug) | 73 | ✅ |

| [TC-P14.md](TC-P14.md) | TC-P14 | Parts 270–279 (handbook demo markers + 2x-speed audio, return-to-position scrolling, the demo-clip audit + recorder rebuild (headed-Chrome WebGL, hover/drag/range, title/closing cards, audio-offset + dead-air fixes, spotlight `with`), three shipped backend bugs (/models 500, drift invented-baseline, CatBoost never ran), the full provider audit (Mistral best-effort free tier, Groq retired models, Cohere promoted, Gemini demoted) + efficiency work, the logging spec (trackedFetch/instrument, llm_calls, security_log), and the security-log hardening arc (DB rate limit, Turnstile, CSP, IST views)) | 66 | ✅ |

| [TC-P15.md](TC-P15.md) | TC-P15 | Parts 280–289 (last handbook clips + their tool bugs, frontend Playwright/vitest suites + 6 heading-less pages, backend test phases (deterministic shell + nightly golden evals), ml-eda fold-in (NaN-kurtosis 500, retired-model suggest, 500-as-CORS) + self-origin 403, numpy-2/pandas-3/opencv-5 migration fallout, repos public (AGPL) + name-collision + "Mastercard" scope, the E9–E21 security sweep (baseUrl key leak, pickle RCE, DuckDB file-read, SSRF, unauthenticated DELETE, cost caps, provider-auth alerting), WEBSITE_GUIDELINES a11y/CWV pass, clips-as-integration-tests (null judges, OpenCV-5 HoughLinesP 500)) | 54 | ✅ |

| [TC-P16.md](TC-P16.md) | TC-P16 | Parts 290–299 (last demo clips + fade fix + un-clippable tools, six security tools (Log Anomaly/JWT/Secret-PII/Exploit-Payload/Network Intrusion) + forgotten side-registrations, the Testwright platform build (tool-card→/qa world→GitHub-Actions runner→5 stages→flakiness/assertions/visual/ownership, recorder dropped), Text-to-SQL graduating to a platform, /ml /eda /vision native worlds + HF-app reskin, TECH_STACK.md map, API-docs + git-history secret sweep, the HF token leak, handbook rebuild (Platforms Part 1) + MMRAG clear-out (Periodicity Finder, Scan Descreen, Meeting Intelligence)) | 42 | ✅ |

| [TC-P17.md](TC-P17.md) | TC-P17 | Parts 300–309 (logging-vocabulary activation + per-tool feature tracking, the 502 worker-starvation root cause + Mistral removal, observability (DIY error store + Sentry), upload/LLM security hardening (malware block-everywhere, prompt-injection flag+log, decompression bombs, prompt-hardening), and the long Testwright maturation arc — Run perf, Stop/cancel, self-heal grounding, Discover grounding, deterministic locator disambiguation, grounded-action gate, generation-sees-destination-pages, verify-repair loop, syntax guard, durable/interactive dashboard) | 44 | ✅ |

| [TC-P18.md](TC-P18.md) | TC-P18 | Parts 310–319 (Testwright model selection (owner paid + BYOK) + scheduled monitoring, the two-week-stale CI rescue, 15 tool guides wired, the doc-coverage CI gate, the full observability roadmap O1–O6 (trace id, RUM, LLM telemetry front+back, Sentry trace-tag, SLOs, agent spans) + the ts-column bug, Testwright self-testing + Run-Live Companion + TW-GROUND stacked bugs + Activity Log, analytics dashboard redesign, Phase 2 fixtures/fake-media + npm publish + the volatile-control taxonomy (6/6 green) + Node-26 companion crash, and the crash-durable click-audit subsystem) | 40 | ✅ |

| [TC-P19.md](TC-P19.md) | TC-P19 | Parts 320–330 (ClamAV/hybrid-gate/durable-rate-limit hardening; the platform-roadmap arc — Q5 auth + auth-UX + avatars, Q1 public API, Q2 MCP M1+M2 expanded surface, Q4 eval platform M1→M3 (dashboard, golden set, online judge), Q3 chatbot builder M1 isolation → M4b Stripe billing + embed widget; site-search, homepage-chat starter chips, tool-header fix; and the homepage-chat grounded-RAG rework + copy/links/context + upload-affordance follow-up) | 34 | ✅ |

**Total: 25 files written, ~1798 test cases, covering Parts 1–330 (full range, no gaps).**

---

## Generation History

| Session | Date | Files Written | TCs | Method |
|---------|------|--------------|-----|--------|
| Round 1 | 2026-06-23 | TC-DOC, TC-PEND, TC-REC, TC-HIST | 190 | 4 parallel agents |
| Round 2 | 2026-06-23 | TC-EARLY, TC-P1, TC-P2-A, TC-P2-B, TC-P4 | 400 | subagents writing to disk |
| Round 3 | 2026-06-26 | TC-P3, TC-P5, TC-P6, TC-P7 | 338 | 4 parallel agents |
| Round 4 | 2026-07-05 | TC-P8 (Parts 125–157, complete) | 90 | Inline — no subagents; full coverage in 2 passes |
| Round 5 | 2026-08-22 | TC-P9 (Parts 173–200, complete) | 128 | Inline — no subagents, per explicit user instruction; scoped to Part 200 (not full 249) |
| Round 6 | 2026-08-22 | TC-P10 (Parts 201–249, complete) | 93 | Inline — no subagents, continuing "keep going" instruction |
| Round 7 | 2026-08-22 | TC-P11 (Parts 158–172, complete) | 99 | Inline — no subagents; corrected a prior false "no logs exist" claim (logs existed under a different filename prefix, `Conversation_` not `Session_`) |
| Round 8 | 2026-10-24 | TC-P12 (250–259), TC-P13 (260–269), TC-P14 (270–279), TC-P15 (280–289), TC-P16 (290–299), TC-P17 (300–309), TC-P18 (310–319), TC-P19 (320–330) | 447 | Inline — no subagents; batches of 10 parts per file, full line-by-line re-read of every session log |

---

## Quick Reference by Category

| Category | Description |
|----------|-------------|
| Bug-Regression | A bug was fixed; test prevents it coming back |
| Feature | New capability; test verifies it works end-to-end |
| Backend API | pytest test against a FastAPI endpoint |
| E2E | Full user journey across frontend + backend (Playwright) |
| UI | Visual/DOM structure, no backend call |
| Data | Input validation, schema contract |
| Animation | CSS/JS animation correctness |
| Architecture | Service boundaries, async, concurrency |

---

## Pending Test Cases (TC-PEND)

47 open TCs tied to unbuilt backlog items. They close as features land:

| Backlog Item | Relevant TCs |
|-------------|-------------|
| #19–22 Pipeline Builder | TC-PEND-015 |
| #23 Drift detection v2 | TC-PEND-016, TC-PEND-021 |
| #25 Ensemble/stacking | TC-PEND-014 |
| #45 E2E Playwright CI | TC-PEND-023, TC-PEND-025 |
| #47 Dockerize | TC-PEND-024 |
| #50 Batch predictions | TC-PEND-026 |
| Feature Engineering enhancements | TC-PEND-001 to TC-PEND-007 |
| EDA export bugs | TC-BUG-001 to TC-BUG-011 |
| Architecture/microservices | TC-ARCH-001 to TC-ARCH-010 |

---

## Coverage Gaps

- Insurance model has no E2E coverage → TC-DOC-067
- K-Means clustering UI has no E2E coverage → TC-DOC-068
- SHAP bars: spinner alone should not count as pass → TC-DOC-069
- Error states (backend unreachable, empty form) partial → TC-DOC-071, TC-DOC-072
- No predict latency performance baseline → TC-DOC-073
- No contract test matching JS form fields to API schema → TC-DOC-074

## ✅ Closed (corrected) — Parts 158–172 (TC-P11)

Previously flagged as "no session logs exist at all." That was wrong: the
15 logs for this range exist under a different filename prefix
(`Conversation_...`, singular — not `Session_...`), which the original
`find`/`ls` search missed. All 15 were located and read in full; TC-P11.md
(99 TCs) now covers this range — RAG tiered retrieval/web override, drift
data versioning, EDA microservice deploy, and the entire Text-to-SQL Agent
build (guardrails, 4-engine DB support, ERD diagram, pagination, MSSQL,
NL filter, saved queries, the chart build-out-then-removal arc, follow-up
suggestions).

## ✅ Closed — Parts 201–249 (TC-P10)

Previously a major gap; now covered by TC-P10.md (93 TCs) — Document
Intelligence provider cascade, full Multimodal RAG architecture + MMRAG
backlog, CV forensics, Inpainting, Sharpen/Deblur, homepage redesign,
Adversarial Robustness Lab (attacks/defenses), Face Cloak, Style Cloak,
adversarial training defense, and the Part 248–249 sitewide theme sweep +
CI fix + theme toggle rollout. See TC-P10.md's own Coverage Note: Parts
201–243 TCs are derived from the aggregated technical-concept record for
that range rather than a fresh line-by-line re-read in this pass; Parts
244–249 TCs are derived from a direct full re-read.

**Next open range, if the project continues past Part 330**: Parts 1–330 are now
fully covered (TC-P12→TC-P19 closed Parts 250–330 on 2026-10-24). Any parts beyond
330 have no coverage yet — check `Conversations/` for new session logs before
assuming this index is current.
