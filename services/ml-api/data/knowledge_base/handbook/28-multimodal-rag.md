Chapter 23Multimodal RAG


> Ask questions about a PDF and get answers cited back to the page they came from — including answers that live in a table or a chart rather than a paragraph. Tables are read as structured data and figures get an AI-written caption, so a number buried in a bar chart is still findable.

## At a glance

| | |
|---|---|
| **Also called** | Tables & Figures as Citable Knowledge |
| **Model or method** | Groq / Mistral / Gemini |
| **What you give it** | PDF (text, tables, figures) |
| **Chunk Types** | 3 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/multimodal-rag` |

## Using the tool

### What this tool does
Upload a PDF that mixes prose, tables, and charts/figures — a quarterly
report, a research paper, a spec sheet — and ask questions about it. Unlike
plain text search, this tool reads tables as structured data and writes an AI
description of every chart or photo, so it can answer questions whose answer
lives in a number buried in a table or a trend shown in a chart, not just in
paragraphs. Every answer cites the page and content type (text, table, or
figure) it came from. A page with two unrelated visuals — say, a chart and
a company logo — gets each one described and cited separately instead of
blended into one caption, so an answer about the chart doesn't accidentally
pull in details from the logo sitting next to it. A row of several small
images that only make sense together — a career timeline of company
logos, for instance — is recognized as one group and captioned as such,
even though no single logo in it is large enough to trigger captioning on
its own. When a chart has genuinely readable numeric values — printed data
labels, or bar heights read against the axis scale — those values are
pulled out as their own little data table alongside the prose description,
so a precise question ("what was Q3 revenue, exactly") gets answered from
the real extracted number, not the AI's rough paraphrase of the chart.
That table shows up as its own citation, downloadable as CSV and plottable
as a mini bar chart, exactly like a table pulled straight from the
document. This depends on the AI reading the chart correctly — a chart
with clear printed data labels is reliable; one with no data labels at
all (values only readable by judging bar height against the axis), a
rotated/cramped axis, a log scale, or overlapping bars is inherently
harder to read accurately and hasn't been extensively tested. Treat an
extracted chart value the same as any other AI-read number: quick to
check against the original if the answer matters.

You can also upload a single photo or image (PNG, JPG, GIF, WEBP) on its own
— no PDF needed. The AI writes a thorough description of everything in it
(subjects, objects, setting, colors, any visible text or numbers), and you
can then ask follow-up questions about that description in the same chat,
just like with a document.

A CSV file works too — its rows and columns are indexed the same way a
PDF's embedded tables are, so you can ask questions about the data directly.

You can also upload a short video (MP4, MOV, WEBM, AVI, MKV). If it has an
audio track, that's transcribed first and indexed as regular text — so you
can ask what was said, not just what's shown. Once a real transcript
exists, only 2 visual frames are sampled (rather than 6): for a
talking-head video the audio already carries the content, so extra frames
mostly just confirm the scene hasn't changed. A silent video, or one whose
audio can't be transcribed, samples the full 6 frames instead, since frames
are then the only available signal. Those frames aren't just evenly spaced
in time — the video is scanned for real scene changes first (comparing
frames in the frequency domain, the same technique behind the blur-quality
check), so a video with a couple of distinct shots samples near where they
actually change instead of risking 6 near-duplicate frames of the same
shot. A video with no clear scene changes (a static talking-head shot)
falls back to plain even spacing. Each sampled frame is described and
OCRed just like a PDF's figures (the caption itself notes what timestamp it
was taken at), and citations are labeled "Video Frame."

The full transcript (not just the chunked pieces used for chat retrieval)
is readable in a video's "▸ summary" panel, timestamped by segment
(e.g. "[0:07] ..."). Download it as a plain .txt file, or as a
timestamped .srt subtitle file. If the video has enough content, a row of
clickable chapter markers (like YouTube's auto-chapters) appears above the
transcript — click one to jump straight to that part. Clicking a
transcript-based citation in the chat also jumps to and highlights the
exact segment it came from. A search box above the transcript highlights
every matching word and lets you step through matches one at a time.

The actual video is also playable right there in the summary panel —
clicking any transcript line, a chapter, or a transcript-based citation
seeks playback to that exact moment, the same way YouTube's transcript
panel works. A citation for a captioned video FRAME (something visual, not
spoken — e.g. "what's written on the whiteboard") jumps and seeks the same
way, straight to the exact second that frame was sampled from, even though
there's no transcript segment behind it.

For videos with more than one person talking, each transcript segment is
also labeled with who's speaking ("Speaker 1," "Speaker 2," etc.) when
that can be reliably determined — included in the .srt export too. A
video with just one speaker won't show labels, since there's nothing to
distinguish.

As you watch, a smooth density curve appears above the transcript labeled
"Your most re-watched moments (this session)" — every time you scrub the
video back or click a transcript line/chapter to jump to it, that moment
raises the curve there. Example: if you watch straight through once, then
go back twice to re-listen to the 1:20 mark, the curve peaks around 1:20
— a quick visual of what YOU personally rewound to, similar in spirit to
YouTube's "most replayed" graph but scoped to just your own session
(there's no cross-viewer data here to draw on, since each upload is
private to whoever uploaded it). It only appears once you've actually
jumped around at least once; a linear first watch shows nothing yet.

Every video/audio upload is also automatically checked for two possible
deepfake indicators — nothing to click, they run in the background. A red
"Possible deepfake signals" box appears above the transcript only if
something looks off: (1) **audio/lip-motion desync** — whether the
speaker's mouth movement actually tracks when the audio has speech in it,
using face-landmark tracking compared against the audio's volume pattern
over time; (2) **possible synthetic voice** — whether the audio's frequency
pattern looks more like a TTS/cloned voice than natural human speech.
Neither is a trained deepfake-detection model — both are statistical
heuristics, tested and disclosed as reliably catching a fully mismatched
audio/video pairing but weaker at a subtle few-hundred-millisecond offset,
and the voice check has only been validated against system text-to-speech,
not sophisticated voice-cloning tools. Treat a flag as "worth a closer
look," not a verdict — and treat no flag as "nothing obviously wrong,"
not "confirmed genuine."

### How to use it
0. You can upload more than one file into the same chat — each stays listed
   above the chat with a way to remove it, and questions are answered across
   all of them together, with citations naming which document each part of
   the answer came from. Good for "compare these two reports" style questions.
1. Upload a PDF or an image (max 20 MB; PDFs process their first 8 pages).
   A video's audio is automatically split into smaller pieces for
   transcription if needed, so a longer recording still works within the
   same 20 MB upload limit.
2. Watch the ingestion steps: for a PDF — page extraction → table detection →
   figure captioning → embedding; for a standalone image — captioning →
   embedding. A summary shows how many text, table, figure, or image chunks
   were found.
3. Ask questions in the chat below. Answers stream in with citations you can
   expand to see the source page, content type, and a thumbnail.
4. Clicking a citation jumps the preview panel to that page. A thumbnail
   strip on the far right lets you browse every page of the document on
   your own, independent of citations (hidden for single-page/image
   uploads, since there's nothing else to browse).
5. Click "summary" next to any uploaded document's name to see everything
   extracted from it — every table (shown as an actual table) and every
   figure/image caption — without asking a question first. Whenever there's
   substantial extracted text to show (a PDF, CSV, or standalone image, not
   just a video's transcript), the same search-as-you-type box described
   above for videos appears here too — highlighting every match and letting
   you step through them one at a time.

### Two upload choices, both with real tradeoffs
- **Find visually similar figures (optional)**: off by default. Turning it on
  additionally encodes each figure/chart image with a small image-recognition
  model, adding a "find similar figures" button to figure citations. This
  does NOT change how chat questions are answered — captions always power
  that — it only adds a bonus visual-search feature. Downloads an extra model
  the first time it's used and adds a few seconds per figure during upload.
- **Sharing scope**: "Session only" (default) means only you can query what
  you uploaded, and it's gone if you refresh. "Share with all visitors right
  now" makes it queryable by anyone using the tool while this server keeps
  running — useful for showing a document to someone else in the same
  sitting. Neither option is permanent: this demo runs without persistent
  storage, so a server restart clears everything uploaded, shared or not.

### Re-uploading a document you already added
If you upload a file that looks like a newer version of something already
in this chat — same filename, or text that's highly similar even under a
different name — a banner asks you before doing anything: "Replace the old
one, or keep both?" Nothing is ever swapped out automatically. Choosing
"Replace old" removes the earlier version the same way the × button does;
"Keep both" just dismisses the banner and leaves both documents in the
chat. This only compares against documents still in your current session,
never anything from another chat.

### Answers keep working even if a provider is busy
Chat answers are generated by an AI provider (Groq, Gemini, Cohere, etc). If
your selected provider is rate-limited or briefly unavailable, the tool
automatically retries with another provider behind the scenes. This only
happens before an answer has started; if a provider fails partway through
writing a response, that's shown as an error rather than silently switched,
since splicing two providers' text together would produce a garbled answer.

A tag above the chat always shows which provider actually generated the
answer. Normally it just says "Answered via X." If your chosen provider
failed and a fallback stepped in, it says so plainly instead — e.g.
"cohere unavailable (rate limited) — answered via groq" — so a different
provider answering is never a silent surprise.

### Answer length
A "Concise / Normal / Detailed" toggle sits next to the Provider button.
"Concise" asks the AI for the shortest complete answer — 1-3 sentences,
no extra context — good for a quick fact check like "what's the invoice
total?" "Detailed" asks it to explain its reasoning and pull in related
details from the source, good for "walk me through how this pricing table
is structured." "Normal" (default) is unchanged from before this toggle
existed. It only changes how the SAME retrieved information is written up
— it doesn't change what's retrieved or which citations show.

Clicking a different length regenerates the answer you're currently
looking at, in place — you don't need to ask the question again. It
replaces just the last answer bubble; earlier answers in the conversation
keep whatever length they were originally given at.

### While an answer is generating
A "Stop generating" button replaces the send button while an answer is
streaming in — click it to cancel mid-answer if it's heading somewhere
unhelpful or taking too long, rather than waiting it out.

### Rating an answer
Every assistant answer has small thumbs-up/thumbs-down buttons underneath
it. These are for your own feedback only — clicking one doesn't change the
answer, regenerate it, or affect later questions in any way.

### Checking your documents for contradictions
Once you've uploaded 2 or more documents into the same chat, a "Check
documents for contradictions" button appears. Click it and the tool scans
your uploaded documents for passages that make a factual claim about the
same specific thing — a date, an amount, a name, a status — but disagree
with each other. Example: one document says a deadline is March 15, a
revision memo says it moved to April 30 — that's flagged, with both
excerpts, their source document, and page number shown side by side, plus
a one-line explanation of what disagrees.

It only flags genuine disagreements, not every passage that happens to
mention a similar topic — two documents stating the same figure in
different words are correctly left alone. It only compares documents
within your current chat session, and only checks a bounded number of the
most topically-similar passage pairs, so it stays fast even with several
documents loaded.

### Only search specific content types
When your document(s) contain more than one kind of content (say a PDF
with both prose and tables), an "Only search: All / Text / Table / Figure
/ Image / Video Frame" row of chips appears above the citations. Selecting
one or more restricts retrieval to just that type — genuinely excluded
before the AI even sees it, not just hidden afterward. Example: click
"Table" before asking "what were the totals" and the AI can only answer
from detected tables, ignoring any prose that happens to mention similar
numbers — useful when you specifically want the structured-data answer,
not a paraphrase from surrounding text. Click "All" to go back to normal.
This only appears when a document actually has 2+ distinct content types
to choose between — a plain-text-only upload has nothing to filter.
The same row also lets you filter by the key-fact type a chunk contains —
Money, Date, Percent, Person, Organization, Location, Legal Clause,
Financial Term, or Medical Condition — once at least one uploaded chunk has
one, for narrowing down to (say) only chunks that name a specific person or
company, or only chunks that mention contract-clause language.

### Using your own API key (optional)
The "Provider" button above the chat lets you pick a specific AI provider
and model, and optionally paste in your own API key for it. This is entirely
optional — the tool works out of the box using shared demo keys, which is
enough for normal use. Bringing your own key is useful if you want a
specific model, or want your usage on a quota you control rather than the
shared demo's. Your key is stored only in your browser (localStorage). Each
question sends it along with your query to this tool's own backend, which
uses it to call the provider on your behalf for that one answer — it's
never written to disk, stored in a database, or logged on this server, and
isn't kept anywhere after that request completes.

### Reading citations
A citation is the small card under each AI answer that says exactly where
that answer came from — click one to expand it and see more.

- **"Directly cited" vs "Additional context."** When an answer only actually
  used some of what was retrieved, the Evidence column splits into two
  labeled groups instead of one flat list: "Directly cited" (what the
  answer's citations point to) and "Additional context (not used in this
  answer)" (other relevant passages that were retrieved but didn't end up
  backing anything the answer said). If everything retrieved was used, you
  just see one plain list — the split only appears when there's a real
  difference to show.
- **Source, page, and type.** Each citation shows its source document, a
  page number, and a content type badge — Text, Table, Figure, or Image —
  whenever that's known. Example: ask "what was Q3 revenue?" and the
  citation might read "quarterly-report.pdf · p.4 · Table," meaning the
  number came from an actual detected table on page 4, not a guess.
- **Table citations are real, structured data — and downloadable.** If a
  citation is typed "Table," the answer came from that table's actual rows
  and columns (shown below as a real rendered table, not raw text). A
  "Download CSV" link sits right above it — click it and that exact table
  saves to your computer as a real .csv file you can open in Excel or
  Google Sheets. Example: upload an invoice, ask "what line items are on
  this invoice," get a Table citation, click "Download CSV" — you now have
  the invoice's line items in spreadsheet form without retyping anything.
  When the table has at least one column of real numbers (prices,
  quantities, scores), a "Table / Chart" toggle also appears next to
  Download CSV — switching to "Chart" turns that column into a quick bar
  chart, using whichever non-numeric column (e.g. item name) as labels. If
  a table has more than one numeric column (say Price and Quantity), small
  buttons above the chart let you pick which one to plot. This is view-only
  — it doesn't change the answer or the underlying data, just a faster way
  to eyeball a trend than reading raw numbers.
- **Figure and Image citations combine an AI description with exact OCR
  text.** These mean the answer came from an AI-written description of a
  chart, diagram, or photo, PLUS a separate OCR pass that reads out any
  exact text or numbers visible in the image. Example: a citation for a
  timeline graphic might say "shows quarterly milestones from Jan to Dec"
  (the AI's description) AND list every date printed on the graphic (the
  OCR reading) — so you can ask both "what does this chart show" and
  "what's the exact date next to milestone 3" and get real answers either way.
- **"Read aloud" plays a citation's caption as speech.** Open "Choose an
  action…" on an image/video citation and pick "Describe (caption + OCR)" —
  once the caption text appears, a "Read aloud" button sits right above it.
  Click it to hear that description spoken using your browser's own
  text-to-speech voices (entirely on your device, no server call); click
  "Stop reading" to cancel partway through. Only one citation reads at a
  time — starting another automatically stops whichever was already playing.
- **Click to expand and see a thumbnail.** Every citation can be clicked
  open to show a thumbnail of the actual page or image it came from, so
  you can visually confirm it yourself.
- **Mixed pages get both extracted.** A page that has both real text and
  an embedded graphic (e.g. a resume with a text sidebar next to a skills
  chart) is split into two chunks: the text as usual, plus a separate AI
  caption for the graphic — so the chart isn't silently skipped just
  because the page is mostly text.
- **"Show everything else on this page."** Every expanded citation with a
  page number has this link. Example: the AI answers from one paragraph on
  page 3 of your report; click this link on that citation and you'll also
  see the table and the chart caption that came from that same page 3,
  even though the answer only cited the paragraph.
- **"Verify number" warning (red).** Every figure/chart gets both an AI
  description and a separate OCR reading. If the two disagree on a number
  from the SAME image — e.g. the description says "revenue grew to $42M"
  but OCR read "$24M" off the same chart — the citation shows a red
  "Verify number" badge, since one of the two likely misread the value.
  The AI itself is told about the disagreement too, so if it answers using
  that citation it will say the number is uncertain rather than stating
  either figure as fact. Check the original page yourself before trusting
  either number in that case.
- **"Contains [type]" warning (amber).** If a chunk's own extracted text
  contains something like an email address, phone number, Social Security
  Number, or credit card number — common on an uploaded resume or invoice
  — that citation shows an amber "Contains email" (or phone/SSN/card
  number) badge. This is only a heads-up before you screenshot or share
  that citation with someone else — in your own session nothing is hidden,
  masked, or withheld, and the AI can still see and use that text normally
  when answering you. A shared-link viewer (see "Sharing a session" below)
  sees this differently: those flagged types are actually redacted from
  what reaches them, not just flagged.
- **"Maybe blurry" note (gray).** Every figure/chart/photo is run through a
  quick sharpness check at upload time (an edge-detail scan, no extra
  model or delay). If it reads low, the citation shows a gray "Maybe
  blurry" badge — a heads-up that the AI's description or OCR reading of
  that specific image might be less reliable than usual, so it's worth a
  quick look at the original. It's a heuristic, not a certainty: a very
  plain, low-detail image can occasionally trip it even when perfectly sharp.
- **"Sharpen image (AI)" / "Sharpen region…" buttons.** Always available
  above any citation's own image (a page image has to exist — same
  requirement as "Draw region"), not just when the "Maybe blurry" badge
  shows: that badge is a whole-image average, so a photo that's mostly sharp
  with only a small blurry patch (a deliberately blurred logo/plate on an
  otherwise crisp product shot, say) never trips it even though there's real
  blur to fix. "Sharpen image (AI)" enhances the whole photo; "Sharpen
  region…" instead lets you drag a box around just the blurry part (same
  click-and-drag as "Draw region") — only that box is sent to the model and
  pasted back, so every pixel outside it is left byte-for-byte untouched, no
  matter what the model does inside the box. A progress bar shows under the
  image while a call is running. Once you have a result, a "View original /
  View sharpened" toggle lets you compare, and you can re-sharpen (whole or
  a different region) any time without starting over.
  This is a generative edit (an AI model re-renders a crisper version), not
  a mathematical fix, so it can occasionally invent plausible-looking detail
  instead of admitting a spot is unreadable — seen live on a real photo
  where a blurred license plate came back with invented text (a DIFFERENT
  invented reading on each independent attempt, which is exactly how this
  was caught).
  A region sharpen specifically corroborates itself before trusting a
  reading: it runs the AI TWICE independently on your selected box and OCRs
  each result. If both readings agree, the caption shows the confirmed text
  directly (still labeled to verify against the original); if they
  disagree, that disagreement IS the finding — the caption switches to an
  explicit "likely unreliable, do not trust this detail" warning rather than
  showing either guess as if it were real. This check only applies to actual
  text — selecting a logo, icon, or other non-text graphic correctly falls
  back to a different caption instead of a false "disagreed" warning, since
  OCR was never going to read text off a picture either way: a separate
  vision-model call looks at the sharpened region and names what it actually
  is (e.g. a specific brand or logo it recognizes), shown as "Identified as:
  ..." — this is a single AI opinion, not a corroborated reading like the
  text case above (there's no independent-agreement check for a free-text
  description), so it's always labeled unverified rather than confirmed. If
  even that call comes back empty, it falls back to the plain generic
  caption. A whole-image sharpen doesn't run either check at all (it's for
  general clarity, not reading or identifying one specific detail) and
  always keeps the plain caption. Either way, the sharpened view is never
  used as the base for
  other edits (removing objects) but CAN be downloaded — "Download" (next to
  the sharpen buttons) saves whichever version is currently on screen,
  original or sharpened.
  A region sharpen takes longer than a whole-image one (it's up to four
  calls, not one) — while it's running, the buttons are replaced by a single
  "Cancel sharpening" if you don't want to wait; a "temporarily unavailable"
  message means one of the calls failed on its own. Your drawn box gets a
  small automatic margin (not literally pixel-exact) so text you selected
  slightly too tight doesn't get clipped at the edge.
- **Key facts chips.** Expand a citation and you may see small colored chips
  above the source text — amounts, dates, percentages, people, organizations,
  or locations found in that exact chunk (e.g. "$1,245.50", "April 30, 2026",
  "12.4%", "Acme Corp"). Amounts/dates/percentages are pulled out with pattern
  matching; people/organizations/locations use a small local name-recognition
  model — both run automatically at upload time, so you can scan a citation
  for its key facts without reading the whole paragraph. A chunk mentioning
  an unusually long list caps at 8 chips with a "+N more" tail rather than
  crowding the citation. Only chunks that actually contain one of these show
  any chips.
- **Domain-term chips (legal / financial / medical).** The same chip row can
  also surface contract-clause language ("indemnification," "force majeure,"
  "non-compete"), accounting/finance terms ("EBITDA," "accounts receivable,"
  "working capital"), or medical-condition names ("diabetes," "hypertension")
  when a chunk mentions one. All three are matched against curated term
  lists, not a trained model — the medical category in particular is a plain
  keyword spotter for condition NAMES only (not symptoms, dosages, or drug
  names) and is not a diagnostic tool or clinically validated in any way.
- **Groundedness score.** Open "How I searched" under any answer and you'll
  see a Groundedness badge (High/Medium/Low, plus a %) — how well the
  answer's own sentences actually match the retrieved sources, checked
  automatically right after the answer is generated. If a sentence doesn't
  match anything retrieved well, it's listed underneath as "possibly
  unsupported" so you know exactly which part to double-check. It's a
  heuristic based on text similarity, not a fact-checker — a true but
  unusually-worded sentence can occasionally get flagged too. The badge is
  simply absent (not shown at all) for an answer in a non-English script
  (Hindi, Telugu, Chinese, Arabic, etc.) — the similarity check compares
  text using an English-centric model, which can't reliably tell a correct
  translation from an unrelated sentence once the script changes. Rather
  than risk showing a misleadingly low score on an accurate answer, it
  skips the check entirely and shows nothing — a deliberate "we chose not
  to guess," not a bug or a missing feature. (If you're looking at the raw
  API response instead of the UI, this is the groundedness field coming
  back as null for that answer.)
- **Self-correction on a weak score.** A "Low" groundedness score — or a
  "Medium" one with specific sentences flagged — triggers one automatic
  fix attempt before you're done reading. You may briefly see an answer
  start streaming in, then watch it clear and restart: that's the retry
  replacing the first attempt, not a glitch. The retry isn't a blind
  do-over — the model is told exactly which of its own sentences didn't
  match the evidence and asked to fix or drop only those, using a
  broadened set of already-retrieved candidates (no extra retrieval
  delay). A small "Self-corrected once" tag appears next to the
  Groundedness badge when this happened; hover it for the same
  explanation. It only ever fires once per answer, and only keeps the
  retry if it scores no worse than the original — a weak-but-complete
  first answer is never swapped for something worse.
- **Ask in your own language.** You don't need to ask in English — type
  your question in whatever language you're comfortable with (Hindi,
  Telugu, Spanish, French, etc.) and the answer comes back in that same
  language, translated from the underlying English captions/transcripts on
  the fly. Citations and the retrieved source text itself stay in their
  original (usually English) language either way — only the written answer
  adapts. Expect no Groundedness badge on these answers, for the reason
  above.
- **"Why was this cited?" trace.** Expand a citation and, below the source
  text, a "Why was this cited?" link opens the actual retrieval signals
  behind that specific citation's rank — not just that it was picked, but
  which of several independent search methods found it and how confidently.
  Up to four signals can run on a question, each shown as its own colored
  chip when it contributed: **dense** (semantic search — matches meaning,
  even with different wording), **keyword** (matches exact terms, even rare
  ones the semantic model might gloss over), **vision** (image-embedding
  search — matches a photo or chart by what it visually looks like, not just
  its caption text; only runs against uploads containing figures/images),
  and **graph** (matches because this chunk and your question share the
  exact same specific value — a dollar amount, date, percentage, person, or
  organization name — a stronger signal than a topical match when your
  question names one precise fact). A citation shows whichever of these
  actually surfaced it, its raw score, and its rank within that method's own
  results — some citations are found by several signals at once, some by
  only one. Hover a chip for a one-line explanation of what it means.

  The wording of your question also tilts how much each signal counts
  before ranking happens — a question naming a specific number, date, or
  name leans on the graph signal more; a question about a color, chart, or
  photo leans on vision more; a short exact-phrase lookup leans on keyword;
  a broader question leans on semantic/dense — so a citation that would
  otherwise rank lower can outrank a superficially "closer" match once your
  question's own phrasing is accounted for. When your question's wording
  also suggested a specific content type (e.g. asking about a "table" or
  "chart"), a separate boost multiplier shown here explains why a short
  table/figure citation outranked a longer passage that would otherwise
  dominate. A final relevance percentage shows the last check applied — an
  actual re-read of the citation against your exact question, which is what
  really decided its final rank and whether it made the cut at all. This
  section only appears when at least one of these signals was actually
  tracked for that citation — a cached answer (repeating an earlier
  question) doesn't carry the original trace, so it's omitted rather than
  shown empty.
  Clicking it never re-runs anything — it just reveals numbers already sent
  with that specific answer, a frozen snapshot of that one retrieval run.
  Those numbers can look different for the SAME document across different
  questions, and that's expected, not a bug: every question re-scores and
  re-ranks against whatever's in the candidate pool at that moment. Example:
  a bicycle photo's citation might rank #1 with a high semantic score when
  it's the only document uploaded, then show a lower score and #2 rank on a
  later question after a car photo (or any other document) joins the chat —
  it's now being scored and ranked alongside genuinely more candidates, not
  because anything about the bicycle photo itself changed.

### Locating objects in an image or video frame
Every standalone image and every sampled video frame is also run through a
closed-vocabulary object detector (601 possible object types — everyday
things like Bicycle, Car, Bus, Backpack, Traffic light, Person, and many
more) once, at upload time — not a fresh AI call every time you ask. So a
question like "where is the bicycle?" or "locate the bus" is answered from
that precomputed list, and the answer describes a coarse position: "spans
most of the frame" for something large/close, or a rough zone like
"top-left," "center," or "bottom-right" for something smaller. This is
intentionally coarse — a phrase, not pixel coordinates — since the model is
meant to place things in general terms, not measure them precisely.

- **The detected object list is baked into the same text the AI reads and
  the same text used to grade the answer.** Earlier versions of this
  feature fed detected objects to the AI separately from what backed the
  "Groundedness" score above, which could make a correct, precise answer
  ("the car spans most of the frame") show up as Low groundedness even
  though it was right — the score just couldn't see where that fact came
  from. That's fixed: the object list is now part of the citation's stored
  text itself, so the answer and its groundedness score are always looking
  at the same thing. Images/videos uploaded before this fix need to be
  re-uploaded to pick it up.
- **A visible bounding box only appears on a clicked citation, and only if
  its labels match your last question.** Click a citation card open (not
  the document "▸ summary" pill — that just opens a plain page preview) and
  the panel on the right can draw a colored box directly on the image. But
  it only draws when the wording of the question you most recently asked
  matches one of THAT SPECIFIC citation's own detected labels. Example: if
  you ask "locate the bicycle" and then click a car photo's citation, no
  box appears — "bicycle" doesn't match anything the detector found in that
  car photo. Click the bicycle photo's own citation instead, or re-ask a
  question that names something actually detected in the image you're
  looking at.
  Two easy ways to end up with no box even when you're looking at the
  "right" image: (1) opening the image via the document's "▸ summary" pill
  instead of clicking an actual citation row — the summary view is a plain
  page preview and never triggers box-matching at all, regardless of what
  you last asked; (2) clicking a citation whose OWN labels don't match your
  last question, even if a different citation earlier in the chat would
  have matched. Concrete example: you ask "locate car" (matched fine
  against a car citation), then click a DIFFERENT citation — the bicycle
  photo's card. No box appears, because the matching always re-checks
  against the citation you just clicked, and "car" isn't one of the
  bicycle photo's detected labels ("Bicycle," "Wheel," "Tire," etc). To see
  a box on the bicycle photo, ask something that names one of ITS labels —
  "where is the bicycle" or "locate wheel" — right before or after clicking
  its citation.
- **A "spans most of the frame" box looks like a thin border, not a tight
  box.** When an object fills most of the photo (common for a single
  product shot or a close-up), the drawn box runs almost all the way around
  the image's edges rather than tightly hugging just the object — easy to
  miss at a glance since it looks similar to the image's own border.
- **A few generic terms are matched to their specific detected subclass.**
  The 601-type vocabulary is hierarchical — a photo's person is detected as
  the more specific "Man," "Woman," "Boy," or "Girl," never the generic
  "Person," and similarly a vehicle is detected as "Car," "Truck," "Bus,"
  etc, never generic "Vehicle." Asking "locate the person" or "where's the
  vehicle" still works — those generic terms are mapped to whichever
  specific subclass was actually detected. "Package," "parcel," and
  "delivery" are also mapped this way, all pointing at the detector's "Box"
  class — there's no dedicated "Package" type in the 601-class vocabulary,
  so asking "is there a package at the door" on an uploaded doorbell photo
  works off the same Box detection "where's the box" would. This mapping
  only covers person/people, vehicle, and package/parcel/delivery right
  now; other generic-vs-specific mismatches in the 601 types aren't
  covered, so if a box doesn't appear, try naming the more specific type
  instead (e.g. "dog" instead of "animal").
- **"Box" has its own, lower detection threshold — verified on real
  delivery photos, still not perfect.** Every other class needs 35%
  confidence to appear; "Box" needs only 22%, since real testing found
  stacked cardboard shipping boxes genuinely score lower than the detector's
  usual confidence range even when clearly, correctly located — a model
  weakness on this specific box style (likely trained mostly on gift/product
  boxes), not a code bug. This closes most of the gap but not all of it: a
  stack of boxes carried IN SOMEONE'S ARMS, partially occluded by their own
  body, can still score near zero and go undetected even with the lower
  bar — a different, harder problem than a plainly-visible box sitting on a
  doorstep.
- **A "Detect faces" button highlights every face at once, independent of
  any question.** When a citation's image/frame has at least one confidently
  detected "Human face," a "Detect faces" button appears above it — click it
  to box EVERY detected face at once, regardless of what you asked (or
  whether you asked anything). This is separate from the question-matching
  behavior above: that draws one box for whatever the question named; this
  draws all faces, on demand, with no question needed. It appears on the
  page-1 preview immediately after uploading, without needing to click a
  citation first. The button doesn't appear at all when no face was
  confidently detected in that specific image/frame — not every photo with
  a person in it will show one, since detecting a whole person
  ("Man"/"Woman") and confidently isolating just their face are different,
  independent detections.
- **The confidence label always stays fully inside the image.** The small
  colored tag showing the label and confidence percentage sits inside the
  box's top-left corner rather than floating above it — so it's never cut
  off, even when the detected object is right at the top edge of the frame
  (common for a person/subject filling most of a close-up shot).
- **The detected list can look repetitive or overlapping.** Because the
  601-type vocabulary includes both general and specific categories (e.g.
  "Wheel," "Bicycle wheel," and "Tire" are all separate types), a single
  wheel in a photo can genuinely trigger more than one of these labels at
  once — that's the detector correctly recognizing the same object under
  several valid category names, not a bug repeating itself. Ask "locate
  object" (no specific name) to see the full raw list it found, deduplicated
  labels and all.
- **It only recognizes what's in its 601-type vocabulary.** Something
  outside that list (a specific brand of an item, an unusual object) won't
  be found or positioned, even if the AI's plain-text caption still
  describes it in words. If a "where is X" question gets a generic
  caption-only answer with no position, X likely wasn't one of the 601
  recognized types.
- **"Detect signatures" flags handwritten signatures.** When a citation's
  image/frame has at least one confidently detected signature, "Detect
  signatures (N)" appears in the "Choose an action…" dropdown — pick it to
  draw a pink box (with confidence %) around each one. Useful for scanning a
  contract or form photo for where it was actually signed.
- **"Detect plates" finds vehicle license/registration plates, with a
  one-click reader.** When a citation's image/frame has at least one
  confidently detected plate, "Detect plates (N)" appears in the dropdown —
  pick it to draw a blue box around each one. Each box has its own "Read
  plate" button: click it and the SAME corroborated sharpen+OCR flow behind
  "Sharpen region…" (see the citations section below) runs automatically,
  scoped to exactly that box, no manual dragging needed. That corroboration
  matters here specifically — a real incident on a blurred plate photo saw
  the AI invent a different, entirely fake reading on two separate attempts,
  which is exactly the failure mode "Sharpen region…"'s double-read
  agreement check exists to catch rather than silently trust.
- **"Detect weapons" flags knives, guns, and other weapon classes.** When a
  citation's image/frame has at least one confidently detected weapon
  (Weapon, Knife, Handgun, Rifle, Sword, Bomb, or Missile — ordinary
  kitchen knives are deliberately excluded so photos of a kitchen counter
  don't false-alarm), "Detect weapons (N)" appears in the dropdown — pick
  it to draw a red box around each one. This reuses the same 601-class
  object detector "Detect objects" already runs; no separate model or
  backend endpoint was needed. It's the same general-purpose detector as
  everything else on this page, not a model trained specifically for
  weapons/explosives — treat a hit as worth a closer look, not a certainty.
- **"Crowd density" shows a real headcount, not just a box count.** When a
  citation's image/frame has more than one confidently detected person,
  "Crowd density (N)" appears in the dropdown — pick it to see the actual
  number, not a box overlay (drawing 40+ overlapping boxes on a crowd photo
  would just be visual noise). This number is deliberately NOT the same as
  "Detect objects"'s count: that list caps at 8 detections total across
  every class for box-drawing, so a genuinely busy photo would silently
  undercount there. Crowd density reads the real, uncapped detection count
  instead — still an estimate, and heavy overlap/occlusion in a dense crowd
  (people hidden behind others) can undercount the true number in frame.
- **"Check for tampering" flags possible photo editing.** Where available,
  "Check for tampering (N)" runs three independent statistical checks —
  compression-error analysis (ELA), sensor-noise-texture analysis, and
  (JPEG uploads only) a compression-history check that looks for a region
  whose JPEG quality doesn't match the rest of the photo — and merges them
  into one set of boxes, labeled High/Medium/Low confidence. None of these
  are a trained classifier and none are a certainty — a real edit can still
  be missed, and reflective/metallic surfaces, fine detail like spokes, or
  a glossy sticker can still trip the compression/noise checks. Combining
  three differently-flawed signals catches more real edits (especially on
  a photo that's already been re-saved/re-shared once) without simply
  flagging everything busy as suspicious. Even "High" here means "an
  unusual statistical pattern," not "confirmed edited" — always verify
  visually before trusting a flag. Tampering boxes are click-to-inspect
  only — there's no ✕ shortcut on them the way there is for objects/faces/
  signatures, since checking for tampering is a verification step, not an
  edit workflow.
- **"Possible duplicate" flags a repeat of something already uploaded.**
  If an uploaded image or page closely matches another page already
  uploaded earlier in the same session (a perceptual-hash comparison, not
  just a filename match), "Possible duplicate (N)" appears in the dropdown
  — pick it to see which other source/page it matches and how similar (a
  percentage). Useful for catching an accidental re-upload of the same
  photo, or two documents that share the same embedded image.
- **"Possible hidden data" flags LSB steganography — and can identify the
  actual hidden file, not just a statistical pattern.** Where available,
  "Possible hidden data (N%)" runs the classical chi-square LSB attack
  (checks whether pixel value-pairs are suspiciously equalized, the
  fingerprint of data hidden in the least-significant bit of each pixel).
  Only meaningful on a losslessly-saved image (PNG/BMP/TIFF) — JPEG
  compression destroys LSB data, so a JPEG upload will essentially never
  trigger a true positive. Only runs on images at least 500px on each side:
  below that, the statistic itself becomes unreliable and was found to
  false-positive on completely ordinary small photos, so it's skipped
  entirely rather than shown with a misleading number. Click "Show what the
  computer sees" to view the raw bit-plane the detector reads — it looks
  like static either way (that's the point: a hidden payload doesn't
  visually change the image), so the picture itself proves nothing; the
  confidence number and any signature match below it are the real evidence.
  When the option reads "...— looks like a [file type]," the tool went
  further than the statistical hint: it actually extracted the hidden bytes
  and matched them against known file signatures (ZIP, Windows/Linux
  executables, RAR, 7z, gzip, PDF, or a script). That's a much stronger
  claim — a real recognizable file was found, not just a suspicious
  pattern — though it still isn't proof of anything malicious, only that
  something real is hidden there.
- **"Possible screen/scan pattern" flags a photo taken of a screen or a
  scanned document.** Where available, this looks for a repeating ripple
  hidden in the image's frequency structure — the kind of interference
  pattern (moiré) that shows up when a camera photographs a display or a
  scanned page, rather than a real scene directly. Click "Show what the
  computer sees" to see the image's own frequency-spectrum picture with the
  actual detected pattern circled in red — every photo's spectrum has the
  same smooth cloudy shape in the middle, so only the two circled spots
  matter. A strong hint, not proof: some real photos with fine repeating
  textures (mesh, fabric, a wire fence) can occasionally trigger this too.
- **"Possible same camera" flags two photos sharing a sensor fingerprint.**
  Where available, this compares each photo's camera sensor noise pattern
  (PRNU — Photo Response Non-Uniformity, a real source-camera-identification
  forensic technique, not a look-alike comparison) against every other
  image already uploaded in the same session. A match means two DIFFERENT
  photos were likely taken by the physical same camera — different from
  "Possible duplicate" above, which flags the SAME photo uploaded twice.
  Both photos are resized to a common working resolution before comparing,
  so a heavily cropped or rescaled copy of a photo from the same camera may
  not match even though it genuinely is the same sensor — a real,
  un-worked-around limitation, not a claim of robustness against it.
- **Detected objects and caption details aren't linked to each other.**
  The detector and the AI caption are two separate passes over the same
  image with no shared memory — so a question like "which side is the
  person in the blue jacket on" won't reliably work even if a "Person" was
  detected and the caption mentions a blue jacket, since nothing connects
  that specific detected box to that specific caption detail. The tool will
  say the information isn't available rather than guess.

### Removing and replacing things in an image (Object Remover)
Any citation with a page image — a standalone image/video upload OR a PDF's
own page — can have a region removed (painted over so it blends with the
surroundings) and then optionally have something new put back in its
place. "Draw region," "Download," and "Reset" appear above the image for
any citation; the per-detection ✕ shortcut described below is available
wherever that detection type itself appears (standalone image/video only —
see the object-detection section for which dropdown options need that).

- **You have to open "Choose an action…" and pick a detection first before
  you can remove anything by clicking a box** (standalone image/video
  uploads only — a PDF page doesn't have this dropdown, use "Draw region"
  instead, see below). The dropdown above the image (same one used for
  "Detect objects," "Detect faces," etc) is what actually draws the boxes
  on the image — until you pick one of those options, there are no boxes on
  screen, and therefore no ✕ button to click. Pick any detection option
  from that dropdown first — "Detect objects," "Detect faces," or "Detect
  signatures" all work — THEN click the small ✕ in a box's corner to remove
  that specific region. **"Check for tampering" boxes don't have this ✕** —
  checking for tampering is a verification step, not an edit workflow, so
  those boxes are click-to-inspect only. If you don't want to hunt for the
  right detection, skip the dropdown entirely and use "Draw region" instead
  (below) — it doesn't need a prior detection at all, and works on any
  citation including a PDF page.
- **"Draw region" removes any shape you draw, detected or not.** Click "Draw
  region" (next to the dropdown), then click-and-drag directly on the image
  to trace a freehand shape — release to remove exactly that area. Useful
  for anything the detector didn't recognize, or a shape a box can't
  express (an odd outline instead of a rectangle). Click "Stop drawing" when
  done; the dropdown's boxes become clickable again immediately.
- **Removals chain.** Remove one region, then remove another (via either
  method) — each new removal builds on the already-edited image, so you can
  clear several things one after another without starting over.
- **A "+" appears over every removed region — click it to put something
  back.** Three ways to fill it, as tabs in the small panel that opens:
  - **Text** — type a short label or caption; it's drawn directly onto the
    image, centered in the region.
  - **Image** — pick a file from your device; it's scaled to fit inside the
    region (keeping its own proportions, not stretched) and centered.
  - **AI fill** — describe what should go there (or leave it blank to just
    ask for a natural-looking fill) and an AI image-editing model generates
    it, blended to match the surrounding photo's lighting and style.
- **AI fill takes a few seconds — text and image fill are instant.** Text
  and image fill never leave your browser; AI fill makes a real model call,
  usually done in under 10 seconds, occasionally longer. A "temporarily
  unavailable" message means that one call failed — safe to just try again.
- **AI fill's quality varies call to call.** It's a whole-image editor, not
  a pixel-exact patch — most results blend seamlessly, but it can
  occasionally leave a visible trace of the blank area around whatever it
  added, or make a small unintended change elsewhere (a label re-rendered
  slightly differently). If a result looks off, "Reset" and try again — a
  repeat of the same request often comes out cleaner. Works best when
  what's removed is a smaller region against a photo that's still mostly
  intact, rather than most of the frame.
- **Once a region has something added back, its "+" goes away** — a region
  is filled once (text, image, or AI), not stacked with multiple fills. Hit
  "Reset" (see below) and redo the removal if you want to try a different
  fill for the same spot.
- **"Reset" clears every edit on that image/frame back to the original.**
  Removals and anything added back, all undone at once — appears next to
  "Draw region" only once at least one region has been removed.
- **"Download" saves your edited image/page to your device.** Appears next
  to "Reset" once at least one edit exists — click it to get a PNG of the
  image exactly as currently shown, removals and any added content
  included.
- **"Embed watermark" / "Verify watermark" buttons.** Also always available
  above any citation's own image (same requirement as "Draw region" — a page
  image has to exist). "Embed watermark" downloads a copy of whatever's
  currently on screen (original, sharpened, or edited — respects any prior
  removal/fill/sharpen already applied) with an invisible tag hidden directly
  in the pixel data. "Verify watermark" checks any image — the one on screen,
  or a re-upload of that downloaded file later — and shows a green checkmark
  with the recovered label and a confidence percentage if the tag is there,
  or "No watermark detected" if it isn't. This is unrelated to the
  "Traceable watermark" stamped on shared-session links (see "Sharing a
  session" below) — that's a visible screen-tracing tag added automatically
  to a shared view; this is an invisible, opt-in tag you embed yourself into
  one specific image's pixel data, verifiable later even outside this tool.
  It survives a normal re-save (e.g. re-exporting as JPEG at reasonable
  quality) but breaks if the image is resized, since the tag is tied to the
  image's exact pixel dimensions.
- **Edits are kept in memory for the session, not saved permanently.** Switch
  to a different citation and back and your removals/fills are still there;
  reload the page and they're gone, same as the rest of this tool's
  session-only data.

### Sharing a session
Once you've uploaded a document, a "Share this session" chip appears next
to it. Clicking it warns you first, then gives you a link good for 24
hours. Anyone who opens it lands in a read/chat-only view: they can ask
questions and see citations, but can't upload, delete, or re-share. Three
protections apply automatically to that view, none of which touch your own:
1. **Locked to first opener.** Whoever's network opens the link first is
   the only one it works for afterward — forwarding it to someone else
   won't extend access to them.
2. **PII hidden from the AI and the citations.** Anything the detector
   flags (email, phone, SSN, credit card number) is replaced with a
   placeholder like "[REDACTED EMAIL]" before it reaches the shared
   viewer's AI answers or citation text — the AI genuinely can't repeat
   it back to them, no matter how the question is phrased.
3. **Traceable watermark.** A faint, repeating tag (the link's ID and the
   date) is stamped across the shared view's chat and citations. It can't
   stop someone from screenshotting the page, but it means a leaked
   screenshot can be traced back to which link produced it.

You can cut off access at any time with the "Revoke" button, independently
of deleting the document yourself; the link also stops working on its own
after 24 hours either way. A shared viewer's citation cards work the same
as yours otherwise, but the page-image preview and per-document summary
panel are only available in the tab that did the uploading — the share
link carries chat access, not the full workspace.

### Usage stats
A "Usage stats" button in the header opens a dashboard in a pop-up panel,
right here on this page — it never navigates away or disturbs your
current upload/chat session. It shows total uploads by file type, total
questions asked, average answer time, cache hit rate, and which AI
provider actually served each answer (shown as an interactive donut
chart — hover a slice or its legend entry to see that provider's exact
count and share). It only ever shows aggregate counts, never anything
about what any specific person uploaded or asked. Like every upload on
this tool, the numbers reset to zero the next time this demo server
restarts — nothing here is a permanent record.

### What it can't do
- PDF, standalone images (PNG/JPG/GIF/WEBP/BMP/TIFF), CSV, short videos
  (MP4/MOV/WEBM/AVI/MKV), and standalone audio files (MP3/WAV/M4A/OGG/
  FLAC/AAC) are all supported (CSV rows up to 500, video: up to 6 sampled
  frames — fewer once a real transcript exists — plus an audio transcript
  when present); DOCX and XLSX are not — see the separate Document
  Intelligence tool for DOCX.
- A standalone audio upload doesn't need to be part of a video — it gets
  transcribed on its own, with a player and the same searchable transcript
  as a video's audio track. A "Speech only" warning icon appears since
  music or instrumental audio may transcribe inaccurately (there's no
  speech for it to actually pick up).
- A video's visual understanding only comes from a handful of sampled
  frames, not every frame — something that flashes on screen briefly
  between samples could be missed, even though the audio transcript (if
  present) covers the entire runtime.
- It won't fabricate an answer that isn't in the document/image — if nothing
  relevant is found, it says so instead of guessing.
- Nothing uploaded here is permanent. For document field extraction with
  human-editable results and export, use Document Intelligence instead.

### Your data is not stored anywhere permanently
The original PDF, image, or CSV you upload is never saved — only the
extracted text, table, figure-caption, or image-caption chunks are indexed.
A video is the one exception: its raw file is kept in memory for this
session only, specifically so you can play it back and click-to-seek in
the transcript — capped to only a few videos in memory at once, evicted
immediately when you remove the document, and never written to disk.
Everything here lives only in this server's temporary memory for as long
as it keeps running. There is no database backup, no export of your file
to any other system, and no persistence layer behind this demo. A server
restart (which can happen at any time on this free-tier demo) wipes
everything — every upload, its chunks, and any "shared" copy — with no way
to recover it. Treat this as a scratch space for trying the tool, not a
place to keep anything you need later.

## What problem it solves

A language model knows what was in its training data, up to a cut-off, and
nothing about your PDF. Ask it about your document and it will either refuse or
invent — and inventing is the dangerous option, because a fabricated answer
reads exactly like a real one.

**Retrieval-Augmented Generation** fixes this by changing the question. Instead
of *"what do you know about X?"* it becomes *"here are the relevant passages
from this document — answer using only these, and say where each claim came
from."* The model stops being a knowledge store and becomes a reader.

The **multimodal** part is what makes this tool harder than a standard RAG
demo. A real document is not a stream of paragraphs. The number you want is in
the third column of a table, or it is the height of a bar in a chart, or it is
in a photograph's caption. A pipeline that only indexes prose is blind to
exactly the content people put in documents because it is important.

## How it works, step by step

### Ingest

1. **Parse the PDF** into three kinds of content: **prose, tables and figures**
   — the "3 chunk types" on the tool's card.
2. **Tables are kept as structure**, not flattened into a word stream, so which
   number belongs to which row survives.
3. **Figures get a written caption** from a vision model, which is what makes a
   chart searchable at all: you cannot embed a picture into the same space as a
   question, but you can embed a sentence describing it.
4. **Prose is chunked** at **450 words with 45 words of overlap**.
5. **Everything is indexed twice** — as embeddings in ChromaDB, and as tokens in
   a BM25 index.

### Query

6. **Route.** A cheap model decides whether the question is *simple* or
   *complex*.
7. **Decompose,** on the complex route only, into sub-questions.
8. **Retrieve** — dense and sparse in parallel, merged.
9. **Grade.** A model judges whether the retrieved chunks actually help:
   `good`, `rewrite`, or `websearch`.
10. **Loop or escalate.** `rewrite` reformulates the query and retrieves again;
    `websearch` goes outside the document.
11. **Generate,** with the chunks as context and citations required.
12. **Check the answer against its sources** and report how grounded it is.

## The model or algorithm

### Why the overlap exists

450-word chunks with 45 words of overlap. The overlap is not padding — it is
insurance against the boundary problem. A fact stated across a chunk boundary is
split in half, and neither half retrieves well. Ten percent overlap means every
boundary region appears whole in one of the two chunks.

### Hybrid retrieval — dense and sparse

**Dense retrieval** embeds the question and finds the nearest chunk vectors.
It matches *meaning*: "how do I stop overfitting" finds a passage about
regularisation with no shared words.

**BM25** is the classic sparse method — a bag-of-words score built on term
frequency and inverse document frequency, with two refinements that matter:
term frequency **saturates**, so the tenth occurrence of a word adds far less
than the second, and the score is **normalised for document length**, so a long
chunk does not win by containing more words.

They fail in opposite directions, which is exactly why both are used. Dense
retrieval is bad at rare exact tokens — a part number, an error code, an unusual
surname — because those are poorly represented in the embedding space. BM25 is
bad at synonyms. Neither is reliably better; the union is much better than
either.

### Reciprocal Rank Fusion

Merging two ranked lists is not obvious, because their scores are not
comparable: a cosine similarity of 0.82 and a BM25 score of 14.3 live in
different units, and normalising them requires assumptions that do not hold.

RRF sidesteps this by **throwing the scores away and using only the ranks**:

```
score(d) = Σ over lists of  boost × weight / (rank + k)      k = 60
```

A document ranked 1st contributes 1/61; ranked 2nd, 1/62. The differences are
small and the curve is flat, which is the point — it says *"being near the top of
several lists matters more than being at the very top of one"*, and it cannot be
fooled by one retriever's score scale. `k = 60` is the value from the original
paper, and its effect is to flatten the curve so ranks 1 and 5 are not wildly
different.

This implementation adds two things to the standard formula.

**A per-chunk-type boost.** Table, figure and image chunks are structurally
short — a caption, or a table's own text — so they are weaker dense *and* BM25
matches than verbose prose even when they are the right answer. The boost
multiplies their contribution to correct for a disadvantage that comes from
their shape rather than their relevance. Without it, the multimodal content this
tool exists to surface loses to paragraphs.

**A per-list weight,** so a question classified as visual can trust the vision
signal's votes more. The docstring is careful about what this is: *"a tilt, not
a filter — an unlisted label defaults to 1.0, never zero, so a wrong
classification degrades gracefully instead of blinding the pipeline to a
signal."* That is the right instinct for any routing heuristic — a
misclassification should cost you some ranking quality, never a whole retrieval
channel.

### Why was this cited? — the retrieval trace

Optionally, fusion records **one label per input list**, so each merged chunk
carries a trace: this chunk was rank 3 in dense with score 0.71 and rank 1 in
BM25 with score 12.4, its type boost was 1.3, and its hybrid score before any
reranking was 0.031.

This is harder than it sounds because the pipeline **overwrites `score`**
repeatedly — an outer fusion pass, then a reranker. So the trace preserves
`hybrid_score` separately, and the labels argument is deliberately **omitted on
outer fusion passes** so an inner pass's trace survives instead of being
replaced. Threading intermediate values through a pipeline whose later stages
overwrite its earlier ones is the actual engineering problem, and the solution
is to give the value you want to keep a name nothing else writes to.

### The agent loop

Five nodes, in a LangGraph state machine:

| Node | Job |
|---|---|
| **router** | simple or complex? |
| **decompose** | complex only — split into sub-questions |
| **retrieve** | hybrid retrieval |
| **grade** | `good` / `rewrite` / `websearch` |
| **rewrite** | reformulate and go round again |

Two details are worth pointing at.

**The grader sees truncated chunks.** Each is cut to 200 characters, and the
comment says why: it saves roughly 400 tokens per call. The grader is deciding
*relevance*, not answering — and the first 200 characters are enough for that.
Cheap where cheap is sufficient, so the budget goes to the generation step that
needs it.

**Every node fails toward "continue".** The router defaults to `complex` if it
errors, the grader defaults to `good`, the rewriter falls back to the original
query, and the decomposer falls back to the unsplit question. Each failure is
logged. The principle: **a meta-step that fails should degrade the answer's
quality, never prevent an answer.** The alternative — a rate-limited router
taking down the whole query — is far worse than one that occasionally takes the
expensive route unnecessarily.

**CRAG** is the escalation. When the grader says the topic is outside the
knowledge base, the pipeline searches the web (Tavily, with a DuckDuckGo
fallback) and cites those results instead — better than answering from nothing.

### Groundedness — checking the answer against its sources

After generation, the answer is split into sentences, and each is embedded and
compared against the source chunks. A sentence with no similar source sentence
is flagged as ungrounded.

**Two real bugs shaped this, and both are recorded in the code.**

**Sources are split into sentences too, not embedded whole.** A car photo's
chunk mixed a long appearance description with one short trailing spatial fact.
Embedding the whole chunk as one vector averaged that fact away under the longer
unrelated text — so the correct answer *"the car spans most of the frame"*
scored *below* an unrelated bicycle photo whose chunk happened to be mostly
spatial content already. Splitting the source into sentences lets a short
factual answer match its one relevant source sentence directly instead of an
entire diluted paragraph. **The general lesson: an embedding of a long mixed
passage is an average, and averages hide short specific facts.**

**Non-English answers were being falsely flagged.** The similarity threshold was
calibrated on English; a correct Hindi answer grounded in an English source
scored 0.185 — well inside "unsupported" — purely because of the script gap. The
fix is a script-mismatch check: if the answer is largely non-ASCII and the
sources are not, groundedness returns `None` rather than a misleading low score.
Refusing to score is the honest option when the measure does not apply.

The thresholds themselves were calibrated against measured examples, not chosen:
sentences genuinely paraphrasing their source scored 0.44–0.94; fabricated
unrelated sentences scored 0.10–0.36.

## Why these choices

**Why embedding similarity for groundedness rather than an LLM judge.** It costs
nothing extra and adds no latency, and the docstring is explicit that the
trade-off is some false positives — a correct sentence phrased very differently
also scores low. It is also written so that swapping in an LLM judge later only
needs to preserve one function's signature.

**Why the meta-calls use the cheapest model.** Routing, grading and rewriting
are one-word decisions. Spending the good model on them and the cheap one on the
answer would be exactly backwards.

**Why captions for figures rather than image embeddings.** A caption lives in
the same text space as the question, so it retrieves with the same machinery as
everything else. No second index, no cross-modal embedding model.

**Why table structure is preserved.** Flattening a table into words destroys the
row-column relationship, which is the only thing that makes a number in a table
meaningful.

## How to read the output

- **Read the citation, not just the answer.** The page reference is the point of
  the whole system.
- **A low groundedness score means check it** — the answer contains sentences
  that do not match anything retrieved. It does not prove the answer is wrong.
- **No groundedness score at all** can mean the answer was in a different script
  from the sources, where the measure does not apply.
- **A cited table or figure** means the answer came from structured or visual
  content, which is the tool working as intended.
- **The retrieval trace answers "why this chunk"** — whether it won on meaning,
  on exact words, or on both.
- **A web-search citation** means the grader decided your document did not cover
  the question.

## Limits

- **Retrieval quality is the ceiling.** If the right chunk is not retrieved, no
  amount of model quality recovers it. Most "the model got it wrong" cases in
  RAG are retrieval failures.
- **Chunking splits arguments.** 450 words with 45 of overlap handles the
  boundary case, not a claim spread across three pages.
- **Figure captions are a lossy summary.** What the vision model did not mention
  is not findable.
- **Groundedness is similarity, not entailment.** A correct paraphrase can score
  low; a fluent sentence that reuses source vocabulary while stating the
  opposite can score high.
- **The router and grader are heuristics** that fail toward continuing, so a bad
  classification costs money or quality, not an answer.
- **CRAG's web results are unvetted.**
- **Multi-hop reasoning is limited** to what decomposition catches.

## Likely interview questions

**"Why hybrid retrieval instead of just embeddings?"**
Because they fail in opposite directions. Dense retrieval matches meaning but is
bad at rare exact tokens — part numbers, error codes, unusual names — since those
are poorly represented in the embedding space. BM25 nails exact terms and is
blind to synonyms. Neither dominates, so the union beats both, and the only real
question is how to merge two ranked lists whose scores are not comparable.

**"How do you merge them, then?"**
Reciprocal Rank Fusion — throw the scores away and use ranks: sum `1/(rank + 60)`
across lists. It is scale-free, so a cosine similarity and a BM25 score never
have to be reconciled, and the flat curve encodes "near the top of several lists
beats top of one". I added a per-chunk-type boost on top, because table and
figure chunks are short and therefore structurally weaker matches than prose
even when they are the right answer.

**"How do you know the model isn't hallucinating?"**
Two things. Citations, so every claim points at a chunk a person can check. And
a groundedness score: split the answer into sentences, embed each, and compare
against the source sentences — anything with no similar source is flagged. It is
similarity rather than entailment, so it has false positives, and I would say so
rather than present it as a hallucination detector.

**"What was the hardest bug in this?"**
Groundedness scoring a correct answer as unsupported. A photo's chunk mixed a
long appearance description with one short spatial fact; embedding that whole
chunk as one vector averaged the fact away, so the right answer scored below an
unrelated photo. The fix was to split the *source* into sentences as well as the
answer. The lesson generalises: an embedding of a long mixed passage is an
average, and averages hide short specific facts.

**"How do you handle a table in a PDF?"**
Keep its structure rather than flattening it into text, index it as its own
chunk type, and boost that type during fusion so its shortness does not cost it
the ranking. Flattening is the common shortcut and it destroys the row-column
relationship, which is the only thing that makes a number in a table mean
anything.

**"Your router misclassifies a question. What happens?"**
It takes the wrong path and costs some quality or some money, and that is
deliberate. Every meta-node fails toward continuing — the router defaults to the
complex route, the grader to `good`, the rewriter to the original query — and the
list weights are a tilt rather than a filter, with unlisted labels defaulting to
1.0 rather than zero. A misclassification should never blind the pipeline to a
retrieval channel or stop an answer being produced.
