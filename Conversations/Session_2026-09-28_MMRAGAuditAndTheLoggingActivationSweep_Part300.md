# Part 300 — MMRAG audit, thumbnail/temp cleanup, and the logging activation sweep

Continues [Part 299](Session_2026-09-27_HandbookRebuildAndClearingTheMMRAGBacklog_Part299.md).
2026-09-28. Verified the whole Multimodal RAG feature, finished two housekeeping
items, then planned and executed the client-side logging backlog from
`LOGGING_SPEC.md` — steps 1 through 4 — each shipped, mostly verified live.

Through-line: **check reality, not the plan.** Every "one shared component covers
all of it" assumption in the plan was wrong until grep proved it, and the coverage
audit itself over-counted until the code contradicted it. The wins this session
came from disbelieving the doc and reading the source.

---

## 1. MMRAG full feature audit — complete

Swept the whole Multimodal RAG feature (not just the backlog table):
- Backend: `mm_descreen` + `mm_meeting` imported and mounted in `app.py`; all four
  new routes (`/rag/mm-descreen`, `/rag/mm-meeting`, `/mm-meeting/ask`,
  `/mm-meeting/stream`) **serving live** on the Space; per-route 50 MB body cap in
  `security/body_size.py`. `py_compile` clean.
- **Live functional test** of descreen (free, no LLM): a realistic clean image →
  `removed=0`; the earlier synthetic ramp read 6 peaks (a tiled gradient has a real
  edge discontinuity — bad test input, not a bug).
- Frontend: 3 tools' full file sets, all <400 lines, cards + `toolNav` AREA_OF +
  thumbnails all present; **tsc 0 errors** repo-wide.
- Backlog: 17/18/21 shipped, 20 done, 19/22 + speaker-renaming dropped — closed.

## 2. Housekeeping

- **Thumbnails:** replaced the 3 shared stopgaps with real Pexels photos via
  `thumbnails.py add` (key read from `.env.local`, never printed) — business
  meeting / paper-print / abstract note. ml-portfolio `2171998`.
- **Temp clips:** cleared session test files + the gitignored `.playwright-mcp`
  dir (user asked, so approval was explicit).

## 3. Logging: the plan and the two docs

Read `docs/QA_AUTOMATION_AND_LOGGING_PLAN.md` + `LOGGING_SPEC.md`. Finding: the
**plumbing is complete** (events table, `/api/track`, `trackedFetch`,
`logEvents.ts` with 28 event names, `llm_calls`, `security_log`) — the gap is
per-tool **wiring**. Only ~7 of 28 event types were ever emitted.

Wrote it up: added `LOGGING_SPEC.md` **§12** (audit + plan summary) and a new
companion `docs/LOGGING_COVERAGE.md` (tool lists + step-by-step plan), condensing
§9/§11 to keep the spec at its 400-line limit. ML-Unified `f698d10`.

## 4. Step 1 — client-side run events (+ audit corrections)

Added `trackToolRun(id, meta)` to `useAnalytics.ts` and wired the client-side
tools that emitted no run event. **The audit over-counted and I caught it before
editing wrongly:**
- The first grep (scoped to `src/app/tools`, looking only for
  `trackedFetch`/`query_run`) reported **16**. Real gap was **11** —
  `feature-engineering`/`preprocessing` emit `run_success` directly, and `automl`
  is covered via the shared `AutoMLModal` (`trackedFetch`), all missed by the
  narrow grep.
- **`malicious-package-scanner` makes no network call** — the `fetch(` the grep
  matched was inside a *sample source-code string*. It's a pure client-side tool;
  only `password-audit` actually hits the network (HIBP k-anonymity).

