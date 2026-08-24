# Conversation — 2026-06-08 | Portfolio Chatbot + Palette Picker (Part 39)

**Date:** 2026-06-08
**Projects:** ml-portfolio (Vercel), ML-Unified
**Continued from:** Part 38

---

## Commits This Session

| Hash | Repo | Summary |
|---|---|---|
| `4018f9b` | ML-Unified | Fix ruff E401: split double import in vision conftest |
| `73c4e8a` | ml-portfolio | Add portfolio-wide context-aware chatbot (Claude Haiku) |
| `0d57784` | ml-portfolio | Switch chatbot backend from Claude Haiku to Gemini 1.5 Flash |
| `8eb4d51` | ml-portfolio | Add multi-provider chatbot: Gemini, Claude, Groq selector |
| `c80177e` | ml-portfolio | Fix Gemini API call: use systemInstruction field, add error logging |
| `00ea5c4` | ml-portfolio | Fix glass cards in light mode: solid white bg + visible border + shadow |
| `fcd94cf` | ml-portfolio | temp: surface Gemini error in reply for debugging |
| `cd8d1ad` | ml-portfolio | Fix pipeline cards: equal height via height:100% on card wrappers |
| `76d65e4` | ml-portfolio | Fix Gemini model: gemini-1.5-flash → gemini-2.5-flash; remove debug output |
| `2a2e96f` | ml-portfolio | Add theme palette picker: Cosmic, Sunset, Aurora, Ocean |
| `a850418` | ml-portfolio | Fix palette picker: close on click anywhere outside via mousedown listener |

---

## #2 — ruff + pytest (ML-Unified)

- **ruff:** 1 error — `import sys, os` on one line in `services/ml-vision/tests/conftest.py` (E401)
- **Fix:** Split into `import os` / `import sys` on separate lines
- **pytest:** 61/61 tests passing across `test_api.py` and `test_eda.py`

---

## #3 — Chatbot (Portfolio-wide, Context-aware)

### Architecture
- **`/api/chat/route.ts`** — Next.js API route, calls LLM provider
- **`src/components/Chatbot.tsx`** — Floating widget, bottom-right
- Added to `page.tsx`

### Features
- **IntersectionObserver** tracks which of 8 sections is most visible → updates system prompt context
- **Section-specific hint text** in the input placeholder
- **Multi-provider selector** — Gemini · Claude · Groq pills in chat header; switching clears history
- **Glass card UI** matching portfolio design (accent bar, blur, dark/light theme aware)
- **Typing indicator** — bouncing dots while waiting
- **Message bubbles** — user (gradient right), assistant (card left)
- **Send on Enter**, disabled during loading

### Providers
| Provider | Env var | Model | Status |
|---|---|---|---|
| Gemini | `GEMINI_API_KEY` | `gemini-2.5-flash` | ✅ Working |
| Claude | `ANTHROPIC_API_KEY` | `claude-haiku-4-5-20251001` | Needs credits |
| Groq | `GROQ_API_KEY` | `llama3-8b-8192` | Needs key (free) |

### Debugging journey
1. First attempt: used `gemini-1.5-flash` (hardcoded) → 404 from Google API
2. System prompt injected as fake user/model turn → Gemini rejected; switched to `systemInstruction` field
3. Added `console.error` logging for each provider
4. Temporary debug mode: surfaced real error in chatbot reply → revealed `gemini-1.5-flash is not found`
5. Fixed to `gemini-2.5-flash` → working

### System prompt structure
Section context changes per section:
- `hero` → overview
- `about` → IIIT-B PG Diploma, 3.7/4.0 GPA, end-to-end ML
- `skills` → full tech stack list
- `projects` → live ML apps
- `pipeline` → 8-stage pipeline description
- `contact` → LinkedIn/GitHub/DockerHub/form

---

## Light Mode Glass Card Fix

### Root cause
`--bg-glass: rgba(255,255,255,0.60)` and `--border: rgba(0,0,0,0.07)` in light mode made Pipeline and Skills cards invisible (white on white, 7% border).

### Fix
Added 3 new CSS tokens:
```css
--glass-bg:     rgba(17,24,39,0.60)   /* dark: translucent */
--glass-border: rgba(255,255,255,0.09) /* dark: subtle */
--glass-shadow: 0 4px 24px rgba(0,0,0,0.22) /* dark: deep */

/* light overrides */
--glass-bg:     #ffffff
--glass-border: rgba(0,0,0,0.10)
--glass-shadow: 0 2px 16px rgba(0,0,0,0.08), 0 1px 4px rgba(0,0,0,0.05)
```

Applied to `PipelineShowcase.tsx` and `Skills.tsx`.

---

## Pipeline Card Equal Height Fix

**Issue:** "Exploratory Analysis" and "Feature Engineering" had 2-line titles → those cards were taller than single-line title cards.

**Fix:** Added `height: "100%"` to both the `motion.div` wrapper and the inner card div in `StageCard`. CSS Grid's default `align-items: stretch` then equalises all cards to the tallest in the row.

