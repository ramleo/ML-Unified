Chapter 36Scan Descreen


> Upload a scanned page or a photo of print or a screen and remove the periodic halftone/moire ripple that scanning leaves behind. A 2D Fast Fourier Transform finds the sharp periodic spikes in the image's frequency spectrum — the tell of a print screen — notches them out with a soft filter, and transforms back. Non-generative: it only subtracts periodic energy that is genuinely present, so it cannot invent detail, and an image with no screen pattern comes back unchanged. Shows the before and after and the spectrum with the removed peaks circled.

## At a glance

| | |
|---|---|
| **Also called** | Remove Screen Patterns |
| **Model or method** | 2D FFT · soft notch filter (numpy) |
| **What you give it** | One scanned or screen-photographed image |
| **Notch Filter** | FFT |
| **Where it runs** | On the server |
| **Find it at** | `/tools/scan-descreen` |

### What this tool does
Printed material is made of a fine grid of dots (a **halftone screen**). When you
scan or photograph print, that grid interferes with the sensor's own grid and
leaves a repeating ripple — a **moire / screen pattern** — smeared across the
whole image. This tool removes it, so text and detail read more cleanly.

### How it works (classic DSP, non-generative)
A repeating pattern shows up as a few sharp, isolated **spikes** in the image's
2D Fourier (frequency) spectrum, sitting away from the centre where the real
picture content lives. The tool:
1. Transforms the image to its frequency spectrum (FFT).
2. Finds spikes that stand far above their local surroundings — the tell of a
   periodic screen — while protecting the low-frequency centre (real content).
3. **Notches out** each spike (and its mirror) with a soft filter and transforms
   back to a cleaned image.

Because it only *subtracts* periodic energy that is genuinely there, it **cannot
invent detail** — unlike a generative "AI enhance". If there's no screen
pattern, nothing is removed and the image comes back unchanged.

### How to use it
1. Click **Choose image** and pick a scanned page or a photo of a screen/print.
2. Click **Descreen**. It runs the FFT and notch filter on the server (a few
   seconds) and returns the result.
3. Compare **Before / After**, and look at the **spectrum** — the circled points
   are the periodic peaks that were removed.

### Reading the result
- **"N periodic patterns removed"** — N sharp screen frequencies were notched.
  The spectrum image circles exactly which ones.
- **"No periodic pattern found"** — no spike stood far enough above the noise
  floor; the image is returned essentially unchanged. That's the honest result,
  not a failure.

### What this is (and isn't)
- It targets a **strong, sharp, repeating** pattern. A very faint screen may sit
  below the detection threshold and be left in place.
- A notch filter **cannot tell a print screen from genuinely repetitive real
  content** — a striped shirt, a brick wall, or fabric weave are real periodic
  textures and could be partially removed. Always check the After image.
- It works on the image at up to ~1024px on the long edge (larger images are
  scaled down first), and it is not a substitute for a clean re-scan when one is
  possible.
