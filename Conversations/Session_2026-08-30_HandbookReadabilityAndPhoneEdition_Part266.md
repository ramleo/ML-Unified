# Session 2026-08-30 (Part 266) — reading the handbook: phone type, a phone PDF, coloured sections, and a wrong-repo push

Continues Part 265 (`Session_2026-08-30_HandbookDeepChapters_Part265.md`),
which finished the book's content — 50 of 50 deep chapters. This log is about
**reading** what that produced: nothing here changes a word of the handbook's
text.

It also records a real mistake I made mid-session — 49 MB of the owner's
untracked files pushed to the wrong repository — and how it was undone.

---

## 0. Where things stand in one paragraph

The handbook now reads properly on a phone, in the browser and as a PDF. Two
sections of every chapter are tinted so they can be found by scrolling. The
typeset view has a way out of it. A separate **phone edition** of the PDF is
typeset at 90 × 150mm so it is legible on a handset without zooming. Four
commits in ml-portfolio, all pushed. One commit in ML-Unified cleans up the
wrong-repo push and gitignores the artefacts that caused it.

---

## 1. The commits

| Hash | Repo | What |
|---|---|---|
| `fa200a4` | ml-portfolio | phone type size, exit from the typeset view, tinted sections |
| `17bfa00` | ml-portfolio | the section tints reach the PDF too |
| `41cddfc` | ml-portfolio | the phone edition of the PDF; web type raised again |
| `973509e` | ml-portfolio | contents column aligned; the PDF no longer repaints the site |
| `3c6b2df` | ML-Unified | the owner's real pending changes committed; generated artefacts ignored |

`fdaf6ce` in ML-Unified is **not** in that table on purpose — see §5.

---

## 2. What the owner asked for, in order

1. Is the handbook's font readable after a PDF download, or is it already ideal?
2. On a phone the text is too small and straining.
3. After clicking "Download as PDF" there is no way back — the browser's back
   button is the only exit.
4. Colour some sections so it looks nicer, in colours that are easy on the eyes.
5. Where is the colour? (Looking at the PDF, which had none.)
6. The phone font is still small — 16–18px is the recommended range.
7. *"I want to read the downloaded handbook PDF on a phone, not the handbook
   from the website directly."* — the sentence that changed the whole problem.
8. What is this indexing? (The contents column had broken.)
9. Why does it switch to the light theme when I click the phone PDF?

---

## 3. The four fixes

### 3.1 Type size on the web page

`.hb-body` was set once, at `0.95rem` in `--text2`, and a phone got exactly what
a desktop got. Small **and** low-contrast is what made it tiring, so both change
under 640px: full-strength `--text`, and a size that went to `1.05rem` and then
— when the owner said it was still small — to `1.15rem`.

Measured at a 390px viewport: **15.2px → 16.8px → 18.4px**. The published
guidance for reading on a handset is 16–18px; the first bump landed at the
bottom of that range, the second at the top. Headings, blockquotes and tables
moved with it, and tables now scroll inside their own box instead of pushing
the page sideways.

### 3.2 A way out of the typeset view

Clicking "Download as PDF" adds `bk-paginated` to `<body>`, and `10-print.css`
hides `nav`, `footer`, `.hb-head` and `.hb-body` behind it. Nothing ever removed
the class again, so **every element that could take the reader back was hidden**
— the browser's back button was the only exit.

There is now a "Back to the handbook" button. It is **portalled to `<body>`**,
because its natural parent `.hb-head` is one of the elements pagination hides;
rendering it in place would hide it exactly when it is needed. Leaving also
empties `#bk-pages`, so the next PDF is typeset fresh rather than appended.

### 3.3 Colouring the sections

Every chapter has the same seven headings, so there is a real spine to colour
against rather than decoration to sprinkle on. Two of them — **Limits** and
**Likely interview questions** — are looked up rather than read through, and
those are the two that got a ground of their own.

CSS cannot select "this heading and everything under it until the next one",
and chapters are flat siblings in the finished book, so the wrapper had to be
generated: `wrap_sections()` in `build-handbook.py` emits a `div.bk-sec` around
each. Exactly **100 wrappers, 50 of each, with no change to any chapter text**.

Warm sand for the caveats, soft slate for the questions, the same pair in all
fifty chapters so it reads as furniture and never competes with the part colour
on the chapter title above. Both around 5% strength.

