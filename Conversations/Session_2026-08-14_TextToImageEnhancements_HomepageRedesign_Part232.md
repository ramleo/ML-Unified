# Session 2026-08-14/15 — Text-to-Image enhancements, chat bugs, homepage-style redesign

Continuation of Part 231 (same day). Covers: consolidating a scattered pending-items list into one
memory file, building three free enhancements onto the Text-to-Image Generator, three real bugs
found (two by the user, one by me) in the shared `ToolsAIChat` component, then a from-scratch
visual redesign of the Text-to-Image page to match the homepage's actual card design language,
compared directly against Document Intelligence to make the case for a wider rollout.

## Part 1 — Pending-list audit and consolidation

User asked "what is pending" repeatedly across several angles (MMRAG backlog, then explicitly "not
MMRAG... items needing creation of separate tools altogether"). Traced this to Part 225's CV
brainstorm, which split ideas into "fold into Multimodal RAG" (Object Remover — already built) vs.
"needs its own standalone tool": Text-to-Image Generator, Social Reels Creator,
Gesture-Controlled Desktop, Medical Scan Analyzer, Sign Language Translator.

User asked to scope one out. Used `EnterPlanMode`: two `Explore` agents researched backend
(Gemini image-gen call patterns, `_image_gen_budget.py`'s shared-pool contract, `app.py`
registration) and frontend (SHAP/reconciliation page→Runner→hook split, `ConstellationBackground`
convention, `ML_UNIFIED_API` config, 429-error `cleanErr()` pattern) in parallel; a `Plan` agent
then drafted the concrete implementation. User picked **Text-to-Image Generator** over Medical Scan
Analyzer specifically because they have no medical scans to self-verify output against — this
project's standing norm requires real, self-checkable verification.

Later, user asked for a single consolidated pending-items table spanning every open thread (T2I
enhancements, CV standalone-tool backlog, MMRAG backlog, older AI-fill plan, real-world-use-cases
shortlist). Built and saved as a new standing memory,
`project_pending_master_list.md` — explicitly told to check this file FIRST for "what's pending"
going forward instead of re-deriving from scattered logs each time.

## Part 2 — Text-to-Image Generator: base build (recap from Part 231, for continuity)

Already covered in Part 231's log: `POST /rag/mm-text-to-image` (no input image, unlike
sharpen/AI-fill), its own `text2img` daily budbudget pool (`GEMINI_TEXT2IMG_DAILY_CAP`, default
15/day) separate from the shared 40/day sharpen+AI-fill pool, and a real bug caught by the one live
Phase-B verification call: Gemini's pure-generation response comes back as `image/jpeg`, not PNG —
fixed by returning the actual `mime_type` instead of assuming. User live-tested the base tool
themselves ("a real cat on a tree" → correct photo) before this session's work began.

## Part 3 — Web research + style/aspect-ratio/negative-prompt build

User asked for web research on what features to add to a text-to-image tool. Two rounds of
`WebSearch` covered: aspect ratio/style presets/negative prompts/variations (industry-standard
features across Midjourney/DALL-E/Ideogram/Adobe Firefly), then a second round on prompt
enhancers, seed reproducibility, upscaling, image-to-image, galleries, moderation, and credit
systems. Synthesized into a curated recommendation (not a raw dump) split into: free/cheap
(prompt-only), synergies with existing tools (reuse `mm-deblur` as an "Enhance" button, reuse
`mm-ai-fill` as an "edit this" button), billed/needs-gating (multiple variations, seed), and
explicitly-not-worth-it (credits/billing system, community gallery, custom moderation layer — this
is a portfolio demo, not a commercial SaaS).

User approved building **style presets + negative prompt + aspect ratio** — all pure prompt-text
engineering, explicitly the free tier, since none of them change the Gemini request's shape (still
one text-only call), so no new live-API verification was needed.

**Backend** (`mm_text_to_image.py`, 136 lines after):
- `TextToImageRequest` gained `style`, `aspect_ratio`, `negative_prompt` (all optional).
- Two fixed, server-validated dicts — `_STYLES` (7 presets: photorealistic, watercolor, anime,
  cyberpunk, oil-painting, 3d-render, sketch) and `_ASPECT_RATIOS` (square/landscape/portrait) —
  map a client-supplied KEY to a known-good phrase; an unknown key is rejected with 400, so a client
  can never inject arbitrary text into that part of the assembled prompt.
