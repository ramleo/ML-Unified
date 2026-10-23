# Part 328 — Q2 M2: MCP expanded surface (tools + resources + prompts) (2026-10-23)

Continues Part 327. Picked up the roadmap **in sequence** (Q5✅→Q1✅→Q2→Q4✅→Q3✅):
the next unfinished item was **Q2 (MCP)**, which had only M1 shipped. This day shipped
**Q2 M2** — grew the MCP server from a 3-tool stub to a real surface (6 tools +
resources + prompts) — and verified it live against the Space with an authenticated
`tools/list`. Frontend = ml-portfolio (Vercel); backend = HF Space `wram1708/ml-unified`.

## What shipped (Q2 M2)
- **Tools: 3 → 6.** Kept the M1 three (tls-headers, email-auth, anomaly) and added:
  - **attack_surface_check** — passive recon of a host (deterministic, no LLM spend).
  - **yara_malware_scan** — bundled-YARA signature scan of base64 file content (no LLM).
  - **prompt_injection_check** — heuristic + free-tier Cohere/Mistral judge, **with a
    heuristic fallback** so it still returns a verdict if no provider answers.
  Each calls the same tested first-party logic — no second implementation.
- **Resources (read-only context):** `airaml://tools` (the tool catalog) and
  `airaml://handbook` + template `airaml://handbook/{section}` (the handbook, already
  in the RAG KB, readable section-by-section; the section is resolved against the real
  file listing, so `..`/slash input can't escape the directory).
- **Prompts:** `scan-host`, `check-email-headers`, `check-untrusted-text`.
- **Docs:** PRD Q2 → M1+M2 (local-only); handbook "Public API & MCP" chapter updated
  (it had said MCP exposes "the same tools" as REST — now notes the extra tools +
  resources + prompts); RAG KB section `09-public-api-amp-mcp.md` re-synced.

## Curation decision (the hard part of MCP)
Expose high-value, low-risk tools, not all 136 endpoints. In the `/v1` "cheap, no
provider spend" spirit:
- **In:** the two deterministic no-LLM tools (attack-surface, yara) + prompt-injection
  (genuinely useful for an AI client screening untrusted text; has a non-LLM fallback).
- **Out:** **ai-code-detector** and **siem-triage** (LLM-only, no fallback — lower value,
  every call spends) and **intrusion-detection** (needs bulky inline `train_X`/`train_y`/
  `test_X` matrices — awkward to pass over an MCP tool call; the anomaly tool already
  covers the "numeric security rows" case).

## Lessons
- **Name the package `mcp_ext/`, never `mcp/`.** To stay under the file-length limit the
  tools/resources/prompts/auth were split out of `mcp_server.py` (72 → 28 lines) into a
  package. A package literally named `mcp/` would **shadow the installed `mcp` SDK** that
  FastMCP imports internally → import breakage at startup. Used `mcp_ext/` and registered
  everything via `register_tools(mcp)` / `register_resources(mcp)` / `register_prompts(mcp)`
  taking the FastMCP instance. Dockerfile needed `COPY mcp_ext/ mcp_ext/` or the Space
  build would omit it and crash on `from mcp_ext import …`.
- **Rule-5 slip (batch deploys).** The HF upload ran as **4 separate commits** (3
  `upload_file` + 1 `upload_folder`) instead of one. It debounced into a single healthy
  RUNNING rebuild, so no harm — but next backend deploy should use a single
  `create_commit` with multiple operations = one commit, one rebuild.
- **The authed `tools/list` is the only check that proves the live tool COUNT.** `/mcp`
  returning 401 (not 404/502) + `/` 200 + Space RUNNING proves the app booted with
  `mcp_ext` imported (the real deploy risk), but NOT that 6 (vs the old 3) are served.
  Confirmed with `scripts/mcp_list.py` (a FastMCP `Client` over Streamable HTTP with the
  key as a Bearer header) → `TOOLS (6)`. Needs a real `ak_live_` key, so it can't be run
  from CI/locally without one.

## Deferred
- **Q2 M3 — OAuth 2.1 + PKCE + Protected Resource Metadata.** The standards answer for
  public remote MCP servers (and what Claude Desktop's native "Add connector" UI expects).
  Demand-gated, same logic as Q3 M4c reseller — the key-Bearer stopgap is enough until an
  outside party wants to connect their own AI client. (For a self-demo, the key works today
  in **Claude Code** via `claude mcp add --transport http … -H "Authorization: Bearer …"`
  and in **Cursor**; Claude Desktop needs the `mcp-remote` bridge because of the key auth.)

## Commits / deploy
- ML-Unified **4d18b21** — `feat(mcp): Q2 M2 …` — CI green; HF Space rebuilt, RUNNING.
- ml-portfolio **81d5e29** — `docs(handbook): note MCP's expanded surface …` — CI green.
- HF upload: `mcp_server.py`, `mcp_ext/`, `Dockerfile`, KB `09-public-api-amp-mcp.md`.
- Live verification: authed `tools/list` → 6 tools / 2 resources / 1 template / 3 prompts.

## Follow-up — Groq fallbacks & document cost-guard (same day)
Demoing the new MCP tools surfaced a reliability/cost gap: the LLM-judge tools
no-op'd when Cohere+Mistral free tiers both 429'd, and the Nightly `document-goldens`
job FAILED because document extraction fell through to **paid Gemini** when free
providers were throttled (29/29 values still correct — the "failure" is a fall-to-paid
cost guard). Added a free **Groq** attempt in each place, before the paid key:

- **Judge tools (`e1a5558`, +HF):** `prompt_injection_check`, `siem_triage`,
  `ai_code_detector` now try cohere → mistral → **groq (`openai/gpt-oss-120b`)**. Groq
  is free on a SEPARATE rate-limit pool, so it runs when the other two throttle. Cohere
  stays primary (fallback added, not swapped). Also fixed a misleading judge log
  (`625b5ef`, +HF): empty output from a 429 was logged as "unparseable" — now "no output
  (provider unavailable or rate-limited)".
- **Document text cascade (`d29c310`, +HF; test fix `8213457`):**
  `routers/document/_llm.py` cohere → **groq (`gpt-oss-120b`)** → gemini. Strictly safe
  (groq only after cohere fails; still falls to gemini if groq fails). The change broke
  `test_provider_cascade.py` (hard-coded old order) — CI caught it, tests updated.
- **Document vision cascade (`bbaa457`, +HF):** `routers/document/_vision.py` **groq
  (`qwen/qwen3.8-27b`, Groq's only vision model)** → gemini. NOT strictly safe like text:
  a hallucinating vision model returns confident-but-wrong output used instead of Gemini
  (qwen3.6 caused EC-007). Shipped qwen-first on the newer 3.8 (user chose "option B"),
  leaning on the nightly goldens to catch regressions — watch the next nightly.

**Lessons:**
- **Read your own provider memory before choosing a Groq model.** First picked
  `llama-3.3-70b-versatile` for the judge fallback — which `project_llm_provider_status`
  already listed as retired since 2026-09-07. gpt-oss-120b (8k TPM, text, non-reasoning)
  is the current free Groq text model; qwen3.8-27b is the only vision one.
- **A "fallback" is only strictly safe when every provider is interchangeable in
  QUALITY.** For text that holds; for vision it does not (a wrong-but-non-empty answer is
  used), so qwen-first trades cost for an accuracy risk — a deliberate, user-approved call.
- **Not witnessed firing:** Cohere stayed healthy, so the Groq *judge* path hasn't been
  seen serving live yet; it fires only when cohere+mistral both throttle.
- HF deploys: the first (MCP) upload went as 4 commits; the later ones used a single
  `create_commit` per rule 5.

## State of the roadmap
Q5 ✅ · Q1 ✅ · **Q2 🚧 M1+M2** (only M3 OAuth deferred) · Q4 ✅ · Q3 ✅ (M4c deferred).
Remaining non-deferred: **autocomplete site-wide**. Owner still owes the one manual step
`supabase/eval_online.sql` (the /eval "Online quality" section stays empty until then).