Wiring choices: discrete tools log at their analyze/run moment; **live-as-you-type**
tools (phishing, malicious-package-scanner) **debounce** (1.2 s) so runs count per
settled edit, not per keystroke; `password-audit` logs a **content-free** run (no
password, and deliberately not the breach outcome either, to keep the privacy
page's "nothing you type is recorded" true); asl (webcam) logs one run per session
start; showcases (`pipeline-cinema`, `pose-vj-visuals`) skipped. ml-portfolio
`fcdd28e`, doc `dcdeaa0`. **Verified live:** `query_run` with `points:488` → 200.

## 5. Step 2 — `guide_open`

Plan assumed "one shared modal." Reality: **44 near-identical per-tool modal
copies**, no shared base. Chose minimal wiring (user's call): a
`useGuideOpenTracking(toolId, open)` hook + a one-line call in each modal, the tool
id hardcoded per file (no prop threading). 43 wired by script via the uniform
`if (!open) return null;` anchor; `text-to-sql`'s mount-when-open modal passes
`open={true}`. ml-portfolio `4c7e998`, doc `5ac07e5`. **Verified live:**
`guide_open` `{tool:"periodicity-finder"}` → 200.

## 6. Step 3 — `tool_card_click`

This time the shared component **did** exist: `ToolCard.tsx`, whose
`handleNavigate()` is the single click entry point for every path (body, title
button, "Try it"/"Launch") and has `cap.id`. One emit there covers all grids.
`{ tool, source, opens }` — `source` derived from the path. ml-portfolio
`1d2fadd`, doc `d26b626`. **Verified live:** `tool_card_click`
`{tool:"periodicity-finder",source:"category",opens:"here"}` → 200.

## 7. Step 4 — `citation_click` (`result_expand` N/A)

`RagSourceCard.tsx` (multimodal-rag only) — its click toggles the card open + selects;
emit `citation_click` **on open only**, `{ tool, index, kind }`, no cited text.
`result_expand` was checked and **not wired**: reconciliation has no expandable
rows, document-intelligence's only toggle is its export dropdown, and the citation
card is already `citation_click` — no interaction left to attach it to. ml-portfolio
`705c3a6`, doc `388c5bc`.

**Live verification inconclusive — and honestly so.** The first run rendered a
correct grounded answer ("45 kg", cited) + a clickable citation card, proving the
path — but the deploy hadn't propagated (old bundle, no emit). Every retry since
was blocked by the **Space going unstable**: 502 on `/health` and `/rag/mm-ingest`,
then "Error: Request failed" on the query. Backend infra, not the frontend change.
Stopped per two-failures-stop. To re-check tomorrow when the Space is settled.

---

## Key decisions

- **Minimal wiring over refactor for `guide_open`** (user's choice): a shared hook
  + one line per modal, not a 46-file consolidation into one shared modal. Ships
  the event without a risky rewrite; the consolidation is noted as optional later.
- **`password-audit` logs a content-free run**, dropping even the breach outcome —
  a derived fact about the typed password — so the privacy page stays true. No
  privacy-page change was needed for any of steps 1–4 (same categories as existing
  events; no new column, no content).
- **Don't force an event with no home.** `result_expand` and the two visual
  showcases got no emit because there's no meaningful interaction to attach one to.

## Lessons

- **The narrow grep lies.** Scoping coverage detection to a tool's own directory
  missed tools instrumented via direct `run_success` and via shared components
  (`AutoMLModal`). Always include every run-event signal AND check shared
  components before declaring a gap. The "16" was really 11.
- **A `fetch(` match can be sample data.** `malicious-package-scanner`'s "network
  call" was a string literal in its example. Read the match, don't count it.
- **"One shared component" is a claim to verify, not assume.** It was false for
  guide modals (44 copies), true for tool cards (`ToolCard`). Grep first; the
  approach differs completely between the two.
- **Vercel deploy lag is real and repeatable.** Every live check first hit the old
  bundle; a reload after ~1 min got the new one. Budget for it — don't conclude
  "the emit is broken" on the first miss.
- **Verify the emit at the network layer.** Reading the `/api/track` request body
  (type + meta) is the definitive check, and it caught unrelated `keepalive` pings
  that could be mistaken for the event.
- **The safety classifier can be transiently down.** Bash/MCP calls returned "no
  verdict (error)" for a stretch; read-only tools still worked, and it recovered.
  Recommended waiting over routing around it or spawning an agent that would hit
  the same gate.
- **Stop at two backend failures and find the cause.** The citation_click live
  check hit 502s; the console named the root cause (Space down), so the honest
  call was to stop and defer, not keep hammering a struggling backend.

---

## Commits

| Repo | Commits |
|---|---|
| ml-portfolio | `2171998` (thumbnails) · `fcdd28e` (step 1 run events) · `4c7e998` (step 2 guide_open) · `1d2fadd` (step 3 tool_card_click) · `705c3a6` (step 4 citation_click) |
| ML-Unified (docs) | `f698d10` (logging audit + COVERAGE) · `dcdeaa0` (step 1) · `5ac07e5` (step 2) · `d26b626` (step 3) · `388c5bc` (step 4) |

All frontend/docs only — no backend changes, so no HF upload this session.

---

## State after this session

- **Logging plan: steps 1–4 done.** Client-side run events, `guide_open`,
  `tool_card_click`, `citation_click` all shipped; steps 1–3 verified live, step 4
  pending a stable Space (check tomorrow). Remaining vocabulary: `sample_load`,
  `paste_input`, `run_retry`, `scroll_depth` (steps 5–6). `result_expand` is N/A.
- **MMRAG feature: audited complete and serving live.**
- Optional follow-ups noted in `LOGGING_COVERAGE.md`: platform-world guide modals
  (`WorldUserGuideModal`, `/qa`) not wired for `guide_open`; `ProjectCard` not
  wired for card clicks.
