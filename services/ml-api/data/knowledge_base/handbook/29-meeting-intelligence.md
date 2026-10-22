Chapter 23Meeting Intelligence


> Upload a meeting or call recording — audio or video — and get structured notes back: a short summary, the decisions that were made, the action items with owners and due dates when stated, an agenda of topics with timestamps, and how long each speaker talked, plus the full speaker-labelled transcript. The audio is transcribed with Whisper, speakers are diarized, and one language-model pass extracts the notes — instructed to only include a decision or action item that was actually said, never to invent one. Best on clips up to about ten minutes; nothing is stored after the response.

## At a glance

| | |
|---|---|
| **Also called** | Notes From a Recording |
| **Model or method** | Whisper · Gemini diarization · Cohere/Mistral |
| **What you give it** | One meeting/call recording (audio or video) |
| **+ Diarize + LLM** | ASR |
| **Where it runs** | On the server |
| **Find it at** | `/tools/meeting-intelligence` |

### What this tool does
Upload a recording of a meeting or call and get back structured notes: a short
**summary**, the **decisions** that were made, the **action items** (with an
owner and due date when they were stated), an **agenda** of topics with
timestamps, and **who spoke for how long**. You can also read the full
speaker-labelled transcript.

### How it works
1. **Transcribe** — the audio is transcribed with Whisper (fast, handles any
   length by chunking).
2. **Label speakers** — each line is tagged "Speaker 1", "Speaker 2", … by an
   audio-diarization pass, so the notes and transcript show who said what.
3. **Extract** — one language-model pass over the speaker-labelled transcript
   produces the summary, decisions and action items. It is explicitly instructed
   to only include a decision or action item that was **actually stated**, and
   never to invent an owner or due date that wasn't said.
4. **Agenda & talk-time** — topic markers come from the timestamped transcript;
   talk-time is measured directly from each speaker's segments.

Video files work too — only the audio track is used.

### How to use it
1. Click **Choose recording** and pick an audio or video file.
2. Click **Analyze meeting**. It runs on the server and can take up to a couple
   of minutes for a longer clip.
3. Read the summary, decisions, action items, agenda and talk-time; expand the
   transcript to check anything against the source. The recording plays back in
   the tool — **click any timestamp (in the agenda or the transcript) to jump the
   player to that moment**.
4. **Ask about the meeting** — use the question box under the results to ask
   anything about what was said ("What did each person commit to?"). Answers come
   strictly from this meeting's transcript; if something wasn't said, it says so.

### What this is (and isn't)
- **Lean tool — best on clips up to ~10 minutes.** A very long recording may
  time out; trim it or split it first.
- **The notes are a model's reading of the transcript.** It's told not to
  invent, but always check important decisions and action items against the
  transcript, which is shown for exactly that reason.
- **Speaker labels are generic** ("Speaker 1", "Speaker 2") — it identifies
  distinct voices, not who they are by name.
- **Nothing is stored.** The recording is transcribed in the request and not
  kept after the response.
