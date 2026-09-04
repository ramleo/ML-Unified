# Part 275 — the recorder was the problem, not the chapters

**Date:** 2026-09-04 (continues Part 274)
**Repo:** `ml-portfolio` only. No backend files touched, so no HF Space upload applies.
**Coverage:** 24 → **25 of 50**. Part 3 goes from *blocked* to **1 of 14**.
**Commits:** eleven, all pushed to `main`.

---

## 0. The one-paragraph version

The session started as "record one Computer Vision chapter" and turned into
rebuilding the recorder. Part 3 had zero demos because headless Chromium draws
WebGL as a blank canvas — a broken camera, not a hard chapter. Fixing that
exposed that the recorder could not move a pointer, which Depth Parallax needs
for four of its five modes. Then the owner watched the finished clip and named
four faults in how **every** clip had been recorded since the first one. All
four are now fixed, and five clips have been brought onto the fixed recorder —
three of which turned out to be narrating things that were not true.

---

## 1. The commits

| Hash | What |
|---|---|
| `e05dcd6` | Headed Chrome + `hover`/`drag`/`range` actions; MIME fix; two splits |
| `498e2e8` | Depth Parallax guided demo (ch 19) |
| `4c2400a` | Empty commit to unblock Vercel after the repo went private |
| `d4dfa35` | Title card — and the 1.3s gap between sound and picture |
| `abc0ce2` | Slider steps light the picture they change |
| `2c6cd16` | Closing card — and 32s of dead air it turned out to be hiding |
| `7f67684` | Actions wait for the narration to name them |
| `f99097c` | Re-record: Browser Extension Permission Risk Analyzer |
| `37145f3` | Re-record: AutoML Pipeline, **and correct what it claimed** |
| `d3920fd` | Re-record: Data Drift Detection |
| `54d8c33` | Re-record: Ensemble Methods, **and stop it asserting a coin flip** |

---

## 2. What the owner asked for, in order

1. What's pending in the handbook? (24/50, Parts 3 and 4)
2. What's TOC? — a vocabulary question, answered plainly
3. Recommendation → fix the recorder → **"fix it, and wait for my instructions"**
4. "proceed" ×3 — regression test, Depth Parallax, then the blocker that surfaced
5. **"keep it simple"** — a standing correction, taken
6. Is the Vercel failure caused by making the repo private?
7. Verify the finished clip → **four faults named** → one at a time, with commits between
8. Test the live in-browser player
9. Re-record the rest: one, then AutoML, then drift, then ensemble

---

## 3. THE CORRECTION WORTH KEEPING — "keep it simple"

Asked for a recommendation, I produced a three-part answer with a "what I would
not spend on" section and a closing paragraph. The reply: *"how many times i
have told you, keep it simple"*.

The right answer was four lines: fix the recorder, one line, no API cost,
unblocks 14 chapters; then one Depth Parallax clip to prove it.

**This is not a formatting preference.** A long answer to "what do you suggest"
makes the owner do the summarising, which is the work they asked me to do. It
recurred later in the session and I kept the answers short after this point.
Recorded as a memory.

---

## 4. Part 3 was never blocked on effort

`scripts/record-demo.mjs` launched `chromium.launch()` — headless, bundled
Chromium. On this machine that renders WebGL as a blank canvas. Fourteen
Computer Vision chapters had no demo because **the camera could not see them.**

```js
const LAUNCH = process.env.DEMO_HEADLESS
  ? {}
  : { channel: "chrome", headless: false };
```

Verified with a real GPU string rather than an assumption:

```
ANGLE (Apple, ANGLE Metal Renderer: Apple M4, Unspecified Version)
```

Regression-tested first: an existing clip re-recorded 8/8 steps, correct
frames, 92.7s against 91.3s. Only then was the change trusted.

**Cost of the fix: one line.** Cost of not knowing: fourteen chapters written
off as "needs a webcam anyway" across two session logs.

---

## 5. The recorder could not move a pointer

Depth Parallax has five modes. Four are driven by pointer motion:

| Mode | Driven by | Recordable before |
|---|---|---|
| Parallax | pointer moving over canvas | no |
| 3D relief | click-and-drag | no |
| Bokeh | click + range slider | half |
| AR occlusion | click + range slider | half |
| Depth map | static | yes |

A clip narrating "near objects shift more than far ones" over a frozen frame is
a video that lies about the tool. Three actions added — `hover`, `drag`,
`range` — to **both** players.

One implementation note worth keeping: Playwright's `mouse.move(x, y, {steps})`
fires its intermediate moves as fast as it can, which a pointer-driven WebGL
scene renders as a single jump. Real waits between samples are what make the
motion exist in the video.

### 5.1 The sample photo, and the risk that paid off

The owner supplied a mirrored building in a desert. I flagged the risk before
using it: **reflective surfaces are the known failure case for monocular
depth.** Tested rather than assumed — and the model read the glass as a solid
box in the middle distance rather than a hole with distant canyon showing
through. It measured the surface, not the reflection. That became the most
interesting line in the script.

