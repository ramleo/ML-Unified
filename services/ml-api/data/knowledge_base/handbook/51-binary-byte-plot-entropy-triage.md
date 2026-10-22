Chapter 43Binary Byte-Plot & Entropy Triage


> Upload any file and see its structure as a picture. The bytes are rendered as the grayscale byte-plot used in malware-visualisation research, next to a sliding-window entropy heatmap — sustained near-random entropy is an established sign of packed or encrypted content, the same signal tools like PEiD look for. Windows executables also get a PE header check for a classic packer tell. It won't name a malware family — no dependable pretrained model exists for that — and it never executes the file: static byte analysis only, up to 5MB.

## At a glance

| | |
|---|---|
| **Also called** | Static Analysis · No Execution |
| **Model or method** | Byte-plot + Shannon entropy (local) |
| **What you give it** | Any file |
| **Files Executed** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/malware-image-triage` |

## Using the tool

### What this tool does
Upload any file (capped at the first 5MB). The tool converts the raw bytes
into the same grayscale "byte-plot" image real malware-visualization
research uses, and computes a sliding-window Shannon entropy heatmap —
sustained high entropy is a genuine, established sign of packed or
encrypted content, the actual technique tools like PEiD and Detect It Easy
use to flag suspicious binaries. If the uploaded file is a Windows
executable (PE), it also checks a classic packer tell: whether the entry
point sits in the file's *last* section (real compilers put it in an early
code section; packers typically don't).

### Purpose
Security analysts doing initial malware triage need a fast, cheap way to
flag "this file is probably packed/obfuscated and deserves a closer look"
before spending real time on deep analysis. Byte-plot visualization and
entropy analysis are the actual, published starting techniques for that —
this tool demonstrates the real signal, not a simulated one. **This never
executes the uploaded file** — it is pure static byte analysis.

### How to use it
1. Click **Choose file** and pick any file (an executable, a document, an
   archive — anything).
2. Click **Analyze**.
3. Review the packed/obfuscated likelihood, overall entropy score, the
   byte-plot image, and (for PE files) the entry-point section check.

### A worked example
Upload a plain text file — the entropy stays low (well under half of the
theoretical maximum of 8 bits/byte) and the byte-plot renders as visibly
structured/repetitive, so the packed likelihood comes back **low**. Now
upload a file of genuinely random bytes (e.g. output from a secure random
generator) — entropy reads consistently high (verified during development
at 7.78–7.84 bits/byte for real \`os.urandom()\` output, close to the
theoretical ceiling), the byte-plot looks like uniform static with no
visible structure, and the entropy heatmap renders almost entirely red
("near-random" everywhere) — likelihood comes back **high**.

### Reading the result
- **Packed/obfuscated likelihood** (low/medium/high, with a 0–100% score)
  — driven by how much of the file's entropy stays sustained-high across
  the sliding window.
- **Overall entropy** — the file's average bits/byte, out of a theoretical
  max of 8 (fully random).
- **Byte-plot** — each byte value mapped to a pixel; structured files show
  visible patterns/regions, packed or encrypted files look like uniform
  noise.
- **Entropy heatmap** — blue is low-entropy (structured), red is
  near-random; a mostly-red heatmap is the strongest visual signal.
- **PE entry-point check** (Windows executables only) — flags when the
  entry point sits in the last section, a classic packer stub tell.

### Notes & limits
- **A screening heuristic, not a malware verdict or a family classifier.**
  High entropy means "likely packed or encrypted," not "malicious" —
  legitimate compressed/encrypted files (a .zip, a video, an already-packed
  legitimate installer) will also read high.
- Analysis is capped at the first 5MB of any uploaded file.
- The PE entry-point check only runs on recognized Windows executables and
  is one classic tell among many real packer-detection signals, not
  exhaustive.
- Never executes, opens, or interprets the uploaded file's actual code —
  only reads its raw bytes.

## What problem it solves

An analyst is handed a binary and has to decide, in the first minute, whether
it is worth an hour. Not "is this malware" — that takes real work — but "does
this look like something that has been deliberately obscured?"

Two cheap static signals answer most of that, and neither requires running the
file:

- **What does it look like?** Raw bytes laid out as a greyscale image produce
  visibly distinct textures. Code, text, padding and compressed data each have
  their own appearance, and a person recognises the difference immediately.
- **How random is it?** Compressed or encrypted data is statistically close to
  noise. Ordinary code and text are not. A binary that is mostly noise has been
  packed, and packing is what you do when you want a signature scanner to find
  nothing.

This tool computes both, plus one structural check on Windows executables, and
shows the evidence. **It never runs the file.** Every operation is a bounded
read of raw bytes — no unpacking, no execution, no sandbox needed because
nothing is executed.

### What it deliberately is not

The original idea was a malware *family* classifier — a CNN over the Malimg
dataset, the standard benchmark for the byte-plot-as-image approach. That was
researched before any code was written and abandoned for concrete reasons: no
suitable pretrained model is available off the shelf, and the Malimg dataset
itself is reachable only through a Kaggle account or an unreliable bulk mirror.
Building a headline feature on either is not something to do quietly.

So the tool ships the technique the field actually uses when there is no
labelled dataset and no trained classifier available: **visualisation and
entropy, presented as evidence for a human**. It produces no verdict on whether
a file is malicious.

## How it works, step by step

1. **Upload a file.** Any bytes. The first 5 MB are analysed.
2. **Byte plot** — bytes are reshaped into a greyscale image, one pixel per
   byte.
3. **Entropy profile** — Shannon entropy is measured in a sliding window across
   the whole file and rendered as a colour strip aligned to file position.
4. **Packing likelihood** — the profile is reduced to a score and a
   low/medium/high label.
5. **PE header check** — if the file is a Windows executable, the section table
   is parsed and one classic packer tell is checked.
6. **Everything is returned as evidence**, with no malicious/benign call.

## The model or algorithm

### Byte plots (Nataraj et al., 2011)

Read the file as unsigned bytes, each one a grey level from 0 to 255, and
reshape into a rectangle. The row width is not arbitrary — it comes from
Nataraj's own file-size table:

| File size | Row width |
|---|---|
| ≤ 10 KB | 32 |
| ≤ 30 KB | 64 |
| ≤ 60 KB | 128 |
| ≤ 100 KB | 256 |
| ≤ 200 KB | 384 |
| ≤ 500 KB | 512 |
| ≤ 1 MB | 768 |
| larger | 1024 |

The width matters because structure in a binary is periodic — tables, aligned
records, repeated instruction patterns — and a width that happens to align with
that period turns the periodicity into visible vertical banding. A poorly
chosen width scrambles it into noise. The published table keeps the aspect
ratio interpretable across sizes.

What you learn to see:

- **Fine-grained speckle with faint vertical structure** — machine code.
- **Long uniform black bands** — zero padding, or a section reserved but not
  filled.
- **Regular light stippling** — ASCII text or string tables, since printable
  characters cluster in a narrow byte range.
- **Featureless high-frequency noise** — compressed or encrypted data.

The tool draws the picture. It does not interpret it, and it does not classify
what is shown.

### Sliding-window Shannon entropy

Entropy over a chunk of bytes:

```
H = − Σ p(b) · log₂ p(b)          over the 256 possible byte values
```

The unit is bits per byte, and the maximum is 8 — reached only when all 256
values are equally likely. English text sits around 4 to 4.5. Compiled x86 code
is typically 6 to 6.5. Compressed or encrypted data lands around 7.9.

The window is 1024 bytes with a stride of 512, so windows overlap by half. The
overlap is there so that a boundary between a low-entropy and a high-entropy
region is not smeared across a single window and missed.

**The window size was the subject of a real bug.**

The first implementation used 256-byte windows. Testing it against genuinely
random bytes from `os.urandom` produced a maximum entropy of about **7.26 bits
per byte**, mean 7.17, across twenty samples — well under the 7.5 threshold
that was supposed to mean "essentially random". The threshold could never fire,
even on perfectly encrypted content.

The cause is not a bug in the code but a property of the estimator. **Shannon
entropy computed from counts is biased downward on small samples.** With 256
bytes spread across 256 possible values, many values simply do not appear by
chance; those zero counts drop out of the sum, and the estimate reads lower
than the true entropy of the source. The bias shrinks as the sample grows.

At 1024 bytes, real random data reliably measures **7.78 to 7.84**, and the 7.5
threshold discriminates properly. The window size was widened, and the
verification numbers are recorded in the source so nobody quietly narrows it
again.

This is a general lesson about entropy on binaries: **a threshold is only
meaningful relative to the window size it was measured at.** Quoting "entropy
above 7.5 means packed" without stating the window is meaningless.

### The packing score

The profile is reduced to a single number in [0,1]:

```
score = 0.6 · clamp( (mean_entropy − 6.0) / 2.0 )  +  0.4 · fraction_of_windows_above_7.5
```

Two terms, deliberately measuring different things. The first is the overall
level, rescaled so that 6.0 bits per byte maps to zero and 8.0 maps to one —
because 6.0 is roughly where ordinary compiled code sits, so anything below it
should contribute nothing. The second is how much of the file is in the
near-random band, which catches the common case of a small low-entropy
unpacking stub followed by a large encrypted payload: the mean stays moderate
while the fraction is high.

Thresholds at 0.33 and 0.66 give low, medium, high. The weights are a
judgement, not a fit to data, and there is no calibration set behind them —
which is exactly why the score is shown alongside the entropy strip rather than
instead of it.

### The PE header check

If the file is a Windows executable, one structural tell is worth checking, and
it is done with Python's `struct` alone — no `pefile` dependency for what is a
few dozen bytes of parsing.

The walk is: `MZ` magic → `e_lfanew` offset at 0x3C → `PE\0\0` signature →
COFF header for the section count → optional header for the entry point
address and its own size → section table.

The question asked is: **does the entry point fall inside the last section?**

A normal compiler places the entry point in an early code section, typically
`.text`. A packer works by compressing the original program into data and
appending a new final section containing the unpacking stub, then rewriting the
entry point to the stub. So the entry point landing in the final section is a
real, long-standing packer signature — one of the checks tools like PEiD and
Detect It Easy have always performed.

Every parse step is bounds-checked, and the whole thing is wrapped so that
`struct.error`, `IndexError` and `UnicodeDecodeError` all return "not a PE"
rather than propagating. That is not defensive padding: **the input is
untrusted and deliberately malformed input is the normal case here.** A parser
in this position that can be crashed by a truncated header is a bug, not an
inconvenience.

## Why these choices

**Why no classifier?** Because an honest one was not available. Without the
dataset there is no training, and without training there is no accuracy figure
— and a malicious/benign verdict with no measured accuracy is worse than no
verdict at all, because someone will act on it.

**Why an image at all, if nothing classifies it?** Because the human reading
the screen is the classifier. Byte plots work as a triage aid precisely because
texture differences are obvious to the eye and awkward to specify in code. The
technique's original value in the Nataraj paper was that malware from the same
family looks alike; the value here is narrower and still real — you can see at
a glance where the structured regions end and the noise begins.

**Why put the entropy strip beside the byte plot?** They are two views of the
same axis. A dark uniform band in the plot should read blue in the strip
(padding); a noisy region should read red. Where the two disagree, something is
worth a closer look.

**Why is the YARA scan advisory rather than blocking?** Every upload passes
through the project's shared file gate. In most tools a YARA match rejects the
file. Here it cannot: analysing suspicious-looking files is the entire purpose,
so a match is logged as a security event for the operator's visibility and the
analysis proceeds.

**Why cap at 5 MB?** Real malware samples are typically small, the entropy
profile is dominated by the first megabytes anyway, and an unbounded byte plot
of a 500 MB file is neither computable in a request nor readable. Truncation is
reported in the response rather than performed silently.

## How to read the output

**The colour strip is positional.** Left is the start of the file, right is the
end, and colour runs blue (low entropy) through yellow to red (near random).
The shape tells the story:

- **Mostly blue, red at one end** — a normal file with an appended compressed
  or encrypted blob.
- **Blue prologue, then red for the rest** — the classic packer layout: a small
  stub followed by the packed payload.
- **Uniformly red** — the whole file is compressed. Perfectly normal for a ZIP,
  a JPEG, or a PNG, and completely unremarkable.
- **Mostly mid-range with structure** — ordinary code and data.

**High entropy is not suspicious on its own.** Every compressed archive and
every media file scores high. Entropy is suspicious when it appears where it
should not — inside the code section of an executable, in a document, in a
region a normal file format would not compress.

**The PE check is one bit.** Entry point in the last section is a real tell,
but legitimate installers and some protection systems do it too. Combine it
with a high entropy score before treating it as anything.

**No output here means a file is safe.** Verified during testing: a plain text
file scored low with 0% of windows above threshold, and a file of random bytes
scored high with 94% and a uniformly red strip. Both are correct, and neither
is a malware verdict.

## Limits

- **No malicious/benign classification and no family attribution.** By design,
  for lack of an honestly-obtainable trained model.
- **High entropy has many innocent causes** — every archive and media format.
  On its own it means "compressed", not "malicious".
- **Low entropy proves nothing.** Plenty of malware is not packed at all, and a
  simple script is entirely readable.
- **PE only** for the structural check. ELF, Mach-O and everything else get the
  byte plot and entropy alone.
- **The packing score's weights and thresholds are judgement calls**, not
  values fitted to a labelled corpus.
- **Only the first 5 MB** is examined; a payload beyond that is invisible.
- **Static analysis only.** Anything that reveals itself at run time —
  network behaviour, dropped files, injected processes — is out of reach, and
  that is the trade for the tool being completely safe to use.
- **Entropy thresholds are window-size dependent.** The numbers here are
  specific to the 1024-byte window.

## Likely interview questions

**"What is Shannon entropy on a binary actually telling you?"**
How uniformly the 256 possible byte values are distributed in a region,
expressed in bits per byte with a maximum of 8. It is a compressibility
measure: 7.9 means the data has almost no redundancy left, which happens when
it has already been compressed or encrypted. Text sits near 4.5, compiled code
around 6 to 6.5. It says nothing about intent — only about how much structure
remains.

**"Your entropy threshold never fired. What was wrong?"**
The window was too small. Entropy estimated from counts is biased downward on
small samples, because with 256 bytes across 256 possible values many values
are absent by chance and drop out of the sum. Real random data measured only
7.17 on average at a 256-byte window, so a 7.5 threshold was unreachable.
Widening to 1024 bytes brought random data to 7.78–7.84 and made the threshold
meaningful. The general point is that an entropy threshold is only defined
relative to its window size.

**"Why a sliding window instead of one number for the file?"**
Because location is the signal. A packed executable is a small low-entropy stub
followed by a large high-entropy payload; averaged over the file that looks
unremarkable. The profile shows *where* the randomness starts, which is both
the tell and the thing an analyst needs in order to know where to look next.

**"Why is the entry point being in the last section suspicious?"**
Compilers put the entry point in an early code section. A packer compresses the
original program into data, appends a new final section holding the unpacking
stub, and rewrites the entry point to point at that stub — so execution begins
in the last section. It is one of the oldest packer heuristics, and it is one
bit of evidence rather than a verdict, since some legitimate installers and
protectors do the same.

**"Is it safe to analyse malware this way?"**
Yes, because nothing is executed and nothing is parsed with a library that
could be exploited by a crafted file. It is a bounded read of bytes, a
histogram, and a hand-written header walk with every field length-checked and
every parse failure caught. The whole reason for hand-rolling the PE parsing
rather than pulling in a dependency is that the attack surface is a few dozen
lines I can read, on input that is deliberately hostile.

**"Where does this fit in a real triage pipeline?"**
At the very front, as the cheap filter. It costs milliseconds, needs no
sandbox, and tells you which samples are obfuscated enough to be worth the
expensive stages — signature scanning, static disassembly, then dynamic
analysis in an isolated environment. Its job is to rank a queue, not to make a
decision, which is why the output is evidence and a score rather than a verdict.

**"How would you turn this into a real classifier?"**
Take the byte plot, extract texture descriptors — GIST features in the original
Nataraj work, or a small CNN — and train on a labelled family corpus like
Malimg. Reported accuracy on that benchmark is high, but it comes with two
serious caveats I would state up front: the classes are families rather than
malicious-versus-benign, so it answers a different question; and it is trivially
evadable, since an author who knows the visual signature can pad or reorder
sections to change the texture without changing behaviour. That is one of the
reasons this tool stopped at evidence.
