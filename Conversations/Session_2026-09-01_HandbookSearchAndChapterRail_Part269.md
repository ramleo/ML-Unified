# Part 269 — Handbook search and a chapter rail

**Date:** 2026-09-01
**Repos touched:** `ml-portfolio` only. **No backend file changed, so no HF Space
upload applies.**
**Commits:** `2c10e82`, `f5abd25`, `4894b39`, `43ef795` — all pushed to `main`.

---

## 0. Where things stand in one paragraph

The handbook is 50 chapters in a single 387,000-pixel page, and until today the
only way around it was a contents list. It now has a find bar that reports how
many hits are in which chapter, and a rail down the right edge that can be
dragged to scrub or clicked to jump. Getting there took four attempts at one
bug that three separate verification passes said did not exist — the search bar
was pinned exactly where it was supposed to be and completely invisible,
because the fixed navbar was painting over it. That is the lesson of this
session, and it is worth more than the feature.

---

## 1. The commits

| Hash | What |
|---|---|
| `2c10e82` | search bar, contents indexing, substring matching, chapter rail, both positioning fixes |
| `f5abd25` | clear (×) button |
| `4894b39` | undo history for the query |
| `43ef795` | Cmd-K / Ctrl-K hint |

---

## 2. What the owner asked for, in order

1. *"Handbook backlog search bar"* — pick up §13.1 from Part 268.
2. Four defects after looking at the result: the bar disappears on scroll;
   `security & trust` is not found in the contents; case and partial search;
   the scrollbar is impossible to grab.
3. *"need a cross button in search bar to clear the content"*.
4. *"when i type something and remove it, then when i press undo button, it
   doesnt work, why? it is cumbersome to type again"*.
5. *"it is not only about macbook, undo should work on windows computer as well"*.
6. A hint for the focus shortcut.
7. Update the Part 268 log and write this one.

---

## 3. The design, and the two decisions worth keeping

**Search the DOM, not a shipped index.** All 50 chapters are already
server-rendered into `.hb-body`, so a client-side walk costs nothing extra. A
build-time JSON index would have meant downloading the 17,406-line handbook a
second time.

**Paint with the CSS Custom Highlight API, never `<mark>`.** This is not a
stylistic preference. `HandbookActions.makeBook()` feeds
`document.querySelector(".hb-body").innerHTML` straight to Paged.js when a
reader asks for the PDF. Any element injected into the article for highlighting
would be typeset into their book. `CSS.highlights` paints `Range`s without
touching the DOM at all. Verified directly: zero `<mark>` elements in `.hb-body`
while 20 ranges were painted.

Files, all well under the 350-line threshold:

| File | Lines |
|---|---|
| `src/app/handbook/handbookIndex.ts` | 169 |
| `src/app/handbook/HandbookSearch.tsx` | 256 |
| `src/app/handbook/HandbookRail.tsx` | 140 |
| `src/app/styles/12-handbook-search.css` | 174 |
| `src/lib/search/wordMatch.ts` | 102 (moved) |

---

## 4. THE BUG THAT TOOK FOUR ROUNDS — and why it was missed

The owner said three separate times that the search bar disappeared when
scrolling down. Twice they were contradicted, on the strength of a measurement.

**What was measured:**

```js
window.scrollTo({ top: 30000 });
document.querySelector(".hb-search-bar").getBoundingClientRect().top   // → 0
```

Pinned at the top of the viewport at 2,000 / 30,000 / 120,000 / 380,000 px.
The assertion was true at every depth. It was also irrelevant.

**What was actually wrong.** `src/components/Navbar.tsx` renders inline
`position: fixed; top: 0; height: 60; zIndex: 100`, and once scrolled it paints
a solid `--bg-nav` background. The search bar was pinned at `top: 0`
*underneath* it.

**The check that would have caught it on the first pass:**

```js
const r = el.getBoundingClientRect();
document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
// → NAV, not the bar's own input
```

