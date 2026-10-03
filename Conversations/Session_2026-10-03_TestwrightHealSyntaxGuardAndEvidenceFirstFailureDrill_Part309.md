# Part 309 — Testwright: a model typo that failed the whole spec, and drilling run failures to their real cause

Continues [Part 308](Session_2026-10-03_TestwrightMeasureFirstDurableDashboardAndGroundingFixes_Part308.md).
2026-10-03. The user ran "Suggest a fix" and got a compile error; separately challenged the
dashboard and the earlier run failures ("you are reckless"). This arc split every complaint into
its real cause with live evidence, shipped a provider-independent robustness fix, and cleaned up
the dashboard — then drilled the last two unexplained failures to their roots.

Through-line: **separate a syntax failure (broken writing the computer can't parse) from a logic
failure (parses fine, checks the wrong thing); fix the first with a deterministic law, and diagnose
the second with evidence before touching anything.** And: **validate model output before handing it
to a runner — one typo should never fail the whole spec.**

---

## Arc 1 — "Suggest a fix" shipped code that wouldn't compile (`918103b`, HF)
The heal output contained `getByRole('searchbox', { name. 'Search…' })` — a **period where a colon
belongs**. The runner reported the opaque **"No tests found"** because a single bad line fails the
WHOLE spec at parse time. Root cause, confirmed by reading the code:
- Heal (and Author) shipped the model's code after only `_looks_like_test` (imports `@playwright/test`
  + contains `test(`) and some locator cleanups. **Nothing validated the code parses.**
- Worse, the cleanups all key off a well-formed `name:` (`_GETBYROLE_NAME`), so the `name.` line
  didn't even match them — it couldn't be caught *or* fixed, and shipped verbatim.

Fix (provider-independent, the durable one):
- `locators.sanitize_option_punctuation` — repairs `{ <key>. <literal> }` → `{ <key>: <literal> }`
  for known option keys (name/exact/hasText/level/…), only when followed by a literal value, so a
  real method chain (`page.getByRole`) is never touched. Runs in **both** Author and Heal, FIRST,
  so the name-based transforms then see a well-formed locator.
- `validate.looks_syntactically_valid` (NEW `validate.py`) — a cheap structural gate: defines a
  `test(`, no leftover option-key-dot, and balanced `(){}[]` scanning OUTSIDE strings/comments.
  Heal and Author now **fall through to the next provider** instead of shipping a zero-test spec.
- Verified with 10/10 deterministic unit checks, including the exact broken line: invalid → repaired
  → valid; valid code untouched; unbalanced/prose rejected. Live: HF full rebuild to RUNNING + QA
  endpoint 200 (which also proves the new module imports cleanly).

**Decision — do NOT swap Heal to the paid Gemini.** The user asked to try Gemini. But `config.py`
excludes it on purpose: it is the only PAID key and the QA endpoints are PUBLIC, so every visitor's
"Suggest a fix" would bill credits. And a different model would not fix the CLASS — any model can
typo. So we fixed the validation, kept the free cascade, and parked the Gemini comparison.
[[project_llm_provider_status]] [[feedback_no_unilateral_provider_swaps]] [[feedback_billed_api_testing]]

## Arc 2 — "you are reckless": the run reds were the tests' own wrong assertions, not my commits
Checked the LIVE app before answering, because the accusation deserved evidence not a defense. None
of the three earlier commits (visible-headings, misread-name repair, href tiers) turned a green test
red — they change how locators are GROUNDED; these reds are the auto-generated tests asserting things
that don't match the site. Each cause, verified live:
- **ML Unified Platform → HF Space.** The real "ML Unified Platform" link opens in a **new tab**
  (`target="_blank"`). A same-tab `toHaveURL(hf.space)` can NEVER pass — it needs popup capture.
- **search malware → `/tools/security-trust` visible.** That category link exists on the homepage
  AT REST but **disappears the moment you type** (search swaps the grid for filtered results). The
  test asserts a resting-state element while in searched state.

