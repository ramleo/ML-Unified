Chapter 38Text-to-Image Generator


> Type a description and get an image back — no input photo needed, just a prompt. This one runs on Gemini's paid image model, so a small daily generation budget applies to keep the API cost predictable.

## At a glance

| | |
|---|---|
| **Also called** | Describe It, Generate It |
| **Model or method** | Gemini (gemini-3.1-flash-lite-image) |
| **What you give it** | Text prompt |
| **Prompt In** | 1 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/text-to-image` |

## Using the tool

### What this tool does
Type a description and get an image back — no input photo needed, just a prompt.
It generates on Gemini's paid image model, so a small **daily generation budget**
applies to keep the API cost predictable. You can refine a result with a follow-up
edit instruction, compare versions side by side, and browse what you've made.

### Purpose
Most of this site's vision tools transform a photo you upload; this one is the
pure-generation counterpart — it makes an image from words alone. It shows what a
modern text-to-image model produces, with honest guardrails: a visible budget so a
public tool can't run up an open-ended bill.

### How to use it
1. Type a **prompt** describing the image you want (be specific — subject, style,
   lighting, composition).
2. Pick any **options** offered (e.g. aspect ratio) and click **Generate**.
3. To refine, give a short **edit instruction** (e.g. "make it night-time") — it
   generates a new version from your current one rather than starting over.
4. Use the **comparison grid** to see versions together, and the **history panel**
   to revisit earlier generations.

### A worked example
Prompt: *"a cozy reading nook by a rain-streaked window, warm lamp light, watercolor
style."* Generate, then edit with *"add a sleeping cat on the chair"* — the follow-up
keeps the scene and adds the cat. Open the comparison grid to put the two side by side.

### Reading the result
- The returned image is a **JPEG** (the model returns JPEG for pure generation, not
  PNG) — expected, not a bug.
- Each generation and edit is a separate entry in **history**, so you can step back to
  any earlier version.

### Notes & limits
- **Paid model, daily budget.** Generation uses a paid Gemini image model, so there
  is a per-day cap shared across visitors; when it's reached, try again the next day.
- **Prompt quality drives output.** Vague prompts give generic results; specific
  subject + style + lighting cues help a lot.
- **Generative, not factual.** It invents pixels — it is for creative imagery, not for
  producing accurate diagrams, text, or real people.

## What problem it solves

Every other Computer Vision tool in this book takes a picture and tells you
something about it. This one goes the other way: you type a sentence and it
gives you a picture that did not exist.

That inversion is why it is here. It is the app's only **generative** vision
tool, and it is also the only one that costs real money per use — which turns
out to be the more interesting engineering problem, and the one worth being able
to talk about.

## How it works, step by step

1. **Type a prompt.** Up to 2,000 characters.
2. **Optionally shape it.** Pick a style, an aspect ratio, and a negative prompt
   — things to keep out of the picture, up to 500 characters.
3. **Optionally have the prompt written for you.** *Enhance* sends your short
   phrase to a text model and gets back a fuller description.
4. **Or start from a picture instead of a phrase.** *Describe image* sends an
   image you upload to a vision model, which returns a prompt describing it —
   useful for matching a style you can see but cannot name.
5. **Generate.** The server checks its daily budget, assembles the final prompt,
   makes one call to Gemini's image model, and returns the image bytes with
   their real MIME type.
6. **Keep or continue.** The last six images are kept in your browser. Any of
   them can be sharpened, edited by a further instruction, or compared side by
   side against another generation.

## The model or algorithm

The image model is `gemini-3.1-flash-lite-image`, called over Google's
Generative Language API. This tool does not train, fine-tune or run a diffusion
model of its own — it is a client. So the engineering worth explaining is what
sits either side of that call.

### The prompt is assembled on the server, from a fixed vocabulary

Style and aspect ratio are **not** free text. The client sends a key —
`watercolor`, `landscape` — and the server looks it up in a fixed table and
appends a known-good phrase:

```python
_STYLES = {
  "photorealistic": "in a photorealistic photographic style",
  "watercolor":     "in a soft watercolor painting style",
  "anime":          "in a vibrant anime/manga art style",
  ...
}
```

The reason is stated in the code: a client can only ever pick a key, never
inject arbitrary text into that part of the prompt. Building the final string
server-side is the same instinct as never trusting a client-supplied SQL
fragment — the user's own prompt is theirs to write, but the scaffolding around
it is not.

### The budget — the real engineering here

Each image costs roughly four cents. A text box that generates one is an
invitation to press the button forty times in a row, and nobody doing that
intends to run up a bill.

So every call passes through `check_and_record_call`, which keeps a per-day
counter and refuses once the cap is hit. There are **three separate pools**, and
the separation is the interesting part:

| Pool | Cap/day | Used by |
|---|---|---|
| `shared` | 40 | sharpen and AI-fill — both **edit an image you already have** |
| `text2img` | 15 | this tool |
| `species_id` | 30 | the plant identifier |

Text-to-image gets its own smaller pool deliberately. The reasoning recorded in
the code: a free-text generator invites casual re-rolling with no reuse value
per call, and if it shared the editing pool, an afternoon of experimenting would
exhaust the budget and leave sharpen and AI-fill dead for everyone else for the
rest of the day. **Separate pools mean one tool's failure mode cannot starve
another's.**

The module is candid about where it came from: it was built after repeated
live-testing across one debugging session ran the billing account down toward
its limit — each individual call reasonable, never totalled up. It is also
candid about its limit: the counter is in memory, so a restart resets it. The
argument for accepting that is precise — the failure mode being guarded against
is a *same-day burst*, and a restart resetting the count does not enable one.

### Two live findings recorded in the code

Both are the kind of thing you only learn by making the call, and both are
written down where the next person will find them.

**The response is JPEG, not PNG.** Every other caller of this model in the
codebase attaches an input image and gets PNG back. A text-only request returns
`mimeType: "image/jpeg"`. So the endpoint returns the response's *actual* MIME
type rather than assuming — and the edit path re-encodes to PNG before sending
the image to sharpen or AI-fill, because those endpoints expect PNG.

**Seeds do not work, and were removed.** Passing `generationConfig.seed` is
accepted without error, so it looks like it works. Two calls with the identical
prompt and seed 42 returned genuinely different images — different SHA-256,
different byte lengths, 546,436 against 539,208. The code carries an explicit
instruction not to re-add the field without new evidence. This is the honest
version of a negative result: the API accepted the parameter and did not honour
it, and only a byte-level comparison of two responses would have caught it.

### Enhance and Describe run on a different, free path

Both are plain text or vision completions, not the billed image model, so
neither touches the budget. They use the same provider cascade as the rest of
the app — Mistral, then Gemini, then Cohere, each with its own server key,
taking the first that answers. If every provider is unavailable, *Enhance*
returns your original prompt with `ok: false` rather than an error, so a flaky
free tier can never block you from generating with what you already typed.

### No content pre-check, deliberately

There is no safety filter in front of the model, and the code says why: the
sharpen and AI-fill endpoints already pass arbitrary user text to the same model
with no filtering, a safety refusal already lands in the existing "no image
part" error path, and a custom pre-check would itself be a second billed call —
working directly against the cost discipline the budget exists to enforce.

## Why these choices

**Why a separate, smaller pool.** Answered above, and it generalises: when two
features share a limited resource, the one with the cheaper failure mode should
not be able to consume the other's share.

**Why the enhance cascade degrades to the original prompt.** A helper that fails
loudly and blocks the main action is worse than one that quietly does nothing.

**Why history is capped at six.** The images are base64 strings in
`localStorage`, which has roughly a 5 MB quota. Six is what fits with room to
spare, and the write is wrapped so that exceeding the quota loses the history
entry rather than breaking the tool.

**Why history is populated after mount, not during render.** Reading
`localStorage` during the first render caused a genuine hydration mismatch — the
server has no `localStorage`, so its HTML and the browser's first render
disagreed. The state starts empty to match the server, and fills in afterwards.

**Why grid variations are not each saved to history.** They would fill the small
budget with near-duplicates of one prompt.

## How to read the output

- **A budget message is not an error.** *"Daily text-to-image budget reached (15
  calls) — resets at UTC midnight"* means the cap did its job. It is a project-
  wide cap, not a per-user one.
- **The image is JPEG.** If you are chaining it into something that expects PNG,
  convert first — which is what the built-in edit buttons do for you.
- **The same prompt twice gives different images.** That is the model, not a
  bug, and there is no seed that will fix it. Generate variations and pick.
- **Negative prompts are advisory.** They are appended as text, not enforced as
  a constraint. The model usually respects them and sometimes does not.
- **Style and aspect ratio are prompt text too** — the aspect ratio asks the
  model to *compose* for 16:9, it does not set the output dimensions.
- **`ok: false` from Enhance** means every text provider was unavailable and you
  are looking at your original prompt.

## Limits

- **A hard daily cap of 15 generations** across everyone using the site.
- **No reproducibility.** No working seed, so an image you liked cannot be
  regenerated — save it.
- **The aspect ratio is a request, not a setting.**
- **No image dimensions, quality or step controls.** Those belong to a diffusion
  model you host yourself; this is one API call.
- **No content filtering in front of the model.** Refusals come back from the
  provider as a failed call.
- **History is per-browser, capped at six**, and lost if site data is cleared.
- **The budget counter is in memory** and resets when the Space restarts.
- **You are renting a model, not owning one.** If Google deprecates
  `gemini-3.1-flash-lite-image` or changes its pricing, this tool changes with
  it. That is the trade for not hosting a GPU.

## Likely interview questions

**"You built a feature that costs money per call. How did you stop it running
away?"**
A daily cap enforced server-side before the call, and — the part I would
emphasise — **three separate budget pools** rather than one. The generator gets
its own smaller pool because free-text generation invites casual re-rolling with
no reuse value, and sharing a pool would let an afternoon of experimenting kill
the editing features for everyone else. It was built after a real incident where
live-testing during one debugging session ran the billing account down; each
call was individually reasonable and nobody totalled them up.

**"Your budget counter is in memory. Isn't that broken?"**
It is a known gap and I would rather state it than hide it: a restart resets the
count, so a determined attacker could exceed the cap by waiting one out. But the
failure mode it was built for is a same-day burst — a hundred rapid calls in one
session — and a restart does not enable that. A durable counter needs a database
this deployment does not have. It is an accepted trade with a stated reason, not
an oversight.

**"How did you find out the seed parameter didn't work?"**
By checking rather than trusting. The API accepted `generationConfig.seed`
without an error, which is exactly what a working parameter looks like. Two
calls with the same prompt and seed came back with different SHA-256 hashes and
different byte lengths. The feature was removed and the finding written into the
module docstring with the numbers, so nobody re-adds it on the assumption that
an accepted parameter is an honoured one.

**"Why not run Stable Diffusion yourself instead of paying per image?"**
Because it needs a GPU, and this whole app runs on free-tier CPU hosting. Self-
hosting buys reproducible seeds, no per-call cost, full control of resolution
and steps, and no dependency on someone else's deprecation schedule — at the
cost of a machine that costs more per month idle than this API costs per year at
15 images a day. Given the traffic, renting is the right call; at scale the
maths flips.

**"Why is the style a key rather than free text?"**
So the client can never inject arbitrary text into the prompt the server sends.
The user's own description is theirs, but the scaffolding around it — style,
aspect ratio — is assembled server-side from a fixed table. Same instinct as not
letting a client supply a fragment of a SQL query.
