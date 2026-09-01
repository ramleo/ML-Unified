# Part 270 — Demo markers in the contents, and the 2x-speed bug

**Date:** 2026-09-01
**Repos touched:** `ml-portfolio` only. **No backend file changed, so no HF Space
upload applies.**
**Commits:** `74a508a`, `9c6aa36`, `4ea631e`, `9dcf66b` — all pushed to `main`,
CI green on all four jobs after each push.

---

## 0. Where things stand in one paragraph

Two backlog items closed and one CI failure fixed at its cause. The contents
page now says which of the fifty chapters carry a guided demo, which it never
did — the only way to find one was to open chapters until a button appeared.
The 2x-speed audio bug, open and unreproduced since Part 268, was reproduced
with numbers, root-caused, fixed on both surfaces, and re-measured. Along the
way two claims in the Part 268 write-up turned out to be wrong, and one defect
I reported in this session turned out to be my own instrumentation. That last
one is the lesson: the harness can manufacture the symptom you went looking
for.

---

## 1. The commits

| Hash | What |
|---|---|
| `74a508a` | fix(handbook): stop the generator stamping today's date on the title page |
| `9c6aa36` | feat(handbook): mark the chapters that have a demo in the contents |
| `4ea631e` | fix(handbook): narrate a sped-up clip at the clip's speed |
| `9dcf66b` | feat(handbook): offer 1.75x and 2x on the read-aloud bar |

Split deliberately at the owner's instruction in both cases: the CI fix apart
from the marker feature, and the clip fix apart from the read-aloud picker.
They are unrelated changes that happened to be in the tree together.

---

## 2. What the owner asked for, in order

1. "proceed with video markers in the contents" — Part 269 §12's first item.
2. (screenshots of a red CI run) "there is issue, see ss"
3. "two separate commits"
4. "what is pending from handbook backlog?"
5. "proceed with #1" — the 2x-speed audio bug.
6. "add those lines" — overriding the file-length pause on `HandbookAudio.tsx`.
7. "so you will do it next or how?" — on the two things left undone.
8. "got it, proceed" — check the duplicate first cue.
9. "split clip fix from read-aloud picker"
10. "document above conversations to Conversations/"

---

## 3. Demo markers in the contents

Eleven of fifty chapters have a guided demo. `DemoLauncher.tsx` already put a
"Watch this work" button under each of those eleven headings, and
`demoForChapter(id)` already did the lookup — so the fact existed, it was just
never said anywhere a reader could act on it while choosing what to read.

The same loop now also marks the chapter's row in the contents and adds one
legend line at the foot of it.

### 3.1 Three decisions worth keeping

**A marker, not a second launch button.** The contents row is an `<a>`. A
`<button>` inside a link is invalid HTML and ambiguous to click — does the row
navigate, or does the demo open? The row still does what a contents row does:
it goes to the chapter, where the launcher is waiting.

**An `aria-label`, not a visually-hidden caption.** The obvious accessible name
is an `.sr-only` span, and that was the first implementation. It is wrong here:
the find bar built in Part 269 indexes every text node under `.hb-body`, so a
hidden caption would have given the query "demo" eleven hits in the contents
that a reader could never see highlighted. `role="img"` plus `aria-label` names
the element for a screen reader and contributes no text node at all. Verified:
`.hb-toc-demo` elements contain zero text, and searching "guided demo" returns
1 of 1 — the legend, which is real visible text.

**The legend shows the marker itself.** Not a smaller cousin of it, not a bare
triangle: the same element with the same class. A key that does not match its
map is worse than no key. The first version had a bare 9px `<svg>` in the
legend against a 17px disc in the rows, and it read as two different things.

### 3.2 What the PDF does with them

`HandbookActions.makeBook()` feeds `.hb-body`'s `innerHTML` to Paged.js. By the
time a reader asks for the PDF, the launcher has injected eleven buttons,
eleven markers and a legend into that subtree — all three are offers to click
something, and on paper they are noise. `book.css` now hides all three.

