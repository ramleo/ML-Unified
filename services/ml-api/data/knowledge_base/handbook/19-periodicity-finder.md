Chapter 15Periodicity Finder


> Paste a numeric series or a list of event timestamps and it finds the strongest repeating cycle — the 'every 7 days', 'every 24 hours', 'every 12 steps' pattern hidden in the data. A Fast Fourier Transform, run after detrending and a Hann window, turns the series into a spectrum; the dominant peaks are the cycles, each with a strength above the noise floor. Numeric series report cycle length in samples, timestamps in real time units. Nothing is uploaded — it runs entirely in your browser.

## At a glance

| | |
|---|---|
| **Also called** | Find the Hidden Cycle |
| **Model or method** | Radix-2 FFT · Hann window (no library) |
| **What you give it** | A numeric series or a list of event timestamps |
| **Spectrum** | FFT |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/periodicity-finder` |

### What this tool does
It looks for a **repeating cycle** hidden in a series of numbers or a list of
event timestamps — the "every 7 days", "every 24 hours", "every 12 steps"
pattern that's often invisible in a raw column of data. It's the same idea used
to find seasonality in analytics traffic, load cycles in a server metric, or a
rhythm in any measurement over time.

### The technique (real DSP, not invented here)
The engine is a **Fast Fourier Transform (FFT)** — the standard way to turn a
signal from "value over time" into "how much of each cycle length is present".
Before the transform it removes the average (so a flat offset doesn't dominate)
and applies a **Hann window** (a standard taper that stops the ends of your
data from smearing the result). The strongest peaks in the resulting spectrum
are the dominant cycles, and each peak's **strength** is how far it stands above
the typical noise level in the spectrum.

### Two ways to give it data
- **A numeric series** — one number per line (e.g. daily visit counts, an
  hourly temperature, a sensor reading). The data is treated as evenly spaced,
  and cycle lengths come back in **samples** (i.e. rows — if each row is a day,
  "7 samples" means a weekly cycle).
- **A list of timestamps** — one event time per line (ISO like
  \`2026-01-01T09:30:00Z\`, a date, or a unix epoch). These are automatically
  binned into an even timeline of event counts, and cycle lengths come back in
  **real time units** ("~7.0 days", "~24.0 hours").

The mode is picked automatically from what you paste. Click **Load sample** to
see a worked example (event timestamps with a built-in weekly rhythm).

### Reading the result
- **The verdict** — "Strong cycle", "Possible cycle", or "No clear
  periodicity", based on how far the top peak stands above the spectrum's noise
  floor. Pure noise typically tops out around 3× the median; a real repeating
  signal is many times higher.
- **The dominant cycles** — up to three, strongest first, each with its cycle
  length and strength.
- **The spectrum chart** — magnitude at each cycle length; the detected peaks
  are highlighted.

### What this is (and isn't)
This is a real frequency analysis, but it's a **heuristic read**, not a
forecasting model or a statistical significance test. It finds the cycle
lengths present in *the data you paste* — it doesn't predict future values, and
it can't tell a genuinely meaningful cycle from a coincidental one in a short or
noisy series. It needs at least 8 data points, and works best with several full
repeats of the cycle you're hoping to find. A "No clear periodicity" result
means no single cycle dominated — not that the data is definitely random.
