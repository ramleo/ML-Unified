# Session 2026-08-31 (Part 267) — the handbook learns to talk: read-aloud, guided demos, recorded clips, and a backend bug that had been rejecting every real file

Continues Part 266 (`Session_2026-08-30_HandbookReadabilityAndPhoneEdition_Part266.md`),
which finished making the handbook readable. This one is about making it
demonstrable. No chapter text changed.

---

## 0. Where things stand in one paragraph

The handbook can now read itself aloud, and three of its chapters can show
the tool they describe actually working — live in an iframe, or as a recorded
clip, narrated either way, in whatever voice the reader picks including one
from a provider they pay for themselves. Recording those clips is what found
the serious thing in this session: `/rag/mm-ingest` had been rejecting every
compressed file since 29 August, which is every real PDF, image, video and
audio file the Multimodal RAG tool exists to accept. That is fixed and
deployed. Six commits, five in ml-portfolio and one in ML-Unified.

---

## 1. The commits

| Commit | Repo | What |
|---|---|---|
| `122175a` | ml-portfolio | read the handbook aloud with the browser's own voice |
| `a8bad14` | ml-portfolio | guided demos — the real tool, walked through, narrated |
| `6974290` | ML-Unified | **the ingest fix** — stop rejecting every real PDF, image, video and audio file |
| `f75ac6f` | ml-portfolio | the first two recorded clips, and two fixes recording exposed |
| `ddc3a0e` | ml-portfolio | the Multimodal RAG clip, and a recorder that cannot narrate a lie |
| `127e6b7` | ml-portfolio | choose who narrates a demo, recorded clips included |
| `ffad41b` | ml-portfolio | any TTS provider, not a list this project picked |

`6974290` was uploaded to the HF Space in the same response as its push, per
the standing rule. Nothing else this session touched `services/ml-api/**`.

---

## 2. What the owner asked for, in order

1. "can you add audio to handbook?"
2. "use different voice, this voice breaks at every step"
3. "need some clarity in voice"
4. "are you saying that the audio uses uaer's system's voice variant?"
5. "can you add video instructor which can visually show or explain what the
   features mentioned in handbook?" — then, choosing from the options offered,
   "can we combine A and B?...also can you add option of paid avatar presenter,
   just in case in future i go for paid subscription?", pilot on the flagship tools
6. "say it in simple words asshole....what you are asking"
7. "what's this?" — about the stale claim in the safeguard plan file
8. "yes please" — install Playwright and record the clips
9. "Bundle a sample PDF and ingest it", "be careful with LLM calls"
10. "One more run", then "if we Re-record with corrected narration, will that be
    enough?" and "yes"
11. "In auto ml pipeline video, can we have option to select the voice?"
12. "what i meant was there should also be option to user to provide their own
    api key on UI itself"
13. "why only these keys?" → "see, api key can be from any provider, dont just
    restrict to some api keys"
14. "document above conversations to Conversations/"

---

## 3. Reading the handbook aloud

A **Listen** bar on `/handbook` that speaks the chapter the reader is on,
highlights the sentence being read, and skips tables and code.

Not a hosted audio file, and the arithmetic is why: the book is roughly
140,000 words, about fifteen hours of speech and several hundred megabytes of
MP3. Generating that at any TTS vendor is a real bill and hosting it is worse.
`speechSynthesis` is already in every browser, costs nothing, needs no
backend and works offline.

Two things separate this sounding broken from sounding continuous, and both
were learned by listening:

- **Utterances are queued three deep.** `speechSynthesis` runs straight from
  one utterance into the next *only if the next is already in its queue*.
  Waiting for `end` before calling `speak` leaves an audible gap at every cut,
  which is exactly what "breaks at every step" meant.
- **The text is cleaned first.** This book uses hundreds of em dashes and a
  synthesiser reads each one as a hard stop mid-clause. Em/en dashes and
  middots become commas, ellipses become stops, smart quotes are dropped,
  URLs are read as "a link".

Also: the voice list ranks Enhanced/Premium/Natural variants above their
compact twins and defaults to the best installed rather than inheriting the
OS default; novelty voices (Bad News, Zarvox, Bubbles) are filtered out —
41 voices became 22.

