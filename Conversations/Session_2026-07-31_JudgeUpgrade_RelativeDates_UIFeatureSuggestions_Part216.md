# Session Part 216 — 2026-07-31

## Context
Direct continuation of Part 215's open thread: two proposed zero-cost
improvements to the reconciliation feature were awaiting the user's choice.
User said "do both."

## 1. Judge model upgrade

`contradictions.py::_JUDGE_MODEL` swapped from `llama-3.1-8b-instant` to
`llama-3.3-70b-versatile` — same free Groq API key already used elsewhere in
the app for main chat answers, so no added cost, just more of the shared
free-tier rate-limit budget and slower per-call latency. This is the single
constant used by both `/rag/contradictions` (MMRAG-02) and
`/rag/reconciliation` (MMRAG-20), so both endpoints benefit.

## 2. Relative-date entity extraction

`entities.py::_DATE_RE` extended to also match relative payment/date terms —
`net-30`, `Net 45`, `30 days`, `45 days` — previously only calendar-style
dates (MM/DD/YYYY, "Month DD, YYYY", ISO) were recognized, so the
entity-based candidate-prioritization logic added for MMRAG-20 was blind to
exactly the kind of term contracts/invoices actually use, and only ever
worked for money mismatches.

Verified locally with 7 test strings (`net-30`, `Net 45`, `30 days`,
`45 days from issue`, money, no-match, and a `3-5 days` range) — all matched
correctly, no false positives on plain prose.

## Deploy and live verification

Both changes are in one commit (`e8e560f`, ML-Unified) — pushed to GitHub,
then both `.py` files uploaded to the HF Space per the mandatory-upload
rule. Waited for the Space to report `RUNNING`, then did a real end-to-end
verification rather than trusting the status flag alone:

- Ingested a fresh contract (`$50,000`, "30 days of invoice date"), a
  matching invoice ("Due date: 30 days from issue" — same term, different
  wording, the exact phrasing that produced the Part 215 false positive),
  and a genuinely mismatched invoice (`$52,500`, "45 days").
- Ingest response confirmed the new regex is live: contract chunk's
  `entity_types` included `"date"` for the "30 days" phrase.
- `POST /rag/reconciliation` against both invoices returned exactly ONE
  discrepancy — the genuine `$52,500`/45-days mismatch, `confirmed: true` —
  and did NOT flag the paraphrased-but-matching invoice. This is a direct,
  live confirmation that both changes fixed the exact bug reported at the
  end of Part 215, not just an offline unit test.

Scratch fixture PDFs cleaned up after the test.

## Closing discussion — UI/feature/existing-feature suggestions (not built)

User asked three explore-only questions ("is there anything to improve UI
wise? / add as a feature? / improve in an existing feature?") and asked to
search the web for current best practice before answering. Combined web
research (2026 RAG UX/streaming-citation best practices, 2026 agentic-RAG
architecture trends) with direct code review — findings grounded in actual
gaps found in the repo, not generic advice:

**UI gaps found:**
1. `useRagChat.ts` streams via SSE but has no `AbortController` anywhere —
   no way to cancel a bad/slow answer mid-stream.
2. Citations are click-only (`CitationThumbnailPanel.tsx`) — no hover
   preview of the cited passage before clicking.
3. No answer feedback capture (👍/👎) anywhere in `ChatPanel.tsx`.
4. No ARIA live region on the streaming answer — a screen reader gets
   nothing until the full answer has arrived.

**New-feature ideas (checked against what already exists first):**
- Confirmed hybrid search + reranking (BM25 + dense + RRF) already exists
  (`rerank.py`, `retrieve.py`) — correctly did NOT suggest it as new.
- Real gap found: `query.py` already computes `groundedness` via
  `score_groundedness()` after every answer (MMRAG-12), but only surfaces it
  as a "Low confidence" badge — never acts on it. The 2026 agentic-RAG
  pattern of auto-retrying retrieval with a rewritten query when groundedness
  comes back low is not implemented; this would reuse an already-computed
  score rather than add new infrastructure.
- Citation click currently only shows a cropped thumbnail; suggested
  scroll-and-highlight into the actual source document as the more modern
  pattern.

**Existing-feature improvement:**
- The groundedness → self-correction loop (same item above) was flagged as
  highest-leverage: reuses existing code, minimal added cost (one retry pass
  only on the rare low-confidence case).
- Suggested watching whether the reconciliation confirmation pass's
  `confirmed: false` rate drops now that the judge model is stronger — if it
  goes near-zero after real usage, the second LLM call may no longer be
  worth the extra latency.

None of the three suggestion categories were implemented — presented as
options, explicitly not acted on, per the "exploratory question" pattern the
user has used consistently across MMRAG-17/18/19/20/21 discussions.

## Commit summary

| Repo | Commit | What |
|---|---|---|
| ML-Unified | `e8e560f` | Judge model upgrade (70b) + relative-date entity regex, both verified live |

## Pending / next candidates
- Streaming stop/cancel button, citation hover-preview, answer thumbs
  feedback, ARIA live region on streamed answers — all proposed, none built.
- Groundedness-triggered re-retrieval loop — proposed, considered
  highest-leverage, not built.
- Citation click → scroll-and-highlight in source document (vs. current
  cropped-thumbnail-only view) — proposed, not built.
- Whether the reconciliation confirmation pass is still needed post-model-
  upgrade — open question, needs real-usage data over time, not a code task
  yet.
- MMRAG-21 (Meeting/Call Intelligence pivot) — still considered, not chosen.
- MMRAG-11's cut-detection branch and MMRAG-14's real-chart accuracy remain
  unverified against real (non-synthetic) inputs — carried over, still open.
