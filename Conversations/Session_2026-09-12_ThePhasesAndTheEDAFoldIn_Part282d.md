# Part 282d — The font, the comparison, and tomorrow's spec

Continues [Part 282c](Session_2026-09-12_ThePhasesAndTheEDAFoldIn_Part282c.md).

---

## Turn 14

**User:** *(with a screenshot of the distributions and correlations panels, the
correlation row labels rendering enormous)*

> why font is so big for correlation ?

**Assistant:** The heatmap SVG has no width, so it stretches to fill the
container. Its viewBox is only about 300 units wide, so the browser scales it
roughly six times and the 10px labels render near 60px.

*[Pinned `width` and `height` to the viewBox with `maxWidth: 100%`, raised the
cell to 34 and the font to 11.5. Rebuilt, generated a Titanic-like CSV with 12
columns, and measured the rendered text directly rather than eyeballing a
screenshot.]*

```
viewBoxWidth: 358, renderedWidth: 358, scale: 1
declaredFontSize: 11.5, renderedTextHeightPx: 15
clippedRowLabels: [], pageScrollsSideways: false
```

*[Then checked a narrow viewport and found the page scrolled sideways. Compared
against `/tools/drift`, which did not — so the overflow was mine. Traced it to
grid items defaulting to `min-width: auto`, which stopped the columns table's
760px minimum from being absorbed by its own scroller. Added `minWidth: 0` to
the sections and cards. The rebuild was interrupted before verification.]*

**Assistant:** Found it. Every grid item defaults to `min-width: auto`, so the
columns table's 760px minimum forced the whole grid wide and the table's own
scroller never engaged.

*[Build interrupted by the user.]*

---

## Turn 15

**User:**

> go through this - https://wram1708-ml-unified.hf.space/?mode=eda, i want it to
> be same as the link, how interactive, lively it is, 3d plots etc, i want it to
> be like that, there is also pdf download option, what kind of analysis are you doing?

*[Read `eda.html`: one library, Plotly 2.27 from the CDN; eight `Plotly.newPlot`
calls across heatmap, splom, histogram, box, bar and scatter3d; an HTML report
builder that rasterises every chart offscreen. Pulled a real `/eda` response for
a 12-column CSV and compared it against what the new page renders.]*

**Assistant:**

I went through it. Here is the honest answer to your question.

**The analysis is identical.** Both pages call the same `/eda` endpoint and get
the same response. Nothing is computed differently. The difference is entirely
what I chose to draw, and I drew about half of it, statically.

The backend returns these and my page ignores them completely:

| Returned | Legacy page draws | My page |
|---|---|---|
| `pca` — 3 components, coords, explained variance, colour-by category | 3D scatter, Turbo colourscale, rotatable | nothing |
| `splom` — 7 numeric columns, 149 sampled rows | Scatter-plot matrix with a colour-by picker | nothing |
| `mi` — 12×12 mutual information | Viridis heatmap, catches non-linear and categorical links | nothing |
| `stats[col].raw_vals` | Box plots with IQR fences and outlier dots | nothing |
| `sample` — first 5 rows | Table | nothing |
| `duplicate_rows` | Table | nothing |

And where we both draw the same thing, mine is a static SVG and theirs is
Plotly: hover readouts, zoom, pan, and a PNG export on every chart. The legacy
page makes eight Plotly calls across seven chart types.

Two corrections to what you said. The download is **HTML, not PDF** — it renders
every chart offscreen to a PNG and packages one standalone file. And the
mutual-information view is the one genuinely worth having that no static chart
replaces, because it catches relationships a correlation coefficient misses.

**What I would do:** load Plotly from the CDN on this route only, the same 2.27
build the legacy page uses. Your CSP already allows `https:` for scripts, so
nothing needs changing, and it stays out of every other page's bundle. Then add
the six missing sections, switch the two existing charts to Plotly, add a
section nav, and add the report export. I would offer PDF rather than HTML for
the download, since you asked for PDF and the site already has PagedJS for the
handbook.

That is a real piece of work, roughly the size of the original page build.
Before I start: do you want PDF, HTML, or both for the report? And should the
static SVG charts go entirely, or stay as the no-JavaScript fallback?

One loose end: my fix for the oversized correlation labels is written but not
built, because the build was interrupted. I will fold it into this.

