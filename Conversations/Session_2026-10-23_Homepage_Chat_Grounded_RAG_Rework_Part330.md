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