Note that the buttons were already leaking into the typeset book before this
session; nobody had noticed because nobody had looked at a generated PDF for
a chapter that has a demo. Closing the new leak closed the old one.

### 3.3 The colour trap, again

The first draft tinted the marker's ground with
`color-mix(in srgb, var(--hb-hue) 16%, transparent)`. This build flattens
`color-mix()` to its first argument — the same rewrite that cost an hour in
Part 269 and has a warning sitting at `09-handbook.css:155`. Every marker would
have been a solid disc of its part colour, which is precisely the loud
treatment the design was trying to avoid. A literal grey, with the hue on the
glyph and on hover.

---

## 4. The CI failure was a calendar bug

Four commits in a row showed 4/5 with a red `handbook` job. The failing step:

```
public/handbook.md is stale. Run: python3 scripts/build-handbook.py
 public/handbook.md | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)
```

The one-line diff:

```
-First edition · August 2026
+First edition · September 2026
```

`build-handbook.py:107` stamped the title page with
`date.today().strftime('%B %Y')`, and CI regenerates the file and fails if it
differs from what is committed. The file was committed in August. On
1 September the generator began producing a different handbook from unchanged
sources, and the job went red with nobody having touched anything. It had
nothing to do with the handbook work; it would have failed on whatever was
pushed today.

Fixed at the cause rather than by re-committing the file. A `date.today()` in a
generator whose output is diffed by CI is a time bomb that re-arms every month;
re-committing would have bought 30 days. The edition is a constant now, which
is what it should always have been — the date is a fact about the book, not
about when the script last ran.

---

## 5. The 2x-speed bug — reproduced, root-caused, fixed

Open since Part 268 and explicitly **never reproduced**. Part 268 recorded two
hypotheses and was careful to label them as such. One was right, one was wrong,
and one thing it stated as a limitation was also wrong.

### 5.1 The reproduction

Password Strength clip (125s), Samantha voice, 45 seconds of wall clock, with
`speechSynthesis.speak` instrumented to record each utterance's rate, duration,
`boundary` progress, and whether it was cancelled before `end`.

| `video.playbackRate` | video advanced | utterances | cut off mid-sentence |
|---|---|---|---|
| 1x | 44.9s | 6 | 1 |
| 2x | 89.9s | 10 | **8** |

Every utterance in both runs went out at `rate=0.95`. At 2x the first line was
silenced after 5 of its 189 characters.

That is the whole bug, and it is Part 268's first hypothesis confirmed: cues are
frames and arrive twice as fast when the clip is sped up, speech runs on
wall-clock time and does not, so every line is cancelled by the next cue.
`src/lib/presenter/voice.ts` hardcoded `u.rate = 0.95` and nothing anywhere read
`video.playbackRate`.

### 5.2 The fix

`setRate(rate)` joins `setVoice(voiceURI)` as an optional method on the
`Presenter` interface. Optional for the same reason: a presenter that cannot
vary its speed simply omits it.

- **`voice.ts`** — `u.rate = BASE_RATE * this.rate`, with 0.95 promoted to a
  named constant because it is the speed every clip's timings were recorded
  against, not an arbitrary preference. Clamped 0.25–3.
- **`hosted.ts`** — sets `playbackRate` on the `HTMLAudioElement` before play,
  and on the live element if the speed changes mid-line.
- **`DemoVoice.tsx`** — reads `video.playbackRate` at each cue rather than
  holding it in state, because the viewer changes it through the video
  element's own native controls, which React never sees.

A speed change picked up mid-line applies from the **next** line. An utterance
already being spoken cannot change rate, and restarting it would replay words
the viewer just heard. Both alternatives are worse than a slightly late change.

### 5.3 Re-measured

| `playbackRate` | utterance rate | cut off, before → after |
|---|---|---|
| 1x | 0.95 (unchanged) | 1 → 1 |
| 1.5x | 1.425 | — → 0 |
| 2x | 1.90 | **8 → 0** |