**The honest ceiling.** The voice belongs to the visitor's operating system,
so two people hear two different narrators. Measured on this machine:
`say -v '?' | grep -ic enhanced` → **0**. Every English voice installed here
is the compact variant, which is why it sounded muddy no matter what the code
did. Downloading an Enhanced voice in System Settings fixes it for this
machine and changes nothing for anyone else.

---

## 4. Guided demos — one script, three consumers

A **"Watch this work"** button under any chapter that has a demo. It opens the
real tool and walks through it: a spotlight over the actual control, a caption,
narration.

```
src/data/demos/*.json      what to say, what to point at, what to do
  ├─ HandbookDemo.tsx          plays it live in an iframe
  ├─ scripts/record-demo.mjs   replays it under Playwright and records it
  └─ src/lib/presenter/        decides who narrates
```

The scripts are **JSON rather than TypeScript** precisely so the Node recorder
can read the same file the browser does. A clip can never describe a tool
differently from the live walkthrough.

Same origin is what makes the live version real rather than a video: the
player can reach `iframe.contentDocument`, measure a control, spotlight it,
type into it and drop a file into it. Two things it deliberately will not do —
press a button that spends money, and restyle the page it is demonstrating
(the spotlight is drawn in the outer document, over the iframe).

Steps target **`data-wt` anchors**, extending a convention Text-to-SQL's own
walkthrough already used. Anchors survive a restyle; class names do not. Three
tool files gained one attribute each and nothing else moved.

**Pilot chapters:** AutoML Pipeline, Multimodal RAG, Text-to-SQL.

---

## 5. Who narrates — and the swap point for a paid one

`src/lib/presenter/` is one interface and one `getPresenter()`. Everything
else asks for "the presenter" and never names an implementation, so adding
another is one file.

| | |
|---|---|
| `voice.ts` | the browser's synthesiser — free, always there |
| `avatar.ts` | hosted talking head, configured server-side; documented stub |
| `hosted.ts` | a vendor the **viewer** pays for, key entered in the UI |

**Why the paid option is text-to-speech and not a talking head.** An avatar API
(HeyGen, D-ID, Synthesia) renders asynchronously — post a script, poll a job,
get a video back seconds or minutes later. That cannot narrate a clip that is
already playing. A neural TTS endpoint answers one POST with audio, which is
fast enough to speak a line on its cue, and a clear voice is what people
actually mean when they say the browser sounds poor.

**The provider list was wrong and got deleted.** The first version offered
ElevenLabs and OpenAI because they are well known. Counting the keys this
project actually uses settled it:

```
gemini_api_key     27
mistral_api_key     9
groq_api_key        9
cohere_api_key      9
anthropic_api_key   6
openai_api_key      4
```

No ElevenLabs anywhere. The offered list managed to include a vendor the owner
does not use and exclude the two they use most. So a provider is now **data** —
a URL, which header carries the key, a request body, and where the audio is in
the reply — and every field is editable. The named entries are prefilled forms,
not privileges. Anthropic, Mistral and Cohere have no TTS product at all, so
they were never candidates.

Two things the general shape forced, both real:

- A reply is not always the audio. Some vendors answer with JSON carrying
  base64, so a dot path to it is one of the fields.
- Raw PCM has no container and no browser will play it. Gemini returns signed
  16-bit mono PCM, so a WAV header is written in front of it when a sample
  rate is given.

The key is held in memory only — never storage, never this site's backend.
Settings *are* remembered on the device: a URL and a body template are worth
not retyping, a credential is not worth leaving on a disk.

---

## 6. THE SERIOUS ONE — `/rag/mm-ingest` rejected every real file

Recording the Multimodal RAG demo failed. The upload came back:

```json
{"detail":"This file matched a security pattern (High_Overall_Entropy) and was rejected."}
```

`mm_ingest.py:356` blocked on **any** YARA match. One of the built-in rules is
`High_Overall_Entropy`, which fires above 7.5 bits/byte — the defining property
of every compressed format. Measured against the live Space:

| File | Size | Entropy | Result |
|---|---|---|---|
| One of this site's own thumbnails (`.webp`) | 2.7 KB | 7.940 | **rejected** |
| An ordinary PDF | 106 KB | 7.947 | **rejected** |
| `test_invoice.pdf` (tiny, uncompressed) | 1.6 KB | — | passed |

So the route refused essentially every PDF, JPEG, PNG, WebP, MP4 and MP3 it
was given — the entire input of the tool. Only a trivially small uncompressed
file got through. **Live since 29 August (`c0ab0a2`).**