- `negative_prompt` is free text (capped 500 chars), appended as "Do not include: {text}."
- Final prompt is assembled server-side (`full_prompt = prompt + style phrase + aspect phrase +
  negative clause`) before the single Gemini call — request JSON shape unchanged from the
  already-verified one.

**Tests**: 5 new cases added to `test_mm_text_to_image.py` (15 total, all passing) — unknown
style/aspect_ratio rejected, over-length negative prompt rejected, and two tests that inspect the
actual `httpx.Client.post` call args to prove the assembled prompt contains the right phrases (and,
separately, that omitting all three leaves the prompt byte-identical to the raw input).

**Frontend**: `useTextToImageRunner.ts` exports `STYLE_OPTIONS`/`ASPECT_RATIO_OPTIONS` (keys
mirror the backend's dicts exactly — single source of truth, not duplicated prose) and new
`style`/`aspectRatio`/`negativePrompt` state, sent alongside `prompt` on generate. New `ChipRow`
component in `TextToImageRunner.tsx` renders both option sets as toggleable pill chips; a new
"Avoid (optional)" text input with its own char-limit guard.

Deployed: ML-Unified `fcde65c`, ml-portfolio `7a56f7b`. HF Space `/openapi.json` confirmed the new
request schema fields live; Vercel deploy confirmed via raw HTML text markers, then a full
Playwright pass (chip toggle state, form renders) — no live Generate click made by me (billed call,
left for the user).

## Part 4 — Real bug #1: chat suggestions fell back to a wrong generic default

User (screenshot) asked why the floating AI-chat's suggestion chips showed feature-engineering
questions ("Which columns need normalisation?", "What does log1p do to skewed data?", "When should
I use frequency encoding?") on an image-generation tool, then pointedly asked "do you do research
or analysis before doing something?"

Root cause, found immediately via `grep`: `ChatMessageList.tsx:46-50` has a hardcoded default
`SUGGESTIONS` array (written for the preprocessing/FE tools) used whenever a page's `ToolsAIChat`
context doesn't pass its own `suggestions`. The Text-to-Image page's original `ToolsAIChat` call
only set `tool`/`summary` — I had actually read the reconciliation page's pattern (which does pass
`suggestions: RECONCILIATION_SUGGESTIONS`) during the original build but didn't carry it over.
Acknowledged the miss directly, fixed by adding a 3-item tool-specific `suggestions` array to
`page.tsx`. Commit `a98a8d1`. Verified live via Playwright (opened chat, confirmed real suggestions
render).

## Part 5 — Real bug #2: chat had no real grounding to answer those questions from

User then asked, reasonably: even with the right suggestion buttons, would the chat actually be
able to ANSWER "how do style presets change the image" correctly? Traced `useRagChat.ts`'s
`buildToolContext()`: without a `guide` prop, the LLM's ENTIRE context is just `Tool: <name>\n
<summary>` — and the page's one-line summary never mentioned style/aspect-ratio/negative-prompt at
all, so the assistant had nothing to ground an answer in.

Fixed by building `TOOL_SUMMARY` directly from `STYLE_OPTIONS`/`ASPECT_RATIO_OPTIONS` (same import
as the UI itself uses) so the grounding text enumerates the real options and their effects and can
never drift out of sync with what's actually on the page. Commit `b745a7b`. Verified live via
Playwright — opened the chat, confirmed the tool-specific suggestions render (did not click one to
avoid an unnecessary LLM call, per the user's own correction below).

**Note on scope discipline mid-verification**: while about to click a suggestion button to verify
the chat's actual ANSWER quality, the user interrupted the tool call and redirected to an unrelated
visual issue instead (see Part 6) — the click was never completed, and no further attempt was made
after the redirect; the user's real question turned out to be about something else entirely.

## Part 6 — Real bug #3: chat accent was the AI provider's color, not the page's theme (site-wide)

User asked why the chat widget was blue on a pink-themed page. Traced to `useRagChat.ts:148-149`
(pre-fix): `accentColor = providerConfig.color` — the floating chat's entire color scheme was
always the SELECTED LLM PROVIDER's brand color (blue for Gemini, the default), completely
independent of which tool page hosted it. Confirmed via `toolsAiProviders.ts` this was global,
affecting all 14 tool pages using `ToolsAIChat`, not something specific to the new page.

Asked the user how to scope the fix (site-wide vs. this-page-only vs. leave-as-is) — user chose
**site-wide**. Implementation: added an optional `accent?: string` field to `ToolChatContext`
(`useRagChat.ts`), changed the computation to `accentColor = context.accent ?? providerConfig.color`
(fully backward-compatible — no accent passed still falls back to the old provider-color behavior),
then edited all 14 `page.tsx` files under `src/app/tools/` to pass their own `ACCENT` constant (one
page, `drift/page.tsx`, had no named constant — used its existing badge color `#fb923c` literally).
Verified with a grep sweep confirming every `ToolsAIChat context={{` call site now includes
`accent:`. The provider picker inside chat settings still shows each provider's own brand color in
its OWN list (unaffected — that's local to `ToolsAIChatSettings.tsx`, doesn't read the shared
`accentColor`).

Commit `f617725` (15 files: `useRagChat.ts` + all 14 tool pages). Verified live via a real
screenshot (not just DOM snapshot, since color isn't visible in an accessibility tree) — confirmed
the chat panel's border, header, suggestion chips, and floating toggle button are all pink on the
Text-to-Image page now.

## Part 7 — User's own live verification of style/aspect-ratio/negative-prompt

User generated a real image themselves via the deployed UI: prompt "a beautiful girl walking
towards me", style = Cyberpunk, aspect ratio = Landscape. Result: a correctly on-theme
neon-lit cyberpunk cityscape image in the right aspect ratio, matching the style preset's intent —
confirming Part 3's feature works end-to-end for real, not just in mocked tests.

## Part 8 — Homepage UI analysis and Text-to-Image page redesign

User asked to analyze the homepage's UI design and apply it to the Text-to-Image tool page first,
show the result, and only THEN consider rolling it out to every other tool page — explicit
instruction not to touch other pages yet.

**Investigation hit a real Playwright/automation quirk**: viewport screenshots taken immediately
after a JS-driven (`window.scrollTo`/`scrollIntoView`) scroll consistently came back solid navy —
blank — even though `getBoundingClientRect()`/`getComputedStyle()` confirmed the target section was
genuinely in-viewport with opacity 1. A `fullPage` screenshot (Playwright's own internal
scroll-and-stitch) rendered SOME sections correctly (hero, "Live ML Apps" project cards, footer) but
left the `#capabilities` card grid blank too — most likely a framer-motion scroll-triggered
animation whose repaint doesn't complete before the automated capture, not a real user-facing bug.
Worked around it by using the fullPage capture's "Live ML Apps" section (which DID render) as the
design reference instead of fighting the capabilities grid further — cropped/zoomed that region
with PIL for a clean, high-resolution look at the actual card component.

**Read the source directly** (`ProjectCard.tsx`, `globals.css`) rather than eyeballing colors from
a screenshot, to get exact values:
- Theme-aware CSS variables (light AND dark both defined): `--bg-glass`
  (`rgba(17,24,39,0.60)` dark / `rgba(255,255,255,0.60)` light), `--border`, `--border2`, `--text`,
  `--text2`, `--text3` — the Text-to-Image page previously used hardcoded dark-only Tailwind colors
  (`text-white`, `text-gray-400`) that don't respect the site's light-mode toggle at all.
- Card pattern: `var(--bg-glass)` + `backdrop-filter: blur(14px)` + `1px solid var(--border)` +
  `16px` radius + a colored **3px top accent bar** in the card's own accent color — this top-bar
  signature was completely absent from the Text-to-Image page's original design.
- Badge-pill formula: `accent+"22"` background, `accent` text color, `accent+"44"` border.
- "Launch App" button: fully rounded (`9999px`), solid accent fill, white text, arrow icon, hover
  lift (`translateY(-1px)` + opacity 0.88).
- A global `.form-input` class already existed for text inputs (`var(--bg-card)` background,
  `var(--border2)` border, `10px` radius) — reused instead of inventing new input styling.
- Headings site-wide use the "Geist" font at weight 800 (global, inherited automatically — no
  action needed here).

**Rebuilt** `TextToImageRunner.tsx` and `page.tsx` around these exact tokens: new local `Card`
component replicating `ProjectCard`'s glass+top-bar chrome, `ChipRow` restyled to the real
badge-pill formula, Generate button rebuilt to match "Launch App" pixel-for-pixel (pill shape,
arrow icon, hover lift), and every hardcoded text color swapped for `var(--text)/2/3` so the page
now correctly follows the site's light/dark theme toggle like every other page already does.

Deployed as `9340952`. Verified live via a real screenshot (cropped/zoomed with PIL for a close
look) — pink 3px top bar, glass card, pill badges, pill Generate button all rendering correctly.

## Part 9 — Comparison against Document Intelligence

User asked directly which page looks better: the redesigned Text-to-Image vs. the still-unconverted
Document Intelligence page. Screenshotted both and gave an honest, specific comparison rather than
a vague opinion:

Document Intelligence (unconverted, represents every other current tool page's look): flat cards
with no colored top-bar signature, a plain bordered box for the active sidebar item (not a pill),
small flat teal format-tag chips (no pill/border treatment), and a plain rectangular outlined
"User Guide" button — no fill, no pill shape, no hover lift. Reads as functional but visually flat.

Text-to-Image (redesigned): has all the things Document Intelligence lacks — the colored top
accent bar, real rounded-full badge-pill chips with tinted background+border, and a solid-filled
pill Generate button with hover lift and an arrow icon, matching the homepage's actual "Launch App"
buttons closely.

Verdict given: the redesigned page looks better, and Document Intelligence is a good example of
why — it's one of the flatter existing pages, so it would show the clearest visible improvement
from the same treatment.

## Part 10 — Time estimate for full rollout

User asked how long applying the same treatment to the remaining 13 tool pages would take. Gave a
tiered, honest estimate rather than one number: a "quick pass" (page-shell/control-card/button
level, matching exactly what was done for Text-to-Image) estimated at ~2-3 hours of working time
across 3-4 batches (batched deploys, not one deploy per page, per the project's standing "batch
deploys, verify once" rule); a "deep pass" (also restyling every nested card/table/chart inside the
heavier tools — Document Intelligence's sidebar+dropzone+bbox-overlay+results-table, Multimodal
RAG's chat+citations+thumbnails, AutoML/Optuna/Ensemble/SHAP's wizards+leaderboards+charts,
Feature Engineering/Selection/Preprocessing's data tables) would be substantially more, roughly
another 3-4 hours. Recommended quick-pass-everywhere first, then a per-page judgment call on
whether nested components need the same treatment. Awaiting the user's decision on which to do —
this session's log was requested to be saved before that decision was made.

## Commit hashes (this session, chronological)

**ML-Unified (backend):**
1. `fcde65c` — style presets, aspect ratio, negative prompt for text-to-image

**ml-portfolio (frontend):**
1. `7a56f7b` — style presets, aspect ratio, negative prompt UI
2. `a98a8d1` — fix: relevant AI-chat suggestions on Text-to-Image page (bug #1)
3. `b745a7b` — fix: ground AI chat with real feature descriptions (bug #2)
4. `f617725` — fix: chat widget matches each tool page's own accent, not provider color (bug #3,
   site-wide, 15 files)
5. `9340952` — style: redesign Text-to-Image page to match homepage's card design

## Memory changes this session

- New `project_pending_master_list.md` — the consolidated pending-items table; told to check this
  FIRST going forward for any "what's pending" question.
- `project_text_to_image_tool.md` updated three times: enhancements shipped/user-verified, the
  ToolsAIChat-suggestions lesson recorded ("always pass tool-specific `suggestions`"), and the
  site-wide chat-accent fix recorded.

## Pending / not yet resolved

- Whether to roll the homepage-style redesign out to the other 13 tool pages — quick-pass vs.
  deep-pass scope decision still awaiting the user, per Part 10.
- The multiple-variations-per-prompt, seed-reproducibility, prompt-enhancer, generation-history,
  and "Enhance"/"edit this" (reusing mm-deblur/mm-ai-fill) enhancement ideas from Part 3's research
  remain unbuilt — only style/aspect-ratio/negative-prompt were approved and built this session.
- The remaining CV-backlog standalone tools (Social Reels Creator, Gesture-Controlled Desktop, Sign
  Language Translator) are still untouched.