Geometry proves position. Only hit-testing proves visibility.

**Why it took so long to get there.** Local headless screenshots come back
blank on this machine — three attempts, three uniform dark rectangles — so
there was no picture to look at, and DOM measurement was treated as a
sufficient substitute. It is not. The fix for *that* is in §5.

There was a second, earlier positioning fault in the same area: the page
wrapper's `overflow-x: hidden` made it a scroll container, and a scroll
container silently disables `position: sticky` for every descendant.
`overflow-x: clip` cuts the same overflow without creating one. So the bar
genuinely was broken at first — then was fixed, and stayed invisible for a
completely different reason, which is exactly why the owner's repeated report
kept being read as a stale cache.

### The correction

`.hb-search` now pins at `top: var(--hb-nav-h)` (60px). The rail is inset the
same way, or its first ticks sit behind the navbar and cannot be clicked.
Re-verified with `elementFromPoint` at the bar's centre: returns
`INPUT.hb-search-input` at 1,500 / 60,000 / 200,000 px.

---

## 5. The screenshot problem, and its solution

Headless Chromium on this machine returns blank images for ordinary DOM on a
`next start` build. Known, already recorded — but only ever with *substitutes*
(geometry, `innerText`, computed styles) and no workaround.

**There is a workaround, found this session:**

```js
const b = await chromium.launch({ channel: "chrome", headless: false });
```

Same page, same server, same viewport — headless blank, headed correct, first
try. The Playwright MCP browser is the headless one, so this needs a throwaway
`.mjs` run **from inside the repo** (Playwright resolves from `node_modules`;
it will not run from the scratchpad).

Worth the extra few seconds, because two defects were invisible to every DOM
assertion and obvious in one headed screenshot:

- the bar rendering behind the navbar (§4);
- content bleeding through the bar's 60%-opacity `--bg-glass` background — the
  chapter's coloured left rule showed straight through it. Now `--bg-nav`,
  matching the navbar above it.

A third was caught the same way: a transparent 0.4rem gap above the "Where"
panel leaked one clipped line of chapter text, which reads as a rendering
fault. Closed.

---

## 6. A third thing only visible, never measurable

`color-mix()` is **flattened to its first argument by this build**. The
stylesheet resolved as:

```
::highlight(hb-hit) { background: var(--hb-hue); }   /* the 22% is gone */
```

So every hit painted at full strength and the current one was
indistinguishable from the rest. `09-handbook.css:155` already carried a
warning about this exact rewrite; it was not heeded when writing the new file.
Now literal `rgba(251, 191, 36, 0.32)` for hits and solid `#fbbf24` for the
current one.

Amber rather than `--hb-hue`, deliberately: that variable is the *part* colour,
four different values down the book, so highlights would have changed colour by
chapter and collided with the rules and headings already drawn in it.

---

## 7. The four reported defects

### 7.1 "Security & Trust" not found in the contents

Self-inflicted. The contents list had been **deliberately excluded** from the
index, on the reasoning that it only repeats the 50 chapter titles and would
give every title search a duplicate hit. That missed the point: the contents is
where a reader searching for a chapter *wants* to land, and a hit there is a
navigation result, not a duplicate. Now indexed and labelled `Contents`.

A second cause underneath it: `and` and `or` are now skippable connectors. The
book prints `&`, which is not a word character and never reaches the index at
all, so a typed "and" had nothing to match against.

| Query | Result |
|---|---|
| `security & trust` | 3 · Contents, Part 4 · Security & Trust, Ch 50 |
| `security and trust` | 3 · same |
| `Security & Trust` | 3 · same |

Part groups also read `Part 4 · Security & Trust` now rather than bare
`Part 4` — a part page splits its name across an `h1` and an `h2`, and reading
the `h1` alone labels the group with nothing useful.

### 7.2 Case and partial matching

