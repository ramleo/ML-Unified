# Part 326 — LLM-metrics redesign + Q3 M2 chatbot builder (web search, autocomplete) (2026-10-21)

Continues Part 325 (Q4 eval dashboard full build). Two big threads this day:
(1) a full visual redesign of the owner `/eval` LLM-metrics section, and (2) Q3 M2 —
the multi-tenant **chatbot builder** (owner UI) plus web search, citations, markdown
answers, and autocomplete (chips + dropdown + ghost text). Frontend = ml-portfolio;
backend = HF Space `wram1708/ml-unified`.

## LLM metrics (/eval) — redesigned on one validated chart system
- New shared `src/app/eval/charts/` module: `format.ts` (tokens + formatters),
  `useMeasure.ts`, `Tooltip.tsx`, `Panel.tsx`, `Bars.tsx`, `LineChart.tsx`,
  `ColumnChart.tsx`. Every panel rebuilt against it so the whole section reads as one
  system (Panel chrome + hover "i" info dots, measured SVG charts with real axes +
  hover crosshair, period-delta chips).
- **Validated palette keyed to the SITE's theme mechanism, not `prefers-color-scheme`.**
  The site themes via `html.light` (default dark). My first cut keyed tokens off the
  media query → charts mismatched the page; caught in a local preview and fixed. Steps
  validated with the dataviz skill's `validate_palette.js` for both surfaces.
- Fixes driven by owner feedback: **RowBars-style pill bars** (row IS the bar — label
  inside, value right, tinted fill; matches the site's `AnalyticsBars`), **x-axis date
  labels** on calls/trend charts, a clear **budget bar** (`$0 … budget $10`, visible
  "proj" marker), ambiguous **model-comparison Lines** now titled "Pass rate across
  runs" with a % axis, **per-item results** table with Pass/Fail chips + SVG C/F/R +
  groundedness meter. Progress bar moved directly under the Answer-quality header.
- In-dashboard **guide** expanded from descriptive to interpretive (How-to-read,
  defs for RAG + golden set, budget marker, "Watch for" cues).
- Commits ml-portfolio: `ae9e46c` (redesign), `3f44aae` (progress-bar placement),
  `0c25f11` (free Groq models in the eval picker), `37e60f7` (guide).
- **Judge model `gemini-2.5-flash` → `gemini-3.6-flash`** (ML-Unified `7517239` +HF):
  the judge was pinned to an older model while the app moved to 3.6. New runs aren't
  directly comparable to older 2.5-graded ones (expected when the grader changes).
- **Free Groq models** added to the eval generation picker (`openai/gpt-oss-20b` /
  `-120b`) — Groq already wired, no new integration (`0c25f11`).

## Q3 M2 — multi-tenant chatbot builder (owner UI)
Design choice **Option A**: owner-managed but **platform-ready** — everything scoped on
`owner_id`, so flipping to self-serve later (M3/M4) is a gate change, not a rewrite.
- **M2a** (config + management): `tenants.config` = persona/provider/model/greeting;
  config-aware `/internal/tenant/answer` (any allowlisted provider via `complete()`,
  grounding enforced on top, tagged `tenant-chat`); new `PATCH`/`DELETE /api/tenants/[id]`
  and `GET`/`DELETE /api/tenants/[id]/sources`; `src/lib/tenant/config.ts` allowlist +
  `sanitizeConfig`. Commits ml-portfolio `bdc7942`, ML-Unified `1957de2` (+HF).
- **M2b** (builder UI): owner page `/portfolio/chatbots` — create/delete bots + per-bot
  **Configure / Knowledge (paste docs, list/remove sources) / Test (chat against its
  KB)**. Profile-menu "Chatbots" entry. Commit `36e7161`.

## Chatbot capabilities added (same day)
- **Web search + citations** (per-bot toggle, default off for cost): the Space runs
  `web_search_fallback` (Tavily→DDG), merges results, returns source URLs; grounding
  tells the bot to cite. `{{CURRENT_DATE/MONTH_YEAR/FY}}` templating; **deterministic
  refusal** when no KB match and no web result (no LLM call = no hallucinated answer or
  fake sources); prompt cap raised 2000→**16000**. Commits `b6b322d`, `1dbe89d` (+HF).
- **`has_kb` fix:** no-KB bots answer from web only and never claim a KB was searched;
  the "couldn't find in the KB" wording appears only when a KB is attached.
- **Markdown answers** (`ChatMarkdown` via react-markdown + remark-gfm) so `**bold**` /
  lists / links render instead of raw asterisks.
- **Autocomplete** (two separate owner toggles so cost is opt-in):
  - **Auto-suggestions** (cheap, default on): KB-derived — or **persona-derived when the
    bot has no KB** — starter **chips** + a matching **dropdown**. `/internal/tenant/suggest`.
  - **Smart completion** (LLM, default off): inline grey **ghost-text** prediction
    (Tab/→ accept, Esc dismiss), debounced; `/internal/tenant/complete`. Stops after
    terminal punctuation; dropdown dismisses on Esc/blur.
- **Copy button** + selectable text on every chat message.
- Commits ml-portfolio `c4a259a`, `1de5283`, `a39e8d8`, `6b86cb9`;
  ML-Unified `9ab000b`, `817d161`, `75c71aa` (+HF each).

## The provider-outage bug + fix (key lesson)
A 502 "generation failed" appeared on a tenant bot. Error made informative (`75c71aa`)
→ it named `cohere/command-a-03-2025 returned no output`. Then chips/dropdown/ghost went
blank too — root cause: **the answer, suggestions, and completion all hard-depended on a
single provider (Cohere by default); when Cohere rate-limited, everything went dark.**
Fix (`1a15597` +HF): a **`_generate()` provider fallback** (primary → others) on all
three paths, mirroring the main RAG's cascade; the response reports the provider used.
Switching the bot to Gemini confirmed the diagnosis mid-way. **Lesson: any per-tenant
LLM path needs provider fallback, not a single hard dependency.**

## Vercel lag incident (not a bug)
A push appeared not to deploy; an empty re-trigger commit was pushed (`e1c9668`).
Real cause: **Vercel can lag ~15–20 min showing a deployment** — it was never
disconnected (the "no Git tab" worry was a false alarm; the deploy landed late). Also
hit a **GitHub stuck `doc-coverage` check-run** (job steps all succeeded, run = success,
but the check stayed `in_progress`) — a GitHub glitch; `gh run rerun <run> --job <id>`
cleared it. Don't conflate Vercel latency / GitHub check glitches with deploy failures.

## Docs / memory
- PRD `docs/prd/05-roadmap-extensions.md` (local-only): Q3 → M1+M2 shipped; eval
  "Polish 2026-10-21" note.
- Memory: [[project_platform_roadmap]] (Q3 M1+M2), [[project_autocomplete_idea]] (new —
  autocomplete rollout to the rest of the site is pending).

## State of the roadmap
Q5 ✅ · Q1 ✅ · Q2 🚧 M1 · Q4 🚧 M1+M2 (+ redesign, free Groq models, 3.6 judge;
M3 online judge-scoring remains) · **Q3 🚧 M1+M2** (builder + web search + autocomplete;
**M3 embed widget → M4 billing/self-serve remain**). Also pending: autocomplete across
the rest of the site.
