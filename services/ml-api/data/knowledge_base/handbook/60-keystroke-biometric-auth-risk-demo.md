Chapter 52Keystroke Biometric Auth-Risk Demo


> Type a short phrase three times to enrol a keystroke-timing profile, then type it once more and see how closely the rhythm matches. Scoring uses scaled Manhattan distance over dwell and flight times, a published approach for keystroke-dynamics anomaly detection. Try typing normally, then deliberately faster or hunt-and-peck, and watch the score move. A concept demo rather than a calibrated authenticator — and entirely client-side, with no server call.

## At a glance

| | |
|---|---|
| **Also called** | Live Biometric Demo · Zero ML |
| **Model or method** | Scaled Manhattan distance (client-side) |
| **What you give it** | Typed keystroke timing |
| **Timing Signals** | 2 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/keystroke-biometric-auth-risk` |

## Using the tool

### What this tool does
Type a short fixed phrase 3 times to enroll a personal typing-rhythm
profile, built from real key-press timing captured by your browser — no
video, no audio, no server round-trip. Then retype the phrase once more:
the tool measures how closely that attempt matches your enrolled rhythm
and reports a risk band, using the same real, published technique
behind commercial keystroke-dynamics authentication systems.

### The real technique
Two timing features are captured per keystroke:
- **Dwell time** — how long each key is held down (keydown → keyup).
- **Flight time** — the gap between releasing one key and pressing the
  next (keyup → next keydown). This is the classic "digraph timing"
  signal keystroke-dynamics research keys off.

Your 3 enrollment reps build a mean + standard deviation for every
character position's dwell and flight time. A later attempt is compared
against that profile using **scaled Manhattan distance** — summing each
feature's absolute deviation from your enrolled mean, divided by that
feature's own standard deviation, then averaged. This specific classifier
is a real, published top performer for keystroke-dynamics anomaly
detection (CMU's Killourhy & Maxion benchmark and follow-on academic
work report it among the best-performing detectors for this exact
problem), not a heuristic invented for this demo.

### How to use it
1. Type the shown phrase exactly, 3 times in a row, to enroll your
   profile. A mismatched retype (typo, or using Backspace) discards that
   attempt — just try again.
2. Once enrolled, type the phrase once more. Try it normally first (should
   score **Low**), then try deliberately typing much faster, slower, or
   hunt-and-peck style, and watch the score rise.
3. The result shows the risk band, the raw scaled-distance number, and a
   bar chart of that attempt's actual dwell/flight timing.

### Reading the result
- **Low deviation** — this attempt's timing matches your enrolled rhythm
  closely.
- **Medium / High deviation** — this attempt's timing diverges
  meaningfully from what you enrolled — the same signal a real system
  would use to flag a possible impostor typing a stolen password.

### Notes & limits — read before trusting this as "real security"
- **This is a concept demo, not a calibrated authenticator.** Real
  keystroke-dynamics systems are validated against large populations of
  real users and impostors to set false-accept/false-reject thresholds.
  Here, the thresholds were set from a handful of synthetic and manual
  test typings in one browser session — they demonstrate the mechanism
  honestly, not a production-grade false-accept rate.
- Only ONE enrolled profile exists at a time, in this browser tab's
  memory — nothing is saved, sent anywhere, or persisted across a reload.
- A determined impostor who studies your exact rhythm (or a scripted
  bot replaying captured timing) could still pass — this demo shows the
  base signal, not a hardened production system with liveness/replay
  defenses.
- Backspace during a timed attempt discards it rather than trying to
  patch the timing — corrected typos have a different rhythm than a
  clean run and would distort the profile.

## What problem it solves

A password proves you know a secret. It says nothing about who is typing it.
Anyone holding the string is indistinguishable from its owner.

**Keystroke dynamics** is the idea that the *rhythm* of typing is itself
identifying — that the way a particular person types a particular phrase is
consistent enough across repetitions, and different enough between people, to
work as a second factor. It is one of the few biometrics that needs no extra
hardware: a keyboard and a millisecond clock are the whole sensor.

This tool makes that concrete. You enrol by typing one short phrase three
times, and it builds a timing profile from those repetitions. Then you type the
phrase again and it scores how far the new attempt sits from the enrolled
rhythm. Type naturally and the score is low. Deliberately change your
rhythm — slow down, use one finger, pause mid-phrase — and it rises.

The point is to show both halves honestly: the signal is real, and it is also
fragile. Keystroke dynamics is a plausible *risk signal* to combine with other
evidence. It is not a replacement for a password, and this demo is built to
make that obvious rather than to sell the idea.

Everything runs in the browser. No profile is stored, nothing is transmitted.

## How it works, step by step

1. **Type the phrase `the quick fox` three times.** Each repetition is
   captured as raw `keydown`/`keyup` events with a high-resolution timestamp.
2. **Each repetition becomes two feature vectors** — dwell times and flight
   times.
3. **The three repetitions are averaged** into an enrolment profile: a mean and
   a standard deviation per feature.
4. **Type the phrase once more.** The same features are extracted.
5. **Score the attempt** against the profile with a scaled Manhattan distance.
6. **Report a band** — low, medium or high — with the raw number alongside it.

## The model or algorithm

### The two features

Every keypress produces two events with timestamps from `performance.now()`, a
monotonic clock with sub-millisecond resolution. From a sequence of them, two
classic features:

**Dwell time** — how long one key is held down.

```
dwell[i] = keyup[i].t − keydown[i].t
```

**Flight time** — the gap between releasing one key and pressing the next.

```
flight[i] = keydown[i+1].t − keyup[i].t
```

Flight time **can be negative**, and the code treats that as normal rather than
clamping it. A fast typist presses the next key before releasing the current
one; the overlap is real and is itself characteristic of how fluent someone is
with a given phrase. Discarding the sign would throw away signal.

For a thirteen-character phrase this gives thirteen dwell values and twelve
flight values — twenty-five numbers describing one typing performance.

### The classifier — scaled Manhattan distance

The scoring is not invented here. It comes from **Killourhy and Maxion's CMU
keystroke-dynamics benchmark**, which evaluated fourteen published anomaly
detectors on the same dataset. Scaled Manhattan distance was among the
best-performing, at roughly a **0.09 equal error rate** — around nine per cent
of attempts misclassified at the threshold where false accepts and false
rejects balance.

The formula is deliberately simple:

```
score = (1/n) · Σ |attempt[i] − mean[i]| / std[i]
```

For each feature, take the absolute deviation from the enrolled mean, divide by
that feature's own standard deviation, sum across all features, and average.

The division is what makes it work. Some parts of a phrase are stable for a
given person — a two-letter combination typed thousands of times has a tight
distribution. Other parts vary wildly. An unscaled distance would let the noisy
features dominate. Scaling by each feature's own standard deviation converts
every term into "how many of *this feature's* typical deviations away is this",
so a 40 ms miss on a rock-steady feature counts more than a 40 ms miss on a
loose one.

The result is interpretable without a lookup table: **the score is the average
number of standard deviations of error per feature.** A score of 1.0 means the
attempt is typically one standard deviation off across the board.

### The standard-deviation floor

One line matters more than its length suggests:

```
std = max(sqrt(variance), 5)   // 5 ms floor
```

Without it, a feature that happened to come out nearly identical across three
enrolment repetitions gets a standard deviation near zero, and division by it
sends that single term — and the whole score — to infinity. The floor of 5 ms
encodes a real fact: human timing does not repeat to the millisecond, so a
near-zero measured spread is a sampling artefact of having only three samples,
not evidence of superhuman consistency.

### The bands

```
score < 1.2   →  low     (consistent with the enrolled profile)
1.2 – 2.5     →  medium  (some deviation)
score ≥ 2.5   →  high    (substantially different rhythm)
```

These were calibrated during unit verification against synthetic attempts with
known properties — a near-identical retype scores well under 1.0, and an
attempt with every dwell time doubled scores well above 2.5. They are
demonstration thresholds tuned on this phrase and this enrolment size, not
values transferred from a published benchmark, and the interface says so.

## Why these choices

**Why three enrolment repetitions?** It is the minimum that gives a standard
deviation at all — with two you get a spread, but a meaningless one; with one
you get nothing to divide by. Real deployments use far more, typically dozens,
and their accuracy reflects it. Three is chosen so a visitor will actually
finish enrolling, and the small sample size is disclosed as a limitation rather
than hidden behind the score.

**Why a fixed phrase rather than free text?** Because the features are
*positional*. `dwell[4]` means "how long the fifth key was held", which is only
comparable across attempts if the fifth key is the same key. Free-text
keystroke dynamics is a genuinely different and harder problem, using digraph
and trigraph statistics aggregated over a long session rather than a fixed
vector. Fixed-phrase is the tractable version and the one the CMU benchmark
measures.

**Why does a backspace void the attempt?** Correcting a typo destroys the
timing of the surrounding keys — the pause to notice the error, the reach for
backspace, the retype — and none of that belongs in the profile. The choice is
between silently corrupting the data and restarting the repetition. Restarting
is honest; the input clears and a mismatch indicator flashes.

**Why is scoring done in the browser with nothing stored?** A typing profile is
biometric data. Storing it would create exactly the liability the tool is
meant to let people reason about, for a demonstration that needs no
persistence.

### A real bug worth keeping

The finalisation logic has a comment longer than the code it explains, because
the obvious implementation was wrong in a way that took live testing to find.

The natural place to detect "the phrase is complete" is the `onChange` handler,
which fires when the input's value reaches the target string. But the browser
fires the native `input` event **before** the `keyup` for the very key that
completed the phrase. Finalising there captures a buffer that is one `keyup`
short — and worse, that orphaned `keyup` then lands at the head of the *next*
attempt's buffer, shifting every dwell pairing by one index and producing
nonsensical negative dwell times throughout the following repetition.

The fix: `onChange` only sets a "ready to finalise" flag. The actual
finalisation happens in `onKeyUp`, and only once the buffer's `keydown` and
`keyup` counts are balanced again. The lesson generalises past this tool — when
pairing events from two different streams, the completion condition belongs on
whichever stream finishes last, not on whichever one is convenient to observe.

## How to read the output

The score is the average number of standard deviations of deviation per
feature, so it is directly interpretable. Roughly 1 means "about as far off as
this person's own repetitions were from each other". Roughly 3 means "three
times that far", which is a different rhythm.

A **low** band on your own second attempt is the expected result and shows the
signal exists. A **high** band when you deliberately type differently shows the
signal is discriminative. Both together are the demonstration.

What the tool cannot show you, because it never sees a second person, is the
error rate that actually matters: how often *someone else* typing the same
phrase would score low. That is the false-accept rate, it requires an impostor
population, and it is where the published ~9% equal error rate comes from
rather than from anything measured here.

## Limits

- **Three enrolment repetitions is far too few** for real use. The standard
  deviations are crude, which is exactly why the 5 ms floor is needed.
- **No impostor testing.** The demo scores you against yourself. It cannot
  measure false accepts.
- **Fixed phrase only.** Free-text keystroke dynamics is a different technique.
- **Hardware and context change the rhythm.** A different keyboard, a laptop
  versus a mechanical board, a phone, being tired, being cold, or holding a cup
  of coffee will all raise the score for the genuine user. This is the central
  practical problem with the whole biometric.
- **`performance.now()` resolution is deliberately reduced** in browsers as a
  Spectre mitigation, typically coarsened to around 100 microseconds and
  sometimes jittered. Fine for tens-of-milliseconds features, but it means the
  clock is not as precise as its type suggests.
- **Timing can be replayed.** Unlike a fingerprint, the feature vector is a
  list of numbers; anything that can inject synthetic key events with recorded
  timings can reproduce it exactly.
- **Not an authentication system.** It is a risk signal, and the thresholds are
  demonstration values.

## Likely interview questions

**"What are dwell and flight time, and why both?"**
Dwell is how long a key is held; flight is the gap between releasing one key
and pressing the next. They capture different things — dwell is largely motor
habit per key, flight is about transitions between keys and how well-practised
a particular sequence is. Flight can legitimately be negative when a fast
typist overlaps presses, and that overlap is informative, so the sign is kept.

**"Why scaled Manhattan rather than Euclidean or Mahalanobis?"**
Manhattan is more robust to a single wild feature than Euclidean, which squares
deviations and so lets one hesitation dominate the whole score. Full
Mahalanobis would be the principled choice since it accounts for correlations
between features, but it needs a covariance matrix estimated from far more
samples than three repetitions provide — with n=3 and 25 features the matrix is
hopelessly singular. Scaled Manhattan is the diagonal approximation: per-feature
normalisation without the off-diagonal terms. The CMU benchmark found it among
the best performers in practice, which is why it is used here.

**"Your standard deviation could be zero. What happens?"**
The score goes to infinity, which is why there is a 5 ms floor. It is not just a
numerical guard — it encodes a fact about the domain. A measured spread of zero
across three samples means the sample is too small, not that the person is
perfectly consistent, so the floor substitutes a plausible minimum human
variability.

**"How would you deploy this for real?"**
Never as a primary factor. As a risk signal feeding a step-up decision: a
password plus a low keystroke score proceeds normally, a password plus a high
score triggers a second factor rather than a rejection. It needs continuous
re-enrolment so the profile tracks the user's drift over time and across
devices, a per-user rather than global threshold, and an explicit fallback path
for the days when someone's typing is legitimately different — otherwise you
lock out your own users for having a cold.

**"What is an equal error rate and why quote it?"**
It is the operating point where the false-accept rate equals the false-reject
rate, which gives a single number to compare detectors without picking a
threshold first. Around 0.09 for this technique means roughly nine per cent
error at that balance point — usable as one signal among several, nowhere near
good enough alone. Quoting it is also how you make clear that a demo which only
ever tests one person has not measured the number that matters.

**"Is keystroke timing personal data?"**
Yes. It is behavioural biometric data, it identifies a person, and under GDPR
biometric data used for identification is a special category with a higher bar
for processing. That is a substantive reason this tool computes everything in
the browser and stores nothing — and a reason any real deployment needs a
retention policy, a legal basis, and a non-biometric alternative for people who
decline.