Case already worked and was verified — the perception that it did not was a
side effect of 7.1. **Substring was a real gap**: matching was prefix-only, so
`curity` found nothing in `security`. Now `curity` → 66 hits in 23 chapters,
`ntropy` → 106 in 6.

Added as an **opt-in flag** on `wordsMatch`, not a behaviour change.
`wordMatch.ts` moved to `src/lib/search/` this session because two features now
use it, and widening its net underneath the Multimodal RAG transcript panel
would be exactly the shared-infrastructure trap already recorded in
`feedback_shared_infra_hidden_assumptions`.

### 7.3 The scrollbar is impossible to grab

Inherent, not a defect: the page is 387,000px tall, so the thumb is a few
pixels. Restyling the scrollbar would not fix the precision problem.

Built a chapter rail instead — 44px wide, full height, fixed to the right edge.
54 ticks (50 chapters + 4 parts, drawn heavier), an amber marker for the
current position, chapter name on hover, and the whole strip is draggable to
scrub. Verified: clicking the Chapter 50 tick puts its heading at viewport
`top: 0`; a press at 25% down the rail scrolled to `96,396` against an expected
`96,396`.

### 7.4 No way to clear the field

`type="search"` draws a native cancel button, but the stylesheet suppresses it
(`-webkit-search-cancel-button`) because it fought the pill layout — leaving no
way to empty the field but selecting the text or knowing about Escape. An
explicit `×` now, inline SVG per the no-emoji rule, rendered only when there is
something to clear, sitting with the count it clears rather than beside the
step arrows. Escape routes through the same `clear()` so the two cannot drift.

---

## 8. Undo — why it was broken, and what "broken" meant

> *"when i type something and remove it, then when i press undo button, it
> doesnt work, why? it is cumbersome to type again"*

Not a bug that was introduced; a consequence of the field being a **controlled
React input**. React reassigns `value` on every keystroke, and a programmatic
assignment discards the browser's own undo stack for that field. The clear
button does the same. There is no configuration that restores it — the stack
has to be kept by hand.

Now: 50 steps, `Cmd-Z`/`Ctrl-Z` undo, `Cmd-Shift-Z`/`Ctrl-Shift-Z`/`Ctrl-Y`
redo.

Two details worth keeping:

- **Steps snap to the existing 150ms search debounce**, so one undo takes back
  a burst of typing rather than a single character — the way native undo groups
  by word.
- **An undo is not recorded as an edit itself**, or `Cmd-Z` would toggle
  forever between the same two values.

Undo re-runs the search rather than only restoring the text:

| Action | Field | Highlights |
|---|---|---|
| typed `entropy` | `entropy` | 106 |
| clicked × | `""` | 0 |
| **Cmd-Z** | `entropy` | **106** |

### 8.1 The Windows correction

The owner pushed back: *"it is not only about macbook."* The keys had been
bound on `e.metaKey || e.ctrlKey` from the start, so no code changed — but only
the Mac half had been **tested**, and "it should work" is not evidence.

Re-tested in real Chrome, every step logged:

```
== redo via Ctrl+Shift+Z ==          == redo via Ctrl+Y ==
   typed        "optuna"  hits=21       typed        "optuna"  hits=21
   clicked x    ""        hits=0        clicked x    ""        hits=0
   Ctrl+Z       "optuna"  hits=21       Ctrl+Z       "optuna"  hits=21
   redo         ""        hits=0        redo         ""        hits=0
   Ctrl+Z again "optuna"  hits=21       Ctrl+Z again "optuna"  hits=21
```

The first attempt at this test omitted the post-clear row, which made the
result ambiguous — it could not distinguish "undo worked" from "the clear never
happened". It was re-run with every step captured rather than reported as-is.

---

## 9. The Cmd-K hint

`Cmd-K` / `Ctrl-K` had focused the bar since the first commit, but nothing said
so, which makes it a shortcut only someone who already guessed would find. A
keycap now sits in the empty field showing the right key for the reader's
platform, and clears once there is a query.