The one line still logged as cut at 2x had spoken all 189 of its characters
before the next cue arrived, so it is complete in practice.

---

## 6. Two things Part 268 got wrong

Both were labelled as unverified guesses at the time, which is why they were
cheap to correct rather than embarrassing. Recorded here so the correction
travels with the record.

### 6.1 "Voices degrade badly above about 1.5"

The read-aloud bar's picker stopped at 1.5, and Part 268 suggested the settings
it did offer might already sound wrong because compact OS voices fall apart
above that. Measured — same sentence, Samantha, counting `boundary` events:

| rate | 1 | 1.25 | 1.5 | 1.75 | 2 | 2.5 | 3 |
|---|---|---|---|---|---|---|---|
| measured | 6452ms | 4991 | 4331 | 3640 | 3201 | 2546 | 2272 |
| `base/rate` | 6452 | 5162 | 4301 | 3687 | 3226 | 2581 | 2151 |

Within ~5% throughout, all 19 word-boundary events firing at every rate. No
clamping, no dropped words, up to 3x. The assumption was wrong.

There was **no defect at all** on that surface beyond the missing option: at
picker 1.5 the utterances already went out at exactly 1.5. The fix is two
numbers in an array. 2 is the top because it is the top of what was asked for,
not because 2.5 was found to fail.

### 6.2 "A hosted provider returns a fixed audio file, which cannot be sped up this way at all"

It can. `HostedPresenter` plays through an `HTMLAudioElement`, and that has a
`playbackRate`. Verified with `window.fetch` stubbed to return a locally
generated silent WAV — **no vendor contacted, no paid call made** — the audio
elements the presenter creates come out at `playbackRate: 2`.

What remains genuinely unverified is everything upstream of that assignment:
whether a real vendor's response decodes, and whether their audio sounds right
resampled at 2x. That needs a live paid key and is the owner's call, so it
stays on the backlog rather than being quietly claimed.

---

## 7. The defect that was my own instrumentation

**This is the part of the session worth re-reading.**

Every reproduction run logged a phantom first utterance: cut off after ~600ms
having spoken 0 characters, immediately followed by the same line spoken again
in full. It appeared at every speed including 1x, so it looked like a real
pre-existing glitch independent of the bug being fixed. I reported it as one,
flagged it as out of scope, and offered to look at it.

It is not real. Two runs differing only in when the voice is chosen:

| | utterances | first line |
|---|---|---|
| voice picked **before** playback | 2 | finished, all 189 chars |
| voice picked **during** playback | 2 | cut at 174/189 chars |

No duplicate in either. My harness called `video.currentTime = 0` after
selecting the voice; that seek fires `seeking`, and `DemoVoice.tsx`'s `onSeek`
correctly resets the cue index and silences the narrator so the line restarts
where the viewer scrubbed to. The scrub handler doing exactly its job, logged
by my instrumentation as a failure.

The remaining real effect — the first line cut at 174 of 189 characters when
the voice is chosen mid-playback — is narration starting 1.2s late because
that is when the voice was chosen, running into the next cue at 11.57s. Also
not a defect.

**The lesson, and it is the second measurement failure in two sessions.** Part
269's four-round bug was `getBoundingClientRect()` answering a question nobody
had asked. This one is a harness that drives a page artificially and then
records its own interference as the application's fault. Instrumenting a page
changes it. Before reporting a defect that only the instrumentation can see,
run it once without the instrumentation's peculiarities — here, one run in the
order a real viewer would use.

Worth noting what went right: I said "probably real, but the last root cause
got written down wrong, so let me check" rather than fixing it. The check cost
two runs and saved a change to working code.

---

## 8. The file-length rule, and asking rather than shipping

`HandbookAudio.tsx` was 383 lines — under the 400-line hard limit, over the
350-line threshold that says modularise before adding. The change needed was
two numbers in an array.