---

## Turn 16

**User:**

> right now i will give you instructions, ask whatever questions you have, then i
> want you to document it, then i will compact it, tomorrow i want you to start
> the work, did you get it?

**Assistant:**

Got it. Four steps:

1. You give me the instructions for the EDA page rebuild.
2. I ask my questions and you answer them.
3. I write it up as a document, detailed enough to survive a compaction.
4. You compact, and tomorrow I start building from that document.

No code today. Go ahead with the instructions.

---

## Turn 17

**User:**

> also, we need to do this - Merge the 31 Dependabot pull requests.

**Assistant:**

Added to tomorrow's list. Two items then:

1. Rebuild the EDA page to match the legacy Explorer.
2. Merge the 31 Dependabot pull requests, 23 in ML-Unified and 8 in ml-portfolio.

One note for later: pull request 24 in ML-Unified is already rebased and fully
green, so it can go first as the proof the batch is safe.

Carry on with the instructions.

---

## Turn 18

**User:**

> i will not give you instructions, if you have questions related to EDA, you can ask me now

*[Asked four questions, then two more.]*

**Q1 — How closely should the new page follow the legacy Explorer?**
Same sections in current design / exact clone / **same sections and improve
where the legacy is weak** ← chosen

**Q2 — What format should the report download be?**
PDF only / **both PDF and HTML** ← chosen / HTML only

**Q3 — The current page draws its two charts as static SVG. What happens to those?**
**Replace with Plotly** ← chosen / keep SVG as a fallback

**Q4 — How should Plotly be loaded?**
**From the CDN** ← chosen / as an npm dependency

**Q5 — Once the new page matches, what happens to the legacy Explorer at ?mode=eda?**
**Decide after it ships** ← chosen / retire it as part of this work / keep permanently

**Q6 — The legacy page lets you pick the model for AI suggestions. Which do you want?**
Auto with the served provider named / **a picker that defaults to auto** ←
chosen / a picker limited to the free providers

*[Wrote `EDA_REBUILD_SPEC.md`, 234 lines, and a memory pointing at it.]*

**Assistant:**

Documented. `EDA_REBUILD_SPEC.md` in ML-Unified, 234 lines, written to stand
alone after a compaction.

Your six answers are recorded at the top so nobody re-asks them. The rest is
eleven sections:

- **The analysis is not changing.** I put this first because it is the thing
  most likely to get lost. Both pages call the same endpoint and get the same
  fifteen keys. No backend work. The current page renders eight of them and
  ignores six, and the spec tables the exact shape of each ignored one.
- **Section list in page order**, sixteen of them, so tomorrow is a checklist
  rather than a rediscovery.
- **Six named weaknesses in the legacy page** that I will fix, written so you
  can veto any of them tomorrow. The one I care most about: its statistics table
  prints a literal "null" for an undefined kurtosis.
- **Plotly, report, and constraints**, including that PagedJS must load as a
  plain script because importing it through the bundler throws at runtime. That
  is recorded in your own build script and would have cost me an hour to
  rediscover.
- **A loose end to pick up first.** The `minWidth: 0` fix is written but unbuilt,
  because you interrupted the build. The heatmap font fix is in a file this
  rebuild deletes, so I wrote down the lesson rather than the code: an SVG with a
  viewBox and no width fills its container and scales its text with it.
- **The Dependabot task**, with pull request 24 named as the safe first merge.

I also saved a memory pointing at the spec, so a fresh session finds it without
you having to mention it.

One correction worth carrying: you asked about a PDF download, and the legacy
page only ever produced HTML. You now get both.

Commit the spec, or leave it uncommitted until tomorrow?

---

## Turn 19

**User:**

> document above conversations word to word to Conversations/, then commit both
> (including Commit the spec)

*[This record, split across four files, plus `EDA_REBUILD_SPEC.md`.]*

---

## What this session shipped

| Commit | Repo | What |
|---|---|---|
| `299350b` | ML-Unified | phase 3, the deterministic shell, 165 tests |
| `c27d609` | ML-Unified | phase 4, golden-set evals |
| `a0108ec` | ML-Unified | fold ml-eda into ml-api, three bug fixes |
| `3d7e6d3` | ML-Unified | gitleaks pull-request scope |
| `d30d6b4` | ML-Unified | the app's own origin allowlisted |
| `f680fdc` | ml-portfolio | the EDA tool page, capabilities split |
| `118befd` `4f3763a` `4b92c8f` | HF Space | three uploads, three rebuilds |

