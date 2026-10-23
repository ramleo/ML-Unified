# Part 330 — Homepage chat: grounded-RAG rework (2026-10-23)

Continues Part 329. The homepage "AIRaML Assistant" was failing ("Something went
wrong") and, when it did answer, it was **ungrounded** — it only had a few hardcoded
section blurbs, so it gave wrong answers about the tools (claimed CSV upload isn't
supported when EDA/Preprocessing/Feature Engineering all take CSV). This reworked it
onto the site's grounded RAG. All frontend (ml-portfolio / Vercel). Every claim here
was verified against the live production endpoint.

## Proper investigation (the user pushed back on guesses — rightly)
Instead of theorizing, pulled the real evidence:
- **`llm_calls` (prod Supabase, table uses `ts`)** for `tool=chat, status=error`:
  `cohere → 429 "Trial key limited to 1000 API calls/month"` (trial cap) and
  `groq → 401`.
- **Direct Groq calls with the active key** + Groq's **`/models`**:
  - `qwen/qwen3.6-27b` → **404 `model_not_found`** — Groq RETIRED it (it still exists
    on HF/Ollama/OpenRouter; Groq just doesn't host it).
  - `openai/gpt-oss-120b` → 200 (reasoning-heavy), `qwen/qwen3.8-27b` → 200 (clean).
  - `/models`: gpt-oss-120b, gpt-oss-20b, qwen3.8-27b, allam-2-7b … no qwen3.6, no
    llama text models.
- **Lesson:** a **404 (model) ≠ 401 (key)** — don't conflate or say "expired/broken"
  from a bare status. The Groq key was ACTIVE (user was right); the chat's model was
  dead. Verify from `llm_calls` + `/models` + a direct provider call.

## Root cause
`/api/chat` was a bare, ungrounded LLM call: hardcoded section blurbs, Vercel's own
provider keys, calling the retired `qwen3.6-27b` for its Groq option. So it hallucinated
about tools AND died when a key failed (Cohere trial cap; Groq 401/retired model).

## The fix (ml-portfolio)
- **Grounded** (`9411d0b`): `/api/chat` now **proxies the Space's RAG** (`/rag/query`) —
  the same handbook KB the tool chats + site search use, covering **every tool AND
  platform AND site feature**. It accumulates the SSE `token` stream into one reply. The
  Space uses its own working keys and has a provider fallback cascade, so a single
  provider being down no longer breaks chat. Groq pins **`qwen/qwen3.8-27b`** (current,
  clean). Replies say "AIRaML", not the owner's full name (fixes the name complaint).
- **Copyable** (`9411d0b`): `ChatMessages.tsx` (new) renders the transcript with
  selectable text + a per-reply **Copy** button; keeps `Chatbot.tsx` under 400 lines.
- **Website-only** (`b17d979`): the RAG web-falls-back on low KB confidence, so off-topic
  ("capital of France") was answered from the open web. Now `/api/chat` tracks the
  answer's sources and, if none is a real KB file (all `web:` → off-topic), returns a
  website-only decline. **Scoped to the homepage chat** — the shared Space RAG (tool
  chats, ML-theory Q&A) is untouched.

## Verified on production
- "what does Testwright do?" (groq/qwen3.8) → grounded answer.
- "How can I upload a CSV…?" → correct ("go to the EDA tool at /tools/exploratory-data-
  analysis, Upload CSV …") — the exact question that was wrong before.
- "What platforms…?" → lists all 5.
- "capital of France" → declines (website-only).
Both commits CI-green.

## Lessons
- **Investigate with evidence, not status codes.** `llm_calls` (error_message/http_status)
  + a direct provider call + the provider's `/models` beat guessing. 404≠401.
- **Ground a "site chatbot" in the site's own content.** A bare LLM with hardcoded
  blurbs will confidently hallucinate about features it doesn't know.
- **Scope behavior at the edge, not in shared infra.** Website-only enforcement lives in
  `/api/chat` (source check), so the shared RAG that other chats rely on didn't change.
- **The sources are the ground-truth signal** for "did this come from the site?" — a
  `web:` source means the open-web fallback fired.

## Left open (user's call)
- **Cohere** trial monthly cap — user said leave it (Groq/Gemini cover it).

Standing requirements saved to memory ([[project_homepage_chat_grounded]]): the homepage
chat must be grounded (answer any website question), copyable, and must not plaster the
owner's full name.

---

## Follow-up round (same day) — chat usability + upload affordance

After the grounded rework, the user hit three more chat issues plus a site-wide upload one.

### Chat fixes (`4ae9d1e`, ml-portfolio, frontend-only)
1. **User messages weren't copyable** — the Copy button only rendered on assistant
   replies. Now renders on both bubbles (`ChatMessages.tsx`).
2. **Paths were plain text, not links** — a reply saying `/tools/preprocessing` was dead
   text. Added a linkifier in `ChatMessages.tsx` that turns internal paths
   (`/tools/…`, `/platforms/…`, `[label](/path)`) into real `<a>` links, so the user
   clicks instead of retyping (case/spelling no longer matters). External URLs stay plain.
3. **Follow-ups jumped to the wrong tool** — "give me the link to go" returned Meeting
   Intelligence (and later invented `/data-preprocessing`). **Root cause:** `/api/chat`
   sent only the LAST message, and even passing `history` fixes *generation* but NOT
   *retrieval* — a contextless "give me the link" embeds to the wrong KB chunks, so the
   model invents a path. **Fix:** `/api/chat` now (a) passes bounded `history` to the RAG
   (the Space's `QueryRequest` already has `history: list[dict]`, no backend change), and
   (b) resolves a short/referential follow-up into a standalone retrieval query by
   prefixing the prior question. **Proven live:** the exact follow-up now retrieves
   `15-data-preprocessing.md` and returns the correct `/tools/preprocessing`.

### Chat links open in a new tab (`da772d6`)
Clicking an in-chat link navigated away and the chat (not persisted) was lost. Links now
carry `target="_blank" rel="noopener noreferrer"`.

### Upload-affordance audit + fix (`da772d6`, ml-portfolio, frontend-only)
User: the EDA upload was a **bare native `<input type="file">`** ("Choose file / No file
chosen") — no visual cue where to click. Audited **all 44 upload controls** across the
60 tools + shared platform components (AutoML step, pipeline bars, RAG ingest, etc.):
- **Only 2 were bare:** **Exploratory Data Analysis** and **Multimodal RAG**'s add-image
  popover. The other 42 already hid the native input behind a styled drop-zone/button.
- **EDA** → dashed drop-zone (upload icon, "Drop your CSV here / or click to browse",
  drag-and-drop, 10 MB hint) matching its twin **Preprocessing** tool. Verified live with
  a production screenshot.
- **Multimodal RAG** add-image → a styled "Choose an image" button.
- Audit method gotcha: a naïve regex for the hide-style flagged 4 false positives because
  `=>` arrows in `onChange` truncated the match at the `>`. Re-checked each by hand —
  MeetingRunner/TextToImage/FileUploadSection were all already hidden (`className="hidden"`
  / `display:none`).

### Lessons (added)
- **History fixes generation, not retrieval.** A referential follow-up must be resolved
  into a standalone query (prefix the prior turn) or the RAG retrieves the wrong chunks
  and hallucinates a path. The KB had the right path all along (`Find it at` row).
- **Audit the whole class, verify each flag.** Regex heuristics over JSX are lossy
  (`=>`, multiline tags) — confirm every hit/miss before reporting a count.
- **A file input must have a visible affordance** — hide the native input, put a
  drop-zone or labeled button in front; the site already did this for 42/44, EDA was the
  outlier the user actually used.