## Arc 3 — the dashboard complaints, each with its real cause (`c371fe7`)
- **6 proposed, 5 drafted (Q1):** correct behavior — the 6th (Contact Form) returned no test because
  the page has no form to ground. Fix: the UI now SAYS why ("no groundable element, skipped") instead
  of a silent "No test returned".
- **Red tests labelled "Untitled test" (Q3):** the Tests view fell back to the RUN name when per-test
  titles weren't recorded (durable "All runs" rows + older local runs), and an unnamed run's name is
  itself "Untitled test" → every bar read "Untitled test · Untitled test". Fix: number tests within a
  run (`Test 1, Test 2…`); the real run name still shows as context. Verified live (0 duplicates).
- **Same Top-Failing / Flaky on every bar (Q4):** by design — those are history-wide aggregates
  (flakiness only exists across runs); only the outcome strip drills into one run. The layout implied
  otherwise. Fix: caption them "across all runs in view — not the selected bar". Verified live.

## Arc 4 — Q2 generation rules: best-effort advice, not a law
Added grounding help (`prompts.py`) + `[newtab]` link-map marker (`discover.py`): new-tab links use
popup capture, and don't assert a resting element after a search. **These are heuristics** — prompt
advice the model usually follows but cannot be guaranteed to, unlike the sanitizer/guard which are
deterministic. Framed to the user as laws (always work) vs advice (usually work); the syntax guard +
Heal are the safety net when the advice doesn't land.

## Arc 5 — drilling the last two timeouts to their real cause (diagnosis only, no code yet)
Both are LOGIC failures (wrong assumptions about the site), not syntax, not my changes:
- **Security & Trust → Computer Vision (31s timeout).** On `/tools/security-trust`, "Computer Vision"
  is a **filter BUTTON** (filters tools on the same page), not a nav link — there is no link to
  Computer Vision there at all. The test waited for a link that doesn't exist. You reach Computer
  Vision from the homepage, not from inside another category page.
- **handbook → download PDF (34s timeout).** "PDF for print (A4)" opens the browser's **print
  dialog** (print-to-PDF) — it never downloads a file; only "Download Markdown" fires a real download
  event. The test waited for a download that never happens.

## Key decisions / lessons
- **Validate before the runner.** Model output is untrusted text; a parse-guard + a targeted
  punctuation repair stop one typo from failing an entire spec with a misleading "No tests found".
- **Fix the class, not the provider.** Swapping to a paid model would have masked one typo while
  adding cost and bypassing the public-endpoint design. The validation fix is provider-independent.
- **Syntax vs logic.** A deterministic law handles the first; evidence-first live investigation
  handles the second. Never attribute a red to "my change" (or excuse it) without looking.
- **Laws vs advice.** Be explicit with the user about which fixes are guaranteed (code I run) and
  which are heuristics (advice to the model).

## Open / deferred — TOMORROW
- **Two more grounding rules** (the user said "we will do it tomorrow"): (1) a control that is a
  BUTTON, not a link, won't navigate — don't expect it to; (2) a "PDF for print"/print button opens
  the print dialog, so don't `waitForEvent('download')` on it — only a "Download…" button does.
- **Gemini comparison** ("we will test with gemini model as well"): a one-off, off-line comparison of
  heal/author output quality vs the free cascade — NOT wiring the paid key into the public endpoints.
- Still parked: Learn-from-edits Phase 1 (needs real `test_edited` data); R5 authenticated testing
  (needs a login-gated app).

## Commits
| Repo | Commits |
|---|---|
| ml-portfolio | `c371fe7` (dashboard: numbered test labels, history-wide captions, skip reason) |
| ML-Unified (backend, HF) | `918103b` (sanitizer + syntax guard + new-tab/search grounding; new `validate.py`) |

Related: [[project_testwright_run_perf]], [[project_testwright_qa_platform]],
[[feedback_status_claims_need_evidence]], [[feedback_debug_first]], [[feedback_document_only_when_needed]].