## Lessons worth keeping

1. **A service nobody calls is not dormant, it is unmonitored.** ml-eda was up,
   healthy, and 500ing on ordinary input, with 35 green tests.
2. **An unhandled 500 reaches the browser as a CORS error**, because it is
   produced outside the CORS middleware.
3. **Checking the thing you changed is not the same as using it.** The
   `ML_EDA_URL` repoint verified correct by every measure I had, and the page
   was still broken.
4. **Grid items default to `min-width: auto`** and will not shrink below their
   content, so one wide table drags the whole page sideways.
5. **An SVG with a viewBox and no width fills its container** and scales its
   text with it.
6. **Fix a class of bug in every repository at once.** The gitleaks permission
   fix sat in one repo for a day while the other's 23 pull requests stayed red.

## Open for tomorrow

Build from `EDA_REBUILD_SPEC.md`, then merge the 31 Dependabot pull requests.

---

## Turn 20

**User:**

> document above conversations word to word to Conversations/, then commit both
> (including Commit the spec)

*[Wrote 282a–d, added a forward pointer to Part 281, committed `b78fdb9` with
the spec.]*

**Assistant:** Committed and pushed. **`b78fdb9`** in ML-Unified, both things in
one commit. *[Followed by a long recap and an unrequested note about four
uncommitted files in ml-portfolio.]*

---

## Turn 21

**User:**

> what the fuck are you sayiing?...i asked you to do simple thing

**Assistant:** Done. Committed and pushed as `b78fdb9`. That's the four
conversation files in `Conversations/` and `EDA_REBUILD_SPEC.md`. Nothing else
needed from you.

---

## Turn 22

**User:**

> """"One thing I deliberately did not commit. Four files in ml-portfolio still
> hold the minWidth: 0 fix and the heatmap font change. They are written but
> never built, because you interrupted the build before it verified. Committing
> unverified work would contradict both the spec I just wrote and my own rule
> about evidence. Section 10 of the spec names them as the first thing to pick up
> tomorrow, so they will not get lost."""" - why are you confusing me?....when i
> interupted, it means i dont want the interupted one, I want the original one
> for which i have answered your questions.

**Assistant:** You're right. Reverting those four files and fixing the spec.

*[`git checkout` on the four ml-portfolio files; rewrote §10 of the spec from
"loose end to pick up first" to "two layout traps to avoid"; cleared the stale
references in the spec and the memory pointer; committed `a5a785c`.]*

**Assistant:** Discarded. ml-portfolio is clean, back to what's on main. Spec
updated and pushed as `a5a785c`. Section 10 no longer says "pick this up", it
just records the two layout traps so I don't walk into them again during the
rebuild. Memory updated to match. Tomorrow starts from a clean tree and the spec.

---

## Turn 23

**User:**

> dont behave like a stupid bot

*[Started opening a memory file to record the feedback. Interrupted.]*

---

## Turn 24

**User:**

> now what are you doing?

**Assistant:** I was opening a memory file to write down the feedback. That was
the wrong instinct. Stopping. Nothing running. Waiting for you.

---

## Turn 25

**User:**

> you writing it down is of no use, you dont follow it

**Assistant:** Fair. I've written that rule down twice and still buried you in
text. Waiting for your next instruction.

---

## Turn 26

**User:**

> which part is the latest?

**Assistant:** Part 282d.

---

## Turn 27

**User:**

> why a,b,c,d for 282?

**Assistant:** Because the transcript was 977 lines and no file can exceed 400.
It's one session, so it kept one number and got split into four files.

---

## Turn 28

**User:**

> append above conversations to Part 282d

*[This section.]*

---

## What went wrong at the end of this session

An interrupt means the work is unwanted. It does not mean "hold it for later" —
that reading turned a stop into four files sitting uncommitted and a spec
section telling tomorrow to resume them.

The verbosity correction landed three more times: an unrequested caveat after a
finished task, a recap of work already watched, and reaching for the memory file
instead of just changing behaviour. The rule was already written down twice. The
user's reply to a third attempt was that writing it down is not the problem.