---

## 6. Four faults in every clip ever recorded

The owner watched the finished clip and named them. I had verified the clip
frame by frame and found none of them, because I was checking *steps against
narration* and these are faults in the **shape of the whole thing**.

### 6.1 "I am complaining, isn't that enough?"

I had said "nobody has complained" as a reason to leave the 1.3s offset alone.
The owner was complaining. That closed it, correctly.

### 6.2 The four

| # | Fault | Cause | Fix |
|---|---|---|---|
| 1 | Starts abruptly, no statement of purpose | none | Title card |
| 2 | Picture 1.3s behind the words, **whole clip** | capture starts at context creation, ~1.3s before the page paints; audio laid from zero | Card covers the load; recorder measures when it lifts and gives the audio that lead |
| 3 | Actions fire at the step's start | action ran before the narration had named it | Cue at a third of the way in, capped at 2.5s, `actAfter` to override |
| 4 | Ends by stopping — 8.5s of silence on a frozen frame | see 6.3 | Closing card |

### 6.3 The dead tail was not an ending problem

Chasing it found the real defect. The recorder waited the **full** narration
length *after* the action, but narration had been playing since the step began,
over that action. Every step with a long action sat silent for the difference.

```js
const narrationLeft = lines[i].seconds * 1000 - (Date.now() - began);
await page.waitForTimeout(Math.max(0, narrationLeft) + (s.settle ?? 800));
```

**Depth Parallax went from 224.2s to 192.0s.** Thirty-two seconds of dead air,
spread across the whole clip, not concentrated at the end where it was noticed.

### 6.4 The in-app player was worse, and nobody had looked

It ran `await perform(s)` and *then* began speaking. Every upload, click and
drag in the live handbook demo happened in **complete silence** before a word
describing it. Now the line starts first and the action lands on the same cue.

---

## 7. Bugs found in my own work this session

- **Init scripts run before `document.documentElement` exists** — not merely
  before `body`. The first card attempt threw `Cannot read properties of null`
  and recorded a full clip with no card and no error.
- **The title card broke `timings.json`.** `DemoVoice` compares it against
  `video.currentTime` to re-speak narration in the viewer's own voice. The
  audio got the lead; that file did not, so browser narration would have run
  4.9s early. Caught by noticing a frame did not match the step it claimed.
- **The in-app player stamped every upload `text/csv`.** A File's type becomes
  the data-URL prefix and no `<img>` decodes `data:text/csv`. Every image tool's
  live walkthrough would have failed silently while the recorded one worked.
- **A floating promise.** Starting `speak()` before awaiting it means an abort
  between the two surfaces as an unhandled rejection. Caught and swallowed.

---

## 8. LESSON — the spotlight dims what it is not on

Reported by the owner with two screenshots: driving a slider, the ring sat on
the slider, and the image the slider was changing went dark behind the dimming
layer.

Steps gained an optional `with`: a second anchor folded into the spotlight, so
the ring is the bounding box of both. Not a Depth Parallax special case — any
step driving a control whose whole point is its effect elsewhere needs it. It
was used again the same day on AutoML, where one line names both the target
column and the task type.

---

## 9. Three of five re-records were narrating something untrue

This is the return on the work, and it is larger than the cards.

| Clip | What the audit found |
|---|---|
| extension-permission-analyzer | clean |
| **automl** | Step 5: *"four algorithms compete"* over a screen showing **five** chips. Extra Trees has always been in the default line-up. Steps 4 and 5 also pointed at **nothing** while describing three specific controls. |
| drift | clean — both checkable claims hold (glucose and BMI on top, "exactly the two I moved"; 200 rows, 8 features) |
| **ensemble** | Step 8 named the winner. Step 9 had the arithmetic backwards. |

### 9.1 Neither AutoML nor Ensemble could have been caught by an assertion

- `"four"` is not a string the AutoML page contains either way.
- Ensemble's guard was `expect: "XGBoost"` — which matches one of five
  leaderboard rows **whether that row won or lost**. It asserted nothing.

Only reading the frame against the words finds these.

### 9.2 The ensemble arithmetic

Step 9 claimed the fold-to-fold swing is *wider* than the gap from first to
last. `EnsembleResults.tsx:17` defines "Variable" as a standard deviation of at
least **0.03**; the gap this run is **0.034**. The quoted number does not
support the conclusion drawn from it. Rewritten to "the same order as the
distance from first place to last" — same honest point, actually true — and the
assertion moved to `"Variable"`, which is on screen only when the claim holds.

### 9.3 A claim that moves between runs should not be in a script

"XGBoost takes it" was true today. Which model wins is decided at training time.
The step's point was always *how little separates them*, so it now says that and
nothing about who won.

---

## 10. The Vercel failure — and the part I got right by checking

The owner asked whether making the repo private broke the deploy. Both halves
were true and the distinction mattered:

- **The error** is old: no `user.email` set anywhere, so every commit was
  authored `wramakrishna@Ws-MacBook-Air.local`.
- **Going private turned the check on.** A public repo deploys without needing
  to attribute an author; a private one checks the author against the Vercel
  account.

I asked which email GitHub knows rather than assuming `ramleo84@gmail.com` was
usable — it was, but the check cost one question and would have cost a second
failed deploy if it had not been.

---

## 11. Files after the splits

Three modules came out of the recorder, all forced by the 400-line rule and all
better for it:

```
scripts/record-demo.mjs    341   the loop, the timings, the mux
scripts/demo-actions.mjs   134   everything a step can DO to the page
scripts/demo-cards.mjs      93   the opening and closing cards
scripts/demo-overlay.mjs    92   spotlight, caption, backend watchdog
scripts/demo-audio.mjs      92   narration, lead, tail, mux
src/app/handbook/HandbookDemo.tsx  298
src/app/handbook/demoActions.ts    132
```

The act list is the part that grows every time a tool needs a new kind of
input, on both sides. It is now its own file on both sides.

---

## 12. The live player was tested, finally

Driven in real Chrome, chapter 19, start to finish. 185 voices, steps 1→14, no
page errors. Upload fires ~3s into step 2 rather than instantly. Synthetic
pointer events **do** drive the WebGL shader (canvas SSIM 0.93 across the
sweep). The `with` ring encloses canvas and slider.

**Deliberately not added: cards in the live player.** The panel already shows
the tool's name and blurb in its header, and a closing card saying "try it
yourself at …" is absurd when the reader is already inside the tool. The two
players should match on *behaviour*, not on framing.

---

## 13. Coverage and cost

| Part | Coverage |
|---|---|
| 1 · ML Pipeline | 11 / 11 |
| 2 · Language & Documents | 4 / 4 |
| 3 · Computer Vision | **1 / 14** |
| 4 · Security & Trust | 9 / 21 |
| **Total** | **25 / 50** |

**Zero paid API calls this session.** Every clip recorded was local compute or a
free endpoint. Verified rather than assumed, by mapping each demo to the
endpoints its page calls and cross-checking against the backend's
`check_and_record_call` sites.

Free and still on the old recorder — **14**: shap, preprocessing,
feature-engineering, feature-selection, pipeline-builder, pipeline-cinema,
email-auth-checker, tls-security-headers-scanner, dns-tunneling-detector,
malicious-package-scanner, password-audit, phishing-email-classifier,
yara-file-scanner, realtime-analytics.

Paid, untouched — **6**: contract-invoice-reconciliation, document-intelligence,
multimodal-rag, optuna, prompt-injection-playground, text-to-sql.

---

## 14. Recording recipe (changed)

```
NEXT_PUBLIC_ML_UNIFIED_URL=https://wram1708-ml-unified.hf.space \
NEXT_PUBLIC_ML_SQL_URL=https://wram1708-ml-sql.hf.space \
  npx next build && npx next start -p 3300
DEMO_BASE_URL=http://localhost:3300 node scripts/record-demo.mjs <demo>
```

Port **3300** still required — `security/origin_policy.py` rejects any other
Origin. **A real Chrome window now opens and is visible while recording; do not
click in it.** `DEMO_HEADLESS=1` restores the old behaviour.

Frame review at 88% of each step, plus — new this session — **the first frame,
the last frame, and a pair of frames inside every motion step**, compared with
SSIM on a crop of the canvas alone so a caption change cannot be mistaken for
the picture moving.

---

## 15. Still open

- **14 free clips** still on the old recorder (§13). `realtime-analytics` cannot
  record against localhost — it needs the live Vercel path, per Part 273 §7.2.
- **6 paid clips**, one at a time with explicit go-ahead.
- **13 Part 3 chapters** now recordable but not written. Several still need a
  webcam or a very specific upload and may not be worth a clip.
- `QueryResultPanel.tsx` (403) and `UserGuideModal.tsx` (403) — over the line
  limit, pre-existing, worked around four times now.
- A pre-existing lint error at `document-intelligence/DocHistory.tsx:44`.
- Hosted TTS has still never run against a live paid vendor.
- No site-wide emoji-as-icon audit.
- Three untracked `test_*` files in the ML-Unified root — still the owner's call.

---

## 16. What this session is actually about

Part 274 closed with *"building a demo is a testing activity that produces a
video as a by-product"*, and used that to argue the marginal clip is worth less
than the early ones.

This session says something narrower and more useful: **re-recording an old
clip is also a testing activity.** Three of five re-records found a claim that
was not true — one of them in chapter 1, the first demo anyone meets. Those
defects had been shipped and on the site for weeks, and every one of them was
found by looking at a picture and reading a sentence.

The other half: for two sessions Part 3 was written off as *"needs a webcam
anyway"*. It needed one line of configuration. **A blocker nobody has opened the
lid on is not evidence of difficulty.**