The platform read goes through `useSyncExternalStore` with an **explicit empty
server snapshot**. The first attempt set state in an effect; ESLint's
`react-hooks/set-state-in-effect` rejected it, and it would also have risked a
hydration mismatch. Verified with a spoofed Windows user-agent that both
branches render (`⌘K` and `Ctrl K`) and that neither logs a hydration error.

---

## 10. How each claim was verified

Match counts were computed independently from `handbook.md` with a Python
script using the same tokenizer the code uses, then compared to what the page
reported:

| Query | Expected | Page |
|---|---|---|
| `quantile` | 9 | 9 |
| `optuna` | 20 | 20 |
| `entropy` | 104 | 104 |
| `held out` (phrase) | 20 | 20 |

The first run of that script disagreed on `quantile` — 8 vs 9. The code was
right and the script was wrong: Python's `\w` treats `_` as a word character,
so `bin_quantile` stayed one token, while the browser's `[\p{L}\p{N}]+` splits
it. Re-run with `[^\W_]+` it matched exactly. **The discrepancy was chased down
rather than waved off as a rounding difference.**

(`optuna` now returns 21, not 20 — the extra hit is the contents entry, which
is the 7.1 fix working.)

---

## 11. Things worth carrying forward

- **A passing assertion is not the same as a working feature.** The bar
  measured as correctly pinned at every scroll depth while being completely
  invisible. Same shape as the demo-spotlight bug in Part 268, where every
  assertion passed and the extracted frame was wrong.
- **When a user reports something three times, the measurement is what is
  wrong.** Two rounds were spent contradicting a direct observation on the
  strength of `getBoundingClientRect`.
- **Headed real Chrome is available and works.** Reach for it whenever a visual
  judgment matters, rather than declaring the check impossible.
- **Read the warnings already in the file.** `09-handbook.css:155` documented
  the `color-mix()` rewrite before it bit again.
- **Exclusions made for tidiness are worth re-examining.** Skipping the
  contents list was defensible in the abstract and wrong for how the page is
  actually used.

Two memories were written: `feedback_sticky_must_clear_navbar` (new) and an
update to `feedback_local_webgl_screenshot_unreliable` recording the headed
Chrome workaround.

---

## 12. Still open

Carried from Part 268 §12/§13, none started:

- **A video marker in the contents** (§13.3) — 11 of 50 chapters have a demo
  and nothing in the index says which. `demoForChapter(id)` already does the
  lookup, so it can be derived rather than hand-maintained. Inline SVG, not a ▶
  character.
- **The 2x-speed audio bug** (§13.4) — both handbook surfaces, not reproduced.
  Reproduce before changing anything.
- **"Return to where I jumped from"** — the second half of §13.2. The rail
  solves the mechanical difficulty of getting back up; it does not remember
  where a jump came from.
- **The three oldest clips** (`automl`, `text-to-sql`, `multimodal-rag`) predate
  the spotlight fix. ~4 minutes of compute, no API cost.
- **Part 1 of the handbook** — needs `preprocessing` (367) and
  `feature-selection` (369) split before anchoring.
- **The hosted TTS path** has still never run against a live paid vendor.
- Three untracked files in ML-Unified root — still the owner's call.
- **Everything here was verified against localhost.** Vercel builds from the
  push; the live handbook has not been checked.

---

## 13. Standing constraints unchanged

Nothing in this session changed the rules. No subagent was spawned. Every
commit was asked for first. Staging was always explicit paths with
`git -C <absolute path>` — which mattered twice, as the Bash working directory
drifted to the wrong repo mid-session again, once breaking a relative `node`
invocation and once a `mv`. No backend file was touched, so the mandatory HF
Space upload did not apply. Three screenshots written into the ML-Unified root
by the Playwright MCP were deleted by name, individually.
