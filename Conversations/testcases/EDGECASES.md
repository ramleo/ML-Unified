# Edge Cases — Standing List

**Purpose:** Separate from the TC-*.md test case files. This list tracks edge
cases as they're *noticed* (during dev, bug reports, or deliberate review) —
often before they're formalized into a numbered test case. Every entry here
should also get a corresponding TC-* entry once it's actionable (see "TC ref"
column); this file is the raw/standing list, the TC files are the formal
record.

**Rule (added 2026-08-24):** From now on, whenever an edge case is identified,
it is (1) added here, AND (2) added to the relevant TC-*.md file as a numbered
test case. Neither replaces the other.

---

## Open

| # | Area | Edge Case | Noted | TC ref | Status |
|---|------|-----------|-------|--------|--------|
| EC-004b | Multimodal RAG — doc switching | AI Sharpen result surviving a switch-away-and-back (drag-based Draw-region removal already covered by EC-001's fix; the whole-image AI Sharpen half is untested — blocked live 2026-08-24 by a transient 502 on `/rag/mm-deblur`, confirmed NOT a real outage via direct curl (endpoint returned normal 422 to a raw request seconds later), just unlucky timing during verification. | 2026-08-24 | TC-P10-097 | Open |
| EC-005 | Multimodal RAG — doc switching | "Compare these documents" / contradiction-check citations — still correct after a manual sidebar document switch? Attempted 2026-08-24 with two unrelated photos (face.jpeg + bicycle.jpeg) — correctly returned "No contradictions found (0 overlapping passages checked)", but this pair has no real textual overlap to produce an actual contradiction citation to click through. Needs two documents with genuinely conflicting overlapping claims (e.g. two versions of a spec/invoice) to properly exercise this. | 2026-08-23 | TC-P10-098 | Open |
| EC-006 | Multimodal RAG — video | Video timestamp-based citation jumping (MMRAG-09) combined with document switching. Not yet attempted — needs a video test asset (none used in this session). | 2026-08-23 | TC-P10-099 | Open |
| EC-007 | Multimodal RAG — captioning | Vision captioner hallucinates structure on a single, plain portrait photo — reproduced twice live 2026-08-24 on the same face.jpeg upload: captioned it as "a vertical collage of four cropped sections of a young man's face" / "a composite of cropped views" when the source is one plain headshot, no collage/crop involved. Same failure MODE (inventing sub-image structure that isn't there) as the OCR junk-table hallucination fixed earlier this session (`is_junk_table_block` in `mm_caption.py`), but a different SYMPTOM (caption text content, not a bogus table block) — likely not covered by that fix. Root cause not yet investigated. | 2026-08-24 | TC-P10-100 | Open |

---

## Resolved

| # | Area | Edge Case | Noted | Resolved | TC ref | Notes |
|---|------|-----------|-------|----------|--------|-------|
| EC-001 | Multimodal RAG — doc switching | `visualAction` dropdown state across a document switch — does it reset, or show a stale selection from the previous document? | 2026-08-23 | 2026-08-24 | TC-P10-094 | CONFIRMED real bug, reproduced live: selecting "Detect objects" on bicycle.jpeg then switching to face.jpeg left the dropdown on "Detect objects" and rendered face.jpeg's own object boxes under the wrong stale action instead of face.jpeg's actual last state ("Detect faces"). Root cause: `visualAction` (and `showFaces`/`drawMode`/`regionMode`/`zoneMode`/`restrictedZone`/similar-figures state) in `CitationThumbnailPanel.tsx` were plain `useState` with no reset tied to the viewed citation. Fixed by extracting all of it into `useCitationVisualState.ts`, a hook keyed on `editKey` (`source:page`) with a reset `useEffect` — this also brought `CitationThumbnailPanel.tsx` back under the 400-line cap (395→373). Committed `9dd24be`, pushed, verified fixed live on Vercel. |
| EC-002 | Multimodal RAG — doc switching | Removing the currently-active document — does the Evidence panel recover cleanly? | 2026-08-23 | 2026-08-24 | TC-P10-095 | Verified live: removing face.jpeg while it was the active citation cleanly fell back to "Click a citation to see its page" — no crash, no stale image/dropdown, the remaining document (bicycle.jpeg) stayed intact. No bug found. |
| EC-003 | Multimodal RAG — doc switching | Multi-page PDFs + the doc-switch fix (jumps to page 1 of whichever doc is clicked) — is losing the last-viewed page correct, or should page be remembered per document? | 2026-08-23 | 2026-08-24 | TC-P10-096 | Verified live behavior: switching to a different document's session-source row does reset to that document's page 1 (confirmed, not yet judged as right/wrong — deliberately not "fixed" since it may be the intended behavior; flagged for a product-level decision, not a bug). |

*(EC-004's original scope — in-progress edits surviving a switch — was split: the Draw-region/drawMode-toggle half is resolved as part of EC-001's fix since it shared the same root cause; the AI-Sharpen-result-persistence half is tracked separately as EC-004b above, still open.)*