**Literal `rgba`, not `color-mix()`** — a comment already in that file records
that this build rewrote a `color-mix()` wrongly once before.

### 3.4 The phone edition of the PDF

This is the fix that mattered most, and it was aimed at the wrong target until
the owner said the sentence in §2.7. Everything before it was about the
*website* on a phone. The actual complaint was the *downloaded PDF* on a phone.

**The page was the problem, not the font.** A4 is 210mm wide against a phone's
~68mm, so the whole page is shown at about **0.31 scale** and 10.5pt type
renders at an effective **3.3pt**. No point size fixes that.

`public/book-phone.css` typesets the same book at **90 × 150mm with 11pt type**.
The phone then shows the page at about **0.75 scale**, so type renders at an
effective **8.3pt** — paperback size, readable without zooming.

| | A4 edition | Phone edition |
|---|---|---|
| Page | 210 × 297mm | 90 × 150mm |
| Type | 10.5pt | 11pt |
| Text column | 170mm | 78mm |
| Effective size on a 68mm screen | **3.3pt** | **8.3pt** |
| Pages | 345 | 1,165 |

It is one override loaded **after** `book.css`, not a second stylesheet, so page
size and the display sizes that depend on it are the only things stated twice.
Running heads are dropped — 7mm of a 150mm page is a lot to spend on a line the
reader already knows — and the folio stays, because the contents page needs it.

---

## 4. Two bugs the narrow page exposed

Both had been latent in the A4 edition and were only visible once the column
narrowed to 78mm.

### 4.1 The contents column staircased

Two folios landed on one row, another row had none, and the whole column
stepped leftward instead of aligning to the right margin.

The folios were **right floats**. A right float that does not fit its line does
not stay put — it drops, and consecutive ones stack against each other. A4's
170mm column always had room, so it never showed.

Now a flex line: the title, a leader that absorbs the slack, then the folio
pinned right as its own flex item. **A flex item cannot leave its line**, so
the failure mode is removed rather than made less likely. Verified: all 56 rows
share a right edge; every row has its folio.

### 4.2 Asking for a PDF repainted the whole site

`book.css` opened with an unscoped `html, body { color: #1a1a1a; background:
#fff }`. Paged.js injects the stylesheet into the **live document**, so the
reader's dark theme was overwritten the moment typesetting began, the
handbook's own near-white body text landed on a white ground and became
invisible, and it stayed that way after leaving the book view because the
stylesheet is never removed.

Everything document-level is now scoped to `.pagedjs_page`.

**The first attempt at that was wrong and is worth keeping:** I guarded the body
rule with `@media print`, assuming that would confine it to actual printing. It
did not. **Paged.js is itself a print-media processor and hoists print rules out
of their query**, applying them to the live page exactly as the unguarded rule
had. The check caught it — the injected rule was found in the document with
`data-pagedjs-inserted-styles`. `10-print.css` owns sheet-level colours instead,
being a stylesheet the browser evaluates only when it really prints.

---

## 5. The mistake: 49 MB pushed to the wrong repository

Recorded in full because the lesson is a process one, not a technical one.

**What happened.** The shell's working directory silently reverted from
ml-portfolio to ML-Unified between one Bash call and the next. I ran `git add
-A` and committed. That swept up all 17 of the owner's pre-existing untracked
files — including `services/ml-api/data/chroma_db/chroma.sqlite3` at **49 MB**
— and pushed them to `ML-Unified/main` as `fdaf6ce`, under a commit message
about the handbook. Meanwhile the actual handbook work was still uncommitted in
the other repo.

**Why it mattered beyond the noise.** `chroma.sqlite3` is a live database that
changes whenever the RAG tool writes. Once tracked, every future commit touching
it would add another 49 MB blob.

**The recovery.**

1. `git reset --mixed 7e93edf` — all 17 files back untracked, nothing deleted.
2. The real work committed in ml-portfolio with **explicit pathspecs** and
   `git -C <absolute path>`.
3. `3c6b2df` prepared locally: the four changes actually worth keeping
   (`CLAUDE.md` rule 5, the ml-vision Dockerfile and README, ml-sql
   requirements) plus a `.gitignore` for `catboost_info/`, `data/chroma_db/`,
   `models/ci-test-*` and `schemas/ci-test-*.json`.