Per the standing rule ("if splitting first blocks the ask, stop and ask — don't
ship then flag") this was put to the owner rather than decided unilaterally.
The answer was "add those lines". The file is now 389 lines and the rule's
tension is recorded here rather than silently resolved.

---

## 9. How each claim was verified

Everything below was run in **headed real Chrome**
(`chromium.launch({ channel: "chrome", headless: false })`) against a throwaway
dev server on port 3100. Scripts written into the repo root — Playwright
resolves from `node_modules` and fails from the scratchpad — and deleted after.

| Claim | Evidence |
|---|---|
| 11 markers on the right 11 rows | each `href` and `aria-label` printed and checked against `demos/*.json` |
| The marker is actually painted | `document.elementFromPoint` at its centre lands inside its own `<svg>` |
| No phantom search hits | `.hb-toc-demo` text content empty for all 11; "guided demo" returns 1 of 1 |
| Legend matches the marker | same class, same element, screenshotted in both themes |
| Nothing leaks into the PDF | `book.css` attached to the live page; all three compute to `display: none` |
| The CI fix works | regenerating leaves `handbook.md` byte-identical; `git diff --quiet` passes |
| The clip bug is real | 8 of 10 lines cut off at 2x against 1 of 6 at 1x |
| The clip fix works | 0 of 10 at 2x, rate 1.90; 1x still 0.95 and unchanged |
| Hosted audio can be sped up | `Audio` constructor patched; elements come out at `playbackRate: 2`, fetch stubbed locally |
| Voices hold up past 1.5 | seven rates measured against `base/rate`, boundary events counted |
| The new picker options work | picker 1.75 → four utterances at 1.75; picker 2 → four at 2 |
| The duplicate first cue is not real | two runs, voice chosen before vs during playback |
| CI green | all four jobs after each push |

### 9.1 A stale server cost the first reproduction

The first marker verification returned **zero markers with eleven buttons** —
apparently damning. The cause: `localhost:3000` is running `next start` off a
production build from earlier that morning, not `next dev`. It was serving a
bundle that predated the change. Confirmed by grepping every served chunk for
`hb-toc-demo` and finding it in none, then `ps aux | grep next` showing
`next-server`.

Worth adding to the headed-Chrome note from Part 269: **check what is actually
serving before believing a negative result.** A production server started hours
ago looks exactly like a dev server until the moment your change does not
appear.

---

## 10. Still open

Carried forward, unchanged except where noted:

- **Return-to-position scrolling** — the unbuilt half of Part 268 §13.2. The
  rail solves getting back up; nothing remembers where a jump came from. More
  worth doing after this session, since the contents markers give readers one
  more reason to jump.
- **The three oldest clips** (`automl`, `text-to-sql`, `multimodal-rag`) predate
  the spotlight fix. ~4 minutes of compute, no API cost.
- **Part 1 of the handbook** — blocked on splitting `preprocessing/page.tsx`
  (367) and `feature-selection/page.tsx` (369) before `data-wt` anchors go in.
- **The hosted TTS path** has still never run against a live paid vendor. Its
  speed fix is verified against a local stub only — see §6.2 for exactly where
  the verified part stops.
- **Nothing has been checked on live Vercel.** Every verification in Parts 269
  and 270 was against localhost. CI going green is not the same thing.
- Three untracked files in the ML-Unified root — still the owner's call.

**Closed this session:** the video marker in the contents (Part 268 §13.3) and
the 2x-speed audio bug (Part 268 §13.4).

---

## 11. Standing constraints unchanged

Nothing was renegotiated. Applied this session: ask before every commit; split
commits when asked; explicit paths with `git -C`, never `git add -A`; delete
only files created this session and named individually; report the short hash;
push after every commit; no subagents; inline SVG rather than emoji; no live
paid API calls for self-verification; and the file-length rule surfaced as a
question rather than resolved unilaterally (§8).

No backend file was touched, so the mandatory HF Space upload did not apply.