Two comments already in the codebase said this must not happen. The rule's own
description: *"also true of ordinary compressed formats (zip/jpg/etc.), so this
is informational, not a verdict on its own."* `file_gate.py`'s docstring:
*"deliberately a WARNING/advisory gate, not a hard block."* The caller ignored
both.

**The fix** (`6974290`) does not special-case a rule name at the call site.
The ruleset now says which of its rules describe a property rather than
evidence of intent (`ADVISORY_RULES`, next to the rules), and `file_gate` grows
`blocking_matches()` so a caller that blocks asks a function instead of testing
a list for truthiness. Advisory matches are still scanned for, still returned,
still logged — they just no longer decide the request.

**Audited every other caller:** 31 other call sites log and continue.
`mm_ingest` was the only route affected.

**Verified after the deploy, both directions:**

| | |
|---|---|
| Clean PDF | ingests — `"step": "extract", "status": "done"` |
| Same PDF with the EICAR signature appended | **rejected** — `EICAR_Test_File` |

Real signatures still block; a property every compressed file shares no longer
does. (The first EICAR probe was a false pass — the `%` escapes in the printf
were wrong, so the string was not EICAR at all. Worth remembering: a negative
security test that passes may just be a broken test.)

---

## 7. Recording the clips — three lies and the fix for all of them

The recorder replays the same JSON under Playwright, injects the same
spotlight and caption, records WebM, and muxes narration from `say` + ffmpeg.
Playwright is installed with `--no-save` and stays **out of package.json**:
recording is a local authoring step, and Vercel must not install browsers on
every deploy.

**Three separate clips shipped narration describing something that had
silently failed.** Each had a different immediate cause and the same root one —
the recorder swallowed failures and hoped.

| What went wrong | Why | Fix |
|---|---|---|
| Text-to-SQL's own first-visit tour ran on top of the demo | two walkthroughs on one screen | a demo declares which to silence (`"suppress"`), set before the iframe mounts / in an init script |
| "on the left is the schema it can see" — nothing had loaded it | narration described an intention, not a state | step 2 now clicks Load Schema; step 3 speaks to a panel really showing Album 347, Customer 59, Track 3,503 |
| the question was never typed, the send never clicked | the locator matched `[data-wt=X] input` — a *descendant* — but MMRAG marks the textarea itself | match the anchor whether it **is** the field or contains one |
| all three were invisible | every action was wrapped in `.catch(() => {})` | actions fail loudly and abort the run |
| a backend call failed mid-recording and the page still looked plausible | nothing checks the rendered page | a step asserts what must be on screen (`"expect"`) — this caught a real `Failed to fetch` before it became a clip |
| audio drifted ahead of the picture | audio padded to narration+settle, but a `waitFor` step runs far longer | pad to the **measured** length of each step |
| the answer was off-frame | 1280×800 too narrow for a document viewer plus a chat column | 1600×1000 |

**The sample PDF was also wrong.** As vector SVG it produced no figure chunk
at all, which made the chapter's central claim untrue for that file. Rebuilt
with the chart as a raster image: `1 text · 2 table · 1 figure`.

**And the narration philosophy was wrong.** "The citation is the chart" turned
out false — the answer cited a *table*, because the chart-extraction feature had
pulled the chart's values into one. A model's output varies every run, so
anything a clip asserts about it will eventually be false. The chart-to-table
detail moved to the step about ingestion, which is a property of the file and
cannot drift; the step about the answer now describes the mechanism only.

**Cost, honestly: 6 full recording runs of Multimodal RAG plus 2 probe
ingests.** The owner had said "be careful with LLM calls". Three of those runs
were wasted on my own bugs, not on anything unpredictable. AutoML and
Text-to-SQL cost nothing — neither demo calls a model.

---

## 8. Choosing the voice on a recorded clip

A recorded clip carries one voice in its audio track, and browsers cannot
switch between the audio tracks of an HTML5 video. So "pick a voice" for a clip
can only mean: mute the track and say the lines again as it plays.

Each clip ships a small timings file saying when each line begins.
**"As recorded" stays the default on purpose** — the baked track is a known
quantity, and a viewer whose machine has only compact voices should not be
quietly downgraded.

Narration follows the video's own `currentTime`, not a timer started at
`play()`. A timer drifts the moment the viewer touches the scrub bar; this way
pausing, seeking and buffering stay in step, and scrubbing into the middle
speaks the line that belongs *there*.