4. The owner ran the force-push — **the tool's permission classifier blocked it
   twice for me, with no approval prompt**, so it could only be done by hand.
   One command then did both jobs: dropped `fdaf6ce` and landed `3c6b2df`.

**Verified after:** `origin/main` = `3c6b2df`, `fdaf6ce` no longer an ancestor
of `main`, **0** ChromaDB files tracked on the remote.

**The rule, now in memory as `feedback-never-git-add-all`:** never `git add -A`
or `git add .`. Stage explicit paths, prefix every git command with `git -C
<absolute repo path>`, and confirm `remote -v` and `status` in the same call as
the commit. **Bash working directory does not reliably persist between calls in
this environment.**

The three `test_*` files at the repo root were left untracked rather than
ignored. They are from July sessions — a script comparing Groq / Gemini / Cohere
on invoice extraction, plus its two fixtures — and were written by a Claude
session, not the owner. That is the owner's call to make, not mine. Note the
script is hardcoded to the live Space and makes nine billed API calls if run.

---

## 6. `build-handbook.py` had to be split

It was 368 lines before this session, and `wrap_sections()` took it to 403 —
past the project's 400-line limit. The five reader functions moved to
`scripts/handbook_sources.py` (155 lines); `build-handbook.py` is 266 and keeps
everything that decides the shape of the book. The division is real rather than
an arbitrary cut: that file only *reads*, this one *assembles*.

It should have been split **before** the feature, per rule 3. It was not,
because the line count was checked on the file I was about to edit but the
threshold — modularise anything over 350 — was not applied until the hard limit
was already crossed.

---

## 7. How each change was verified

No screenshot evidence in this session: **screenshots render blank on this
machine**, which is already in memory as a known limitation. Everything below
is computed styles and DOM measurement read from a live production build, which
for geometry and colour is stronger evidence than a picture anyway.

| Claim | How it was checked |
|---|---|
| Phone type is 18.4px | `getComputedStyle` at a real 390px viewport |
| 390px viewport is actually 390px | `devicePixelRatio` is 0.5 here, so `setViewportSize(195)` is needed for 390 CSS px — the first attempt silently measured at 780 |
| 100 section wrappers, no text changed | diff of the regenerated `handbook.md`: 100 divs, 400 blank lines, nothing else |
| Exit button works | clicked through: 342 pages built, button found on `<body>`, click restored nav/footer/body and emptied `#bk-pages` |
| Tints reach the PDF | computed `#fdf5ea` / `#f2f5f8` inside `#bk-pages`, `print-color-adjust: exact` |
| Phone page geometry | measured 90 × 150mm, 78mm text column, body resolving to 11pt |
| Contents aligned | all 56 rows share a right edge; three long titles wrap, which is expected at 78mm |
| Theme survives | body background sampled every 600ms for 7.5s of typesetting: `rgb(10,15,30)` throughout, restored on exit |
| A4 unaffected | 210 × 297mm, 345 pages, Georgia, running heads present, tints intact |
| Nothing over 400 lines | `./scripts/check-file-length.sh` — 628 files |
| Handbook not drifting | generator rerun produces an identical file |

---

## 8. Things worth carrying forward

- **A "font too small" complaint about a PDF is usually a page-size problem.**
  Ask which artefact is being read before changing type. Two rounds of work here
  went into the website when the owner was reading the downloaded PDF.
- **Paged.js injects its stylesheets into the live document.** Anything in
  `book.css` that is not scoped to `.pagedjs_page` will hit the real site, and
  `@media print` is not a guard — Paged.js hoists print rules out of their query.
- **Right floats are the wrong tool for a contents leader.** They escape their
  line when space runs short. Flex cannot.
- **`devicePixelRatio` is 0.5 in this Playwright setup**, so viewport widths
  must be halved to hit a given CSS width. The first mobile measurement was
  taken at 780 CSS px and looked like a failed media query.
- **Screenshots are blank on this machine.** Verify with computed styles and
  measured geometry.
- **Never `git add -A`.** See §5.

---

## 9. Standing constraints unchanged

Rules 1–5 in `CLAUDE.md` still hold, plus: ask before every commit, only delete
files created in the session and named individually, never batch live calls to a
paid API for self-verification, no file over 400 lines, no emoji as icons,
always push after committing, always report the short hash.
