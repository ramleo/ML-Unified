# Session Part 219 — 2026-08-01 → 2026-08-02

## Context
Direct continuation of Part 218. User asked to research and design a "state
of the art" UI for Multimodal RAG, then iterate on it, then bring it into
the real app — a much longer arc than a typical session, with several
rounds of visual disagreement and correction along the way.

## Mockup phase (Artifact, not real code)

Researched current AI-chat/RAG UI conventions (Perplexity/Claude-style
inline citations, source strips, confidence indicators) via web search,
then designed and published a static mockup — "Evidence Desk" — as a
Claude.ai Artifact: a 3-column concept (document tray / chat / evidence
panel), ink-and-brass palette, serif display type for questions, numbered
citation chips with hover-linking to matching evidence cards. Iterated once
on user request ("iterate on the direction" → "move forward with it"),
adding the citation-hover-linking interaction, entrance animation, and
per-fact citation mapping.

User then asked to bring this into the real `multimodal-rag` tool
(ml-portfolio), "with constellation background."

## Real implementation — layout restructure

Scope grew across many turns; final architecture:

- **`DocumentTray.tsx`** (new) — vertical left-column doc list (icon, name,
  page/frame count), replacing the old horizontal chip row for this
  purpose. Also now hosts `IngestProgressRail` directly (new `bare` prop —
  skips its own bordered wrapper) so there's exactly **one** "add a
  document" entry point instead of two (a real bug the user caught: the
  first pass had both a tray dropzone AND the old full-width ingest bar).
- **`EvidencePanel.tsx`** (new) — the ranked citation list + groundedness,
  split out of `ChatPanel.tsx` so it renders as its own column. Groundedness
  was later moved back OUT of here per user feedback (see below).
- **`EvidenceColumn.tsx`** (new) — wraps `EvidencePanel` + the existing
  citation-thumbnail/page-rail preview into one column; de-duplicates what
  had become two copies of this block (normal view + shared view) and
  houses `matchObjectsToQuestion`/`HIERARCHY_SYNONYMS` (moved from
  `MmRagRunner.tsx`).
- **`MmRagRunner.tsx`** — rebuilt the 2-column grid into 3 columns (tray /
  chat / evidence), with `DocumentChipsRow` reduced to filters+share only
  (`showDocuments={false}`) since the tray now owns the doc list.
- **`RagSourceFlags.tsx`** (new) — the warning-badge + entity-chip block
  extracted out of `RagSourceCard.tsx` to stay under the file-length limit
  after rebuilding its expanded-card content (quote-highlight block,
  always-visible Retrieval/Rerank-score-bar/Used-in-answer rows, replacing
  a hidden-behind-a-toggle text dump).
- **`GroundednessBadge.tsx`** — restyled to a pill with a colored dot
  ("Grounded · 87%") instead of "high (87%)"; still shared with
  `ChatMessageList`/`ToolsAIChat`.

Several rounds of live Playwright verification (upload `test_invoice.pdf`,
ask a real question against the deployed HF Space backend) caught real
problems along the way, each fixed in turn:

1. **Layout height mismatch** — columns ending at wildly different heights
   (tray short, chat/evidence taller). First attempt (`items-stretch` on
   just the tray) just relocated the empty space instead of removing it.
   Root cause: the mockup is a fixed-`100vh` app shell with internally-
   scrolling panels; the real page was a normal content-sized-card layout.
   Fixed properly: grid given `lg:h-[75vh]`, each column (`DocumentTray`,
   `ChatPanel`, `EvidenceColumn`) rebuilt as a real flex column —
   header/composer `shrink-0`, content area `flex-1 min-h-0 overflow-y-auto`
   — removing the old `maxHeight: 480` caps that had been silently limiting
   growth.
2. **Accent color** — brass/gold was tried (matching the mockup exactly)
   then reverted to the site's original purple (`#a78bfa`) per explicit
   user correction — constellation background was kept throughout via the
   existing translucent card style.
3. **Composer redesign** — rectangular textarea + text button → rounded
   pill input + circular arrow send button + "↵ to ask" hint row, matching
   the mockup.