**The timings for the three existing clips were recovered, not re-recorded.**
`scripts/demo-timings.mjs` reads the silence between lines and refuses to write
anything if the gap count disagrees with the step count. Re-recording
Multimodal RAG costs a real document ingest, which is not a thing to spend on
a metadata file. New recordings write timings directly from what the recorder
already measures.

Three bugs in the first wiring of the paid path, all found by testing rather
than reading:

- The presenter was resolved **once**, when the dropdown changed — before any
  key had been typed — so it captured the browser voice and the vendor was
  never called at all. Now resolved per cue.
- A `byo:elevenlabs` selection was handed to the browser presenter as though it
  were a voice ID, and silently matched nothing.
- Selecting a paid vendor muted the clip immediately, before a key existed, so
  it went quiet with nothing to replace it. The key is now lifted into the
  panel and the clip keeps its own audio until a usable narrator exists.

---

## 9. How each change was verified

| Claim | Evidence |
|---|---|
| Read-aloud works | speaking, block-to-block highlight, pause/resume/stop, 4,264 readable blocks, 94 tables skipped |
| Best voice chosen, not OS default | picked Samantha; 41 voices → 22 after filtering novelty |
| Demo buttons land correctly | 3/3 — `ch-1`, `ch-14`, `ch-15` |
| Live demo really drives the tool | AutoML reached Config: **240 rows, 10 columns**, target `churned` |
| Text-to-SQL typing | question really in the box; all 5 anchors resolve |
| Ingest fix | clean PDF ingests; EICAR-laced PDF rejected as `EICAR_Test_File` |
| Multimodal RAG clip | `1 text · 2 table · 1 figure`, answer **"Dundee had the lowest on-time delivery rate at 65.8%"** — a number that appears nowhere in the document's text |
| Voice override | choosing Daniel mutes the clip and speaks steps 2 and 3 on cue; scrub to 20s re-speaks step 3; back to "As recorded" unmutes and goes quiet |
| Any provider works | an invented endpoint with `{key}` in the query string, a custom header name, a custom body, audio read from `result.audio` — all sent exactly as configured |
| Key never persisted | after configuring, localStorage holds the endpoint and the key appears in no storage key |
| Gates | `tsc`, `eslint`, `next build`, 400-line check all pass at every commit |

**Still untested against a live paid vendor.** No key was ever used; that costs
money that is not mine to spend. The presets use the vendors' documented
request shapes, the source says `UNTESTED AGAINST A LIVE VENDOR` where it
matters, and a failure falls back to the browser voice showing the vendor's own
error text.

---

## 10. Things worth carrying forward

- **A demo is the best test of a tool.** The ingest bug had been live for two
  days and surfaced only because something tried to use the tool end to end.
  Nothing else — no unit test, no page load — would have caught it.
- **`.catch(() => {})` around an action in a recorder is how a lie gets
  shipped.** Three times. An action that cannot be carried out is a broken
  demo, not a slightly different one.
- **Assert the world, not the script.** No care while writing narration catches
  a backend having a bad day mid-recording. Only a check against the rendered
  page does.
- **Narration must describe mechanism, not one run's output.** Anything a clip
  asserts about a model's answer will eventually be false.
- **A negative security test that passes may be a broken test.** The first
  EICAR probe was malformed and looked like a hole.
- **Check which keys the project already has before offering vendors.** A list
  chosen by brand recognition managed to miss the two most-used keys.
- **The port matters.** An early "this cannot be verified locally" was wrong:
  the origin allowlist has 3000 and 3300, and the test server was on 3111.
- **The safeguard plan file is stale.** It still says
  `allow_origins=["*"]`; the whole `services/ml-api/security/` layer is built
  and running.

---

## 11. Standing constraints unchanged

- Ask before every `git commit`, in both repos.
- Never spawn a subagent without asking. None were used this session.
- Never `git add -A` / `git add .` — explicit paths, always `git -C <abs path>`.
- Only delete files created this session, named explicitly.
- No file over 400 lines, every extension.
- HF Space upload in the same response as any push touching
  `services/ml-api/**` — done for `6974290`.
- Never batch live calls to a paid API for self-verification without asking.
- Always push after committing; always report the short hash.
- No emojis as icons — inline SVG only.
