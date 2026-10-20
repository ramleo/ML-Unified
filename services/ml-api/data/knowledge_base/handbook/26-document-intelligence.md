Chapter 21Document Intelligence


> Upload an invoice, contract, resume, medical report or bank statement and get its fields back as structured data. The document type is identified automatically, each field is extracted with a confidence score, and a box is drawn on the page showing exactly where the value was found.

## At a glance

| | |
|---|---|
| **Also called** | AI-Powered Document Data Extraction |
| **Model or method** | Groq / Gemini / Cohere |
| **What you give it** | PDF, PNG, JPG, JPEG, WEBP |
| **Document Types** | 8 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/document-intelligence` |

## Using the tool

### What this tool does
Upload a document (invoice, receipt, contract, resume/CV, medical report, bank
statement, ID card, or purchase order) and AI extracts its key fields as
structured data. Fields stream in live with confidence scores, validation
checks, and bounding boxes that highlight where each value sits in the document.

### Supported formats
PDF, DOCX (Word), PNG, JPG, JPEG, WEBP. Max 50 MB per file.
- Digital PDFs: text is read directly; fastest and most accurate path.
- Scanned PDFs and images: converted to text by AI OCR first, then processed
  like a digital document.
- DOCX: text, tables, text boxes, headers and footers are all extracted. Word
  files have no fixed page layout, so there is no visual preview and no
  bounding boxes for them — fields still extract normally.

### How to use it
1. (Optional) Pick a document type in the left sidebar, or leave "Auto-detect" —
   AI classifies the document and shows its confidence in the sidebar.
2. (Optional) In "Extra fields to extract", type additional fields you want,
   comma-separated — e.g. "GST Number, HSN Code, PO Reference". They are added
   to the standard fields for that document type.
3. Drag & drop or click to upload the file.
4. Watch the four steps: Extract → Classify → Analyze → Validate.
5. Results appear as field cards on the right; the document preview on the left
   shows bounding boxes for located fields (PDF/image only).

### Smart processing under the hood
- **Complexity-based model routing:** every document is scored before AI
  extraction. Short, single-page digital documents with no tables count as
  "simple" and are routed to a small, very fast model first; multi-page, long,
  table-heavy, scanned or photographed documents count as "complex" and go to
  the full large-model cascade. If the fast model's output fails validation,
  the document is automatically retried on the large models — you never trade
  accuracy for speed. When the fast path serves your document, the provider
  chip reads "via Groq · fast".
- **Multi-column reading order:** two-column layouts (common in designed
  resumes) are detected per page and reassembled column by column — the whole
  left column is read before the right column — so extracted text follows the
  order a human would read, instead of interleaving unrelated lines from both
  columns.
- **Automatic straightening:** uploaded photos are auto-rotated using their
  EXIF orientation (sideways phone shots), and tilted scans are deskewed —
  the tool measures the text tilt and counter-rotates anything between about
  1° and 5° before OCR, which noticeably improves recognition of crooked
  photos of receipts and invoices.

### Reading the results
- Confidence ring: percentage on each field (green ≥90%, amber 70–89%, red " chip in the header: which AI provider served the extraction
  (Groq, Mistral, Gemini, Cohere; "Groq · fast" means the small fast model
  handled a simple document). "(cached)" means this exact file was analyzed
  before and the stored result was replayed instantly without new AI calls.

### Editing fields (human-in-the-loop)
Hover any field card and click the pencil icon to edit its value. Saving marks
the field "Corrected" (human-verified) and sets confidence to 100%. The card
then shows a small struck-through "AI: " line underneath your
value, so you can always compare what the AI extracted with what you changed
it to. If you edit the value back to exactly what the AI extracted, the edit
marker disappears. Edits live in your browser session only — they are captured
in exports but reset if you re-upload or refresh.

**The tool learns from corrections.** Every edit is also reported to the
server as an (AI value → human value) pair for that document type. Recent
correction pairs for a document type are fed into every future extraction of
that same type as guidance — the AI is shown "a human previously corrected
this field from X to Y" and is explicitly instructed to apply the *pattern*
behind the correction, never to copy the literal value into an unrelated
document. This has been verified end-to-end: correcting a merchant name on
one receipt caused a later, completely different receipt — different date,
items, amount, receipt number — to have its own (differently-worded) merchant
field extracted using the corrected phrasing, confirming the AI generalized
the correction rather than replaying it. The most recent ~12 corrections per
document type are kept and expire after 7 days; this memory resets whenever
the server restarts.

### Recent documents (history)
Your last 5 analyses are remembered in your browser (localStorage) and listed
in a "Recent documents" card on the upload screen — file name, detected type,
field count and how long ago. Click an entry to restore that analysis
instantly: all extracted fields, the provider chip and the document chat come
back without re-uploading or new AI calls. The page preview image is not
stored (it would exceed browser storage limits), so the preview panel stays
empty on restore. History is stored only on your device — nothing is kept on
the server — and the Clear button removes it entirely. Restored results show
the AI's original extraction, not manual edits made afterwards.

### Ask this document (chat)
After analysis, a chat box appears below the results. Ask free-form questions
about the analyzed document ("What is the total and when is it due?",
"Summarize this document"). Answers come only from the document's content; if
something is not in the document, the assistant says so. Follow-up questions
keep conversation context.

### Export
The Export menu offers JSON (fields with confidence values) and CSV (opens as
a table in Excel, Numbers, Google Sheets). Exports include your manual edits;
in JSON, any field you edited also carries "original_value" (what the AI
extracted) and "human_edited": true, so downstream systems can tell reviewed
values from raw AI output.

### Notes & limits
- Repeat uploads of the same unchanged file return instantly from a server-side
  cache (up to 24 h). Change the file, the document type, or the extra fields
  and it re-analyzes.
- Experience totals on resumes are recomputed deterministically from the career
  timeline periods, excluding employment gaps.
- If all AI providers are temporarily unavailable, an amber warning appears —
  wait a few minutes and try again.

## What problem it solves

An invoice arrives as a PDF. Somebody has to read it and type nine numbers into
a system. Multiply by a few hundred a month, and that is a full-time job whose
entire content is transcription.

The obvious automation — templates — breaks immediately. Every supplier's
invoice has a different layout, so a template per supplier means an unbounded
maintenance job, and one redesign silently breaks it.

This tool takes a different route. Rather than matching positions on a page, it
reads the document the way a person would, works out what *kind* of document it
is, pulls the fields that document type has, scores its own confidence in each
one, draws a box on the page showing where it found the value, and then checks
its own arithmetic.

## How it works, step by step

1. **Accept the file** — PDF, PNG, JPG, WEBP, or DOCX.
2. **Check the cache.** The file's SHA-256 keys a 24-hour result cache, so the
   same document is never paid for twice.
3. **Get the text out**, by whichever route the file needs — see below.
4. **Judge the complexity.** Short and clean, or multi-page, scanned and
   table-heavy? That decides how much effort the rest of the pipeline spends.
5. **Classify the document** into one of eight types.
6. **Extract the fields that type defines**, each with a value and a confidence.
7. **Locate each value on the page** and return a normalised bounding box.
8. **Validate** — arithmetic, date order, and a consistency pass.
9. **Return** fields, confidences, boxes, and a status per field.

## The model or algorithm

### Eight document types, each with a field schema

Invoice, receipt, contract, resume, medical report, bank statement, ID card and
purchase order. Each carries a list of fields with a name, a label and a
**field type** — `text`, `date`, `currency` — which is what lets validation know
that `total` is a number that must add up while `vendor` is just a string.

**The type descriptions are written to separate confusable pairs, not to
describe the type.** The two that matter:

> **invoice** — *"A REQUEST for payment: has an invoice number, due date, and
> payment terms (e.g. Net 30); payment has not happened yet"*
>
> **receipt** — *"PROOF of a completed purchase/payment at point of sale: shows
> payment method, no due date or payment terms"*

Both contain a merchant, a date, a subtotal, tax and a total. A model given
"an invoice" and "a receipt" as labels will confuse them constantly. Given the
*discriminating* feature — has it been paid, is there a due date — it will not.
That is prompt engineering doing real work: the description exists to make a
decision, not to define a word.

### Getting the text out — three routes

**Digital PDF.** The text layer is read directly, which is exact and free. The
one hard part is **reading order**: PyMuPDF returns text blocks in an internal
order that is not always visual, and a two-column page read straight through
interleaves the columns into nonsense. The module detects a column split and
reads down each column in turn.

**Image or scanned PDF.** There is no text layer, so pages are rendered and sent
to **Mistral OCR** (`mistral-ocr-latest`), which returns markdown — preserving
table structure rather than flattening it into a stream of words. Before that,
the image is deskewed: a phone photo of a document is never square, and a few
degrees of rotation measurably hurts OCR.

**DOCX.** Text is read from the document body. The chapter should be honest that
**bounding boxes are skipped for DOCX** — the format has no fixed layout, so
there is no page position to point at, and the preview panel stays empty by
design rather than by failure.

**A vision-model fallback** exists behind the OCR path — Mistral vision, then
Gemini — for pages OCR cannot handle.

### The complexity tier

Before spending anything, the pipeline decides whether the document is *simple*
or *complex*, from its length, page count, whether it is scanned, and how
table-heavy it is. That choice determines how much work the later stages do.
The principle is worth naming: **spend model effort in proportion to the
difficulty of the document, not uniformly.** A one-page clean invoice does not
need the treatment a forty-page scanned contract needs, and charging both the
same is how a per-document cost becomes unaffordable.

### Locating the value on the page — the five-tier search

This is the most interesting piece of engineering in the tool.

The model returns a *value*. To draw a box you need to find that value in the
PDF's own text — and an exact search almost always fails, because the model
normalises as it reads: it returns `Acme Corporation Ltd.` where the page says
`ACME CORPORATION LTD`, or `$1,234.50` where the page says `1234.50`.

So instead of one search, there are five progressively looser candidates:

| Tier | Candidate | Catches |
|---|---|---|
| 1 | the whole value, capped at 80 characters | exact matches |
| 2 | split on `, ; \| newline`, longest chunk first | a value the model joined from several lines |
| 3 | the first two and first three words of each chunk | a value with a trailing difference |
| 4 | for JSON arrays, every scalar inside the objects | line-item tables |
| 5 | any single word of four or more characters | last resort |

The first candidate that is found on a page wins, and its rectangle is
normalised to 0–1 against the page size, so the frontend can draw the box at any
zoom level.

**Arrays get special treatment.** When the value is a JSON array — line items —
the search prefers the page's **detected table region** rather than the bounding
box of the individual hits, because scattered hits across a table produce a
meaningless box. There is a guard on that too: a table detector that returns a
uselessly narrow rectangle is rejected rather than used.

### Validation — checking the model's arithmetic

Extraction is not verification, and this is where a document tool earns trust.
Several independent checks run over the extracted fields:

**Invoice totals.** `total ≈ subtotal + tax`, with a **2% tolerance** on the
total. If it fails, the total is flagged with the numbers spelled out:
*"Total 1240 ≠ subtotal 1000 + tax 200 = 1200.00"*.

**Bank statement balance.** `closing ≈ opening + credits − debits`, same
tolerance.

**Line items.** The individual amounts should sum to the pre-tax subtotal.

**Date order.** An effective date after a termination date is flagged.

**Resume experience.** Years of experience are recomputed from the dates rather
than trusted as stated.

**Low confidence.** Anything below **0.55** is marked `low_confidence` with a
note recommending manual review.

**And an LLM consistency pass** over the whole field set, for the errors
arithmetic cannot catch.

Each field comes back with one of four statuses — `ok`, `corrected`, `flagged`,
`low_confidence` — so the interface can show you the three fields worth checking
instead of asking you to re-read all nine.

**Why a 2% tolerance rather than exact equality.** Rounding, per-line tax, a
discount line the model did not extract as a field — all produce small,
legitimate differences. Demanding exact equality would flag most real invoices
and train the user to ignore the flag, which is worse than not having one.

## Why these choices

**Why a fixed schema per type rather than "extract everything".** A schema gives
you a stable output shape a downstream system can rely on, a known list of what
is missing when a field is absent, and — crucially — the field *types* that make
validation possible. Free-form extraction gives you a different JSON shape for
every document.

**Why confidence per field rather than per document.** A document is rarely
wholly right or wholly wrong. Eight fields read cleanly and the total is
ambiguous — you want to check the total, not re-key the document.

**Why bounding boxes at all.** They convert "the model says the total is £1,240"
into "here is where it says so", which a person can verify in a second. It is
the same argument as showing the SQL in the Text-to-SQL chapter: an unverifiable
answer from a black box is not usable in a process that has consequences.

**Why cache on the content hash rather than the filename.** The same invoice
sent twice under two names is the same work. Hashing the bytes catches that;
hashing the name does not. 24 hours is the usual window for an exact-match cache
over a paid model.

**Why OCR to markdown rather than plain text.** A table flattened into a word
stream loses which number belongs to which row, which is precisely the structure
line-item extraction depends on.

## How to read the output

- **Check the flagged fields first.** They are flagged because a number did not
  add up, and that is the highest-value minute you can spend on the document.
- **Confidence under 55%** carries an explicit review recommendation.
- **Click a field to see its box.** If the box is on the wrong part of the page,
  the value is suspect even when it looks right — the search found something
  else that matched.
- **No box does not mean no value.** DOCX has no layout at all, and the five-tier
  search can fail on a value the model rewrote heavily.
- **A wrong document type invalidates the fields**, because the field list comes
  from the type. Check the type first if the fields look strange.
- **The type descriptions are the tie-breaker.** If an invoice was read as a
  receipt, the useful question is whether it has a due date and payment terms.

## Limits

- **Eight types.** Anything else is forced into the nearest one.
- **Extraction quality is the model's**, and it is not fine-tuned on documents.
  Handwriting, poor scans, unusual layouts and dense multi-column legal text are
  all harder.
- **Confidence is self-reported.** A model's stated confidence is not calibrated
  in the statistical sense — it is a number it produced, not a measured
  probability. Treat it as a ranking, not a percentage.
- **The bounding-box search can find the wrong instance** of a value that
  appears more than once on a page.
- **No boxes for DOCX.**
- **Validation only covers the relationships it knows about.** A wrong vendor
  name is unfalsifiable from inside the document.
- **The 2% tolerance will pass small real errors.**
- **The cache is in memory**, so it is lost on restart.
- **Everything is sent to a third-party model.** Invoices and medical reports are
  sensitive, and the trade is disclosed rather than avoided.

## Likely interview questions

**"Why not use a template-based extractor? They're more accurate."**
They are, on the layout they were built for. The problem is that every supplier
has a different layout, so you need a template per sender and a maintenance job
that never ends — and one redesign breaks a template silently. A model reading
the document generalises to layouts it has never seen, which is the property
that makes it usable at all. I would use templates for a high-volume single
source and this approach for the long tail.

**"How do you know the extraction is right?"**
You verify what can be verified rather than trusting the model. Totals must
equal subtotal plus tax within 2%; a bank statement's closing balance must equal
opening plus credits minus debits; line items must sum to the subtotal; dates
must be in a sensible order; resume experience is recomputed from the dates
rather than read. Anything that fails is flagged with the numbers shown. What is
left — a vendor name, say — is unfalsifiable from inside the document, and for
that the bounding box lets a person check it in a second.

**"Why 2% tolerance and not exact?"**
Because exact equality flags most real invoices — rounding, per-line tax, a
discount line that was not extracted as its own field. A flag that fires on
everything gets ignored, and then it fires on the one that matters and gets
ignored too. The tolerance is chosen so the flag stays meaningful.

**"How do you draw a box around a value the model paraphrased?"**
Progressive relaxation. Five tiers of candidate, from the whole value down to
any four-letter word in it, taking the first that is found on the page. Exact
match almost never works because models normalise case, punctuation and currency
symbols as they read. For JSON arrays the search prefers the page's detected
table region, because scattered hits across a table give a box that means
nothing.

**"How would you keep the cost down at scale?"**
Three things, all in the code. Hash the file content and cache the result, so
the same document is never paid for twice. Tier by complexity, so a clean
one-page invoice does not get the treatment a forty-page scanned contract needs.
And read the text layer directly when the PDF has one, since OCR is the
expensive path and most PDFs never need it.
