# Part 289 — The demo clips turned out to be integration tests

Continues [Part 288](Session_2026-09-17_GuidelinesDoneAndClipsBegun_Part288.md).

2026-09-17 (same day, later). The task was narrow and repetitive: work the E6
demo-clip backlog, one tool at a time, asking before each. What it turned into
was three production-bug fixes, because **recording a guided demo is the most
honest integration test the site has** — it drives a real user's exact path
through a tool against the live backend, and three tools broke on that path in
ways no unit test or `expect` guard had ever caught.

Six clips shipped this session (siem-alert-triage, attack-surface-scanner,
qr-phishing-detector, malware-image-triage, adversarial-robustness-lab,
astrophotography-anomaly-detector), plus a re-record of ai-code-detector. Every
one reviewed frame by frame. Three of them surfaced a live bug affecting real
visitors, not just the clip.

The spine of the day: **a clip that runs the tool for real finds the bugs the
tool's own tests can't — and the fix belongs to the tool, not the clip.**

---

## 0. First, a correction I'd been carrying: I record the clips myself

The compaction summary (twice now) claimed recording needs the user's Mac and
that my part is only authoring the JSON. Wrong. `scripts/record-demo.mjs`
already launches **headed real Chrome** (`channel:"chrome", headless:false`),
so the WebGL-blank problem is gone and I run the whole thing locally:
`next build && next start -p 3300` wired to both Space URLs, then
`DEMO_BASE_URL=http://localhost:3300 node scripts/record-demo.mjs <tool>`,
then review with `ffmpeg -ss <t> -frames:v 1`. The user asked "why will I
record?" — and they were right. No hand-off. Recorded to
[[project_demo_clip_audit]].

## 1. siem-alert-triage → the mistral-only judges were 200-with-null

The clip's grouping step was honest (13 lines → 6 groups), but every triaged
group read **"Judge unavailable."** The endpoint answered `200` with a `null`
body. Space logs were unambiguous: `mistral: Error code: 429 - Rate limit
exceeded` on every call, sustained for minutes. Mistral free-tier capacity
contention — the exact thing [[project_llm_provider_status]] warned "is this
bug waiting to happen" for any single-provider judge.

Two more routers were still mistral-only: `/siem-triage/judge` and
`/ai-code-detect/judge`. Fixed both with the same `cohere → mistral` cascade
`prompt_injection_check.py` already used (cohere first, free/reliable; gemini
absent because it's the only paid key on a public endpoint). `dcef469`,
uploaded to the Space, verified live (real verdicts: login burst → high, new
admin → critical). This also meant the ai-code-detector clip shipped earlier
this session had a broken "unavailable" LLM panel — re-recorded once the fix
was live (`62c7e4a`). The user chose "add a fallback provider" over waiting or
narrating around it — the right call, since it fixes the live tool too.

## 2. attack-surface-scanner → clean by evidence, and no faked findings

example.com and our own deployment both scan completely clean — nothing
exposed, every risky port closed. That's the honest story (the tool confirming
a locked-down host), and the red-Findings behaviour is *explained*, not
manufactured. **I will not point an attack-surface scanner at a third party to
fake findings** — same principle as the phishing-sample lesson. Scanned our own
`ml-portfolio-rho.vercel.app`, the pattern the TLS clip established. `bf795ec`.

## 3. qr-phishing-detector → build the input to the tool's real rules

Rather than imagine a phishing URL, I read the backend heuristics first
(`mm_qr_phishing.py`): IP-host / "@" / punycode / typosquat = high; shortener /
HTTP / abused-TLD = medium. Then crafted `http://paypal.com@paypa1.com/login`,
which honestly trips three real signals at once (the @-trick, a 1-char
typosquat of paypal.com, plain HTTP). The clip shows genuine multi-signal
detection and the on-page honest-limits disclaimer. `57551cd`.

## 4. malware-image-triage → a synthetic input that measures true

Bundled a mixed-entropy sample (readable-text half + random-bytes half) so the
byte-plot and the sliding-window entropy heatmap both tell a real story: a
middling *average* (6.21/8, "low") that hides where the high-entropy region
actually sits. The measurements are real; the file just makes them legible —
same legitimacy as the SIEM sample log. Frame review caught the one narration
error: I'd said the heatmap goes "blue" over the text, but the text region is
mid-entropy **yellow**. Changed the word, not the anchor. `211979e`.

## 5. adversarial-robustness-lab → two narration fixes and a recorder stall