4. **Font sizes** — went through several explicit rounds at the user's
   direction: question/answer bumped up (13/11px → 19/15px → 22/17px on a
   "increase more" instruction), then reduced back down twice more per live
   feedback, settling at **15px question / 13.5px answer**. Separately, a
   whole pass of small UI labels (`text-[8px]`/`text-[9px]` uppercase
   labels, evidence-card text, tray text, filter chips, Share-session
   panel) were bumped roughly +2px each after the user pointed out the
   *non-chat* UI text was too small — including one label (`Concise/
   Normal/Detailed`) that was initially missed because it lived in
   `MmRagRunner.tsx`, not `ChatPanel.tsx` where the rest of the sweep
   happened; caught by the user in a side-by-side screenshot and fixed.
5. **Question/answer alignment** — changed from a right-floating "chat
   bubble" pair (`self-end`/`self-start` with `max-w-%`) to both left-
   aligned, full width, per explicit instruction ("make chat left
   aligned"); feedback thumbs kept right-aligned via `justify-between`.
6. **Groundedness placement** — moved from the Evidence panel (where it
   had landed during the initial split) back to inline under each answer
   bubble, next to the feedback thumbs, matching the mockup's per-turn
   layout — this was the point of "see the design of chatbox... its in
   ss."

## Explicitly declined / deferred

- **Brass/gold palette** — tried, then explicitly reverted to purple.
- **Inline numbered citation markers inside the answer text** (the
  mockup's signature hover-link interaction) — would require a backend
  prompt change in `citations.py` (currently instructed to never emit
  citation markers) plus a new redeploy/verification cycle. Framed to the
  user as "Option 2" against the lower-risk "Option 1" (frontend-only,
  numbered cards in the sidebar but not inline); user chose Option 1.
  Still an open, undone item if ever revisited.
- **Minimal single-row top bar** (mockup's "Answer length / Restrict to
  uploads / theme toggle" bar) — not built as a page-level bar; the site's
  existing header (Back/title/User Guide/Usage stats) was kept, with just
  the Concise/Normal/Detailed control moved up above the grid. "Restrict
  to uploads" was not added as a UI toggle since it isn't actually a
  user-facing option in this tool (hardcoded on) — explicitly declined
  building a fake/non-functional control.

## Verification

Every step this session was checked with `tsc --noEmit` (clean throughout)
and `wc -l` against the project's 400-line cap (all touched/new files
comfortably under it: `MmRagRunner.tsx` 281, `RagSourceCard.tsx` 346,
`ChatPanel.tsx` ~205, `DocumentTray.tsx`/`EvidenceColumn.tsx`/
`EvidencePanel.tsx` all under 110). Live-verified repeatedly via Playwright
against the deployed HF Space backend (`test_invoice.pdf` upload + a real
question), not just visual mockup comparison — including one live
computed-style check (`getComputedStyle` via `browser_evaluate`) to settle
a dispute about whether the answer text had accidentally inherited the
question's serif font (it hadn't — confirmed `Geist` vs `ui-serif` render
correctly at the DOM level, the apparent mismatch was a screenshot
compression artifact).

## Status: NOT committed/pushed

All of this segment's changes are still local/uncommitted in `ml-portfolio`
(`git status` shows 8 modified + 4 new files). Unlike prior sessions, no
commit or HF/Vercel deploy happened this segment — the user was iterating
on visual/layout details live via `next dev` against the deployed backend,
not shipping. Next step, if the user wants to ship this: review the diff,
commit, and push (Vercel auto-deploys `ml-portfolio` on push to main).

## Files touched (this segment)

**New**: `DocumentTray.tsx`, `EvidenceColumn.tsx`, `EvidencePanel.tsx`,
`RagSourceFlags.tsx`.
**Modified**: `ChatPanel.tsx`, `DocumentChipsRow.tsx`, `IngestProgressRail.tsx`,
`MmRagRunner.tsx`, `ShareSessionPanel.tsx`, `page.tsx`, `GroundednessBadge.tsx`,
`RagSourceCard.tsx` — all under `ml-portfolio/src/{app/tools/multimodal-rag,components}`.
No backend (ML-Unified) changes this segment.