---

## #4 — Theme Palette Picker

### CSS Variables Added
```css
:root {
  --accent-from: #818cf8;
  --accent-via:  #38bdf8;
  --accent-to:   #34d399;
  --accent:      #6366f1;
  --brand-gradient: linear-gradient(135deg, var(--accent-from), var(--accent-via), var(--accent-to));
}
html.palette-sunset  { --accent-from: #f97316; --accent-via: #f59e0b; --accent-to: #fbbf24; --accent: #f97316; }
html.palette-aurora  { --accent-from: #a855f7; --accent-via: #ec4899; --accent-to: #f43f5e; --accent: #a855f7; }
html.palette-ocean   { --accent-from: #0ea5e9; --accent-via: #06b6d4; --accent-to: #10b981; --accent: #0ea5e9; }
```

### Components Updated (brand gradient only; semantic per-section colors unchanged)
- `globals.css` — `gradient-text` + `form-input` focus border
- `Navbar.tsx` — logo bg, Resume button
- `Hero.tsx` — CTA button
- `Footer.tsx` — top bar, logo bg
- `About.tsx` — avatar bg
- `Contact.tsx` — Send button
- `Chatbot.tsx` — trigger button, header, message bubbles, spark icon, input focus

### PalettePicker Component
- Gradient circle button in Navbar (left of ThemeToggle)
- Click opens dropdown with 4 palette options
- Each option shows: gradient swatch, label, checkmark for active
- `applyPalette()` toggles `html` class, saves to `localStorage`
- Init script in `layout.tsx` restores palette on load (prevents flash)
- **Click-away fix:** `document.mousedown` listener on `containerRef` closes dropdown when clicking anywhere outside — replaced unreliable fixed overlay div

### Palettes
| Name | Colors |
|---|---|
| Cosmic (default) | Indigo #818cf8 → Sky #38bdf8 → Emerald #34d399 |
| Sunset | Orange #f97316 → Amber #f59e0b → Yellow #fbbf24 |
| Aurora | Purple #a855f7 → Pink #ec4899 → Rose #f43f5e |
| Ocean | Sky #0ea5e9 → Cyan #06b6d4 → Teal #10b981 |

---

## Pending Task List (updated)

| # | Item | Status |
|---|---|---|
| 1 | Mobile responsiveness | ✅ Done (Part 38) |
| 2 | ruff + pytest | ✅ Done this session |
| 3 | Chatbot (portfolio-wide, context-aware) | ✅ Done this session |
| 4 | Theme palette picker | ✅ Done this session |
| 5 | Proxy page (`/app/[id]`) | **Deferred** — low ROI; cold start better solved by Render paid plan |
| 6 | SHAP Interpreter card | Pending |
| 7 | Build Pipeline mode (ML Unified) | Pending |
| 8 | Prediction confidence bar chart | Pending |
| 9 | SHAP in ML Unified | Pending |
| 10 | Training history / comparison | Pending |
| 11 | Cleaned CSV download | Pending |
| 12 | EDA microservice extraction | Pending |
| 13 | 35 EDA unit tests | Pending |
| 14 | Side-by-side vision results | Pending |
| 15 | Batch predict for vision | Pending |
| 16 | Vision ambient themes | Pending |
| 17 | Mobile bottom tab bar | Pending |
| 18 | Data drift detection | Pending |
| 19 | MLflow experiment tracking | Pending |
| 20 | Playwright E2E tests | Pending |

---

## Additional Fixes This Session

### Palette Picker — Click-away Bug
- **Issue:** Dropdown only closed when clicking on the navbar; clicking elsewhere on the page did nothing
- **Root cause:** Fixed-position overlay div was unreliable due to z-index stacking context conflicts
- **Fix:** `useRef` + `document.addEventListener("mousedown", handler)` in `useEffect`; handler checks `containerRef.current.contains(e.target)` to detect outside clicks; listener removed on cleanup

### ML Unified / Palette Picker Scope Clarification
- Palette picker only controls the **ml-portfolio** frontend (Vercel)
- ML Unified is a separate React app on Render — it cannot be affected by the portfolio's CSS variables
- Per-project card accent colors in ProjectsSection are semantic (fixed per project) and intentionally do not change with palette

---

## Standing Rules (unchanged)

- Conversation logs: `ML-Iris/Conversations/Conversation_YYYY-MM-DD_Topic_PartXX.md`
- Never expose `ramleo84@gmail.com` publicly on the website
- `vision_cache/` and `.mcp.json` must never be committed
- Portfolio project cards stay as grid — do NOT change to two-panel layout
- Vercel → ml-portfolio; Render → ml-unified backend
- `--bg-glass` for cards, `--bg-section` for section backgrounds
- Always run `ruff check` + `pytest` before pushing ML-Unified
- User-facing errors: plain English only
- Always run `ruff check` + `pytest` before pushing ML-Unified (ruff at `.venv/bin/ruff`)