FGSM at ε0.03 flips MobileNetV2 from a confident "mosquito net" (82%) to
"quilt" (16%, Fooled) with an imperceptible change; both defenses land on other
wrong labels rather than recovering — which is the tool's own honest headline,
not a broken demo. Two catches:
- My curl test used jpeg_quality 75; the demo's default is 50, at which the
  JPEG defense **disrupts to "studio couch"** rather than "no effect." Narration
  fixed to match the screen. (Lesson: the demo runs the UI defaults, not your
  test's params.)
- Avoided naming "critical" in the priority scale and the run-to-run smoothing
  label, since those vary per run.
Also hit a transient recorder stall — one take produced a **10-minute, 36 MB**
clip with two ~260s dead gaps (Space latency spikes filmed as "Running…"). The
clean re-record is 115s/10 MB. `438812c`.

## 6. astrophotography-anomaly-detector → the tool 500'd on every real detection

The richest bug. Generated synthetic night-sky frames (fixed starfield, an
injected streak) — the tool's own documented validation method — and the
endpoint returned **500**. Space logs: `IndexError: too many indices for array:
array is 2-dimensional, but 3 were indexed` at `_detect_streaks`. Root cause:
**OpenCV 5 changed `cv2.HoughLinesP`'s return from `(N,1,4)` to `(N,4)`**, and
the code indexed `lines[:, 0, :]`. It only crashed *when a line was found* — so
the tool 500'd for every user precisely when there was an anomaly to report,
while a clean frame set returned fine and hid it. One-line fix
(`lines.reshape(-1, 4)`, robust to both), `c51ee25`, deployed.

Then tuned the synthetic streak to a single clean detection: long/thick gave 10
collinear fragments (dedup only merges within 15px), thin/short gave 0 (below
threshold); ~47px width-2 gave exactly one "possible meteor or satellite trail"
that the median stack visibly rejects. Reduced to a 3-frame set to keep the
upload to three steps. `ba3c049`.

---

## Where I was wrong, and corrected

- **"You record the clips."** I record them myself; the recorder is headed. The
  user caught it directly.
- **Narration vs. the screen, twice.** "blue" heatmap that was yellow;
  "no effect" JPEG defense that actually disrupted to studio couch. Both caught
  by reading the frame, both were the word being wrong, not the anchor —
  exactly the [[project_demo_clip_audit]] rule.
- **My curl test ≠ the demo's run.** Different jpeg_quality gave a different
  defense outcome. Test with the same params the UI will use.

Every bug fix this session came from *running the tool*, not from reading it.

---

## Commits

| Repo | Commit | What |
|---|---|---|
| ml-portfolio | `928f129` | siem-alert-triage clip |
| ML-Unified | `dcef469` | judge cohere fallback (siem + ai-code) — HF uploaded |
| ml-portfolio | `62c7e4a` | re-record ai-code-detector (judge now answers) |
| ml-portfolio | `d3667d6` | timings sidecars for siem + ai-code |
| ml-portfolio | `bf795ec` | attack-surface-scanner clip |
| ml-portfolio | `57551cd` | qr-phishing-detector clip |
| ml-portfolio | `211979e` | malware-image-triage clip (+ synthetic sample) |
| ml-portfolio | `438812c` | adversarial-robustness-lab clip |
| ML-Unified | `c51ee25` | astro HoughLinesP OpenCV-5 fix — HF uploaded |
| ml-portfolio | `ba3c049` | astrophotography clip (+ synthetic frames) |

Backlog: 18 tools without clips, now mostly webcam/WebGL (which a clip can't
show honestly) plus a few image-upload CV tools.

---

## Lessons

- **A guided demo is an integration test.** It runs the real UI path against
  the live backend on a real input. Three tools that passed their unit tests
  and `expect` guards broke here — the null judges, the OpenCV-5 crash — because
  those only manifest on the exact input a real interaction produces.
- **A 200 is not a success.** Two of the three bugs answered HTTP 200 (with a
  null body) or failed fast; the SIEM one showed no error banner at all. Assert
  the rendered result, and watch the clip — a guard that a broken path can pass
  is no guard.
- **Build the input to the tool's real rules, then let it measure.** Reading
  `mm_qr_phishing.py` before crafting the URL, and generating synthetic byte /
  astro inputs, gave honest demos with real measurements — never staged
  verdicts.
- **The fix belongs to the tool, not the clip.** Each time, the honest move was
  to fix the live bug (with the user's go-ahead for backend deploys) and then
  record the working tool — not to script around the breakage.
- **Pinned OpenCV 5 keeps changing return shapes.** Haar cascades gone (Part
  earlier), now HoughLinesP `(N,1,4)`→`(N,4)`. Audit any `cv2` return shape
  assumed from old examples. See [[project_deepfake_detector_dtw_lesson]].
