# Conversation — 2026-06-07 | Portfolio + ML Unified Polish (Part 37)

**Date:** 2026-06-07
**Projects:** ML-Unified (Render), ml-portfolio (Vercel)
**Continued from:** Part 36

---

## Commits This Session

| Hash | Repo | Summary |
|---|---|---|
| `1bfc706` | ml-unified | Fix ml-vision Python version: add .python-version to force 3.11 |
| `c56a450` | ml-unified | Dockerize ml-api and ml-vision services |
| `c8595b7` | ml-unified | Fix EDA Explorer footer link to open EDA mode, not ML Unified |
| `f06ac08` | ml-unified | Add neural network favicon to EDA Explorer HTML export |
| `6180220` | ml-unified | Light theme: boost ML Unified visibility + theme-aware HTML export |
| `00c5ad9` | ml-portfolio | Hero mouse parallax, pipeline SVG icons, light theme fixes |

---

## Render Port-Scan Timeout Fix

**Symptom:** `==> Port scan timeout reached, no open ports detected` on every ml-vision deploy.

**Root cause:** The failing service was **ml-vision**, not ml-api (confirmed by `onnxruntime` and `Pillow` in the pip log — ml-api uses sklearn/pandas). ml-vision had no `.python-version` file tracked in git, so Render defaulted to Python 3.14.3. The `PYTHON_VERSION` env var in render.yaml is processed after the Python installer runs and was being silently ignored.

**Fix `1bfc706`:**
- Added `services/ml-vision/.python-version` with `3.11.0`
- Added `healthCheckPath: /health` to ml-vision in render.yaml

---

## Dockerization (`c56a450`)

**Motivation:** Python version detection on Render is fragile — bumping their default breaks deployments. Docker pins the interpreter in `FROM python:3.11-slim`, making Render's defaults irrelevant.

### Files Created

| File | Key detail |
|---|---|
| `services/ml-api/Dockerfile` | `python:3.11-slim`, installs `libgomp1` (required by LightGBM/XGBoost for OpenMP), copies models/ + schemas/ |
| `services/ml-api/.dockerignore` | Excludes `__pycache__`, tests, `.python-version` |
| `services/ml-vision/Dockerfile` | `python:3.11-slim`, no system deps needed |
| `services/ml-vision/.dockerignore` | Excludes `vision_cache/` (ONNX models download at runtime) |

**render.yaml changes:** `runtime: python` → `env: docker` for both services. `buildCommand` and `startCommand` removed (handled by Dockerfile `CMD`).

**ml-vision requirements.txt:** Pinned all 4 previously-unpinned packages (`numpy==1.26.4`, `Pillow==10.4.0`, `onnxruntime==1.20.1`, `python-multipart==0.0.32`).

```dockerfile
# CMD pattern for $PORT (Render sets this at runtime)
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

---

## EDA Explorer HTML Export Fixes

### Footer Link (`c8595b7`)
The exported HTML footer linked to `ml-unified.onrender.com` which opens the default ML Unified mode. Fixed to `ml-unified.onrender.com/?mode=eda` — the app already supported `?mode=` via `URLSearchParams`.

### Favicon in Export (`f06ac08`)
Downloaded HTML had no favicon (generic browser icon in tab). Added the same base64 data URI `<link rel="icon">` used by the main app into the export HTML's `<head>`. Works offline — no external request.

---

## ML Unified Light Theme + Theme-Aware Export (`6180220`)

### Light Theme Visibility Boost

| Element | Before | After |
|---|---|---|
| Particle line opacity | 0.18 | 0.28 |
| Particle dot opacity | 0.40 | 0.55 |
| Blob 1 opacity | 0.07 | 0.14 |
| Blob 2 opacity | 0.06 | 0.11 |

Same boost ratio applied to the portfolio light theme in the same session.

### Theme-Aware HTML Export

`_exportEDAReport()` now reads `data-theme` at export time and passes `isLight` flag to `_buildExportHTML()`. The function generates different CSS blocks based on the flag:

**Light export CSS:**
- Body: `#f0f4f8` bg, `#0f172a` text
- Header: white→indigo→mint gradient, stronger blob glows (0.14/0.12)
- Cards: `#ffffff` with `rgba(0,0,0,0.08)` border, soft shadow
- H1 gradient: dark-to-indigo (readable on light bg, not washed out)
- Dividers/borders: flip from `rgba(255,255,255,…)` to `rgba(0,0,0,…)`
- Footer link: `#4f46e5` instead of sky blue

Dark export is unchanged.

---

## Portfolio — Hero Parallax + Pipeline SVG Icons + Light Theme (`00c5ad9`)

### Files Changed

| File | Change |
|---|---|
| `src/hooks/useIsDark.ts` | New shared hook — MutationObserver on `html.light` class |
| `src/components/NeuralNetwork3D.tsx` | Mouse parallax + light theme material colors |
| `src/components/PipelineShowcase.tsx` | Tinted tile SVG icons replacing emojis |
| `src/components/Hero.tsx` | Blob opacities boosted in light mode |

### Hero Mouse Parallax

`NeuralNetwork3D` now reads `state.pointer.x/y` (Three.js normalized -1..1) every frame. Base auto-rotation accumulates in a `useRef`, mouse adds an offset on top. Lerp at `0.05` gives smooth weighted follow — fast enough to feel responsive, physical enough to feel real.

```ts
autoRot.current.y += delta * 0.09;          // continuous base rotation
const targetY = autoRot.current.y + pointer.x * 0.8;  // mouse offset
currRot.current.y += (targetY - currRot.current.y) * 0.05; // lerp
```

### NeuralNetwork3D Light Theme

| Property | Dark | Light |
|---|---|---|
| Line color | `#6366f1` | `#4f46e5` (darker for contrast) |
| Line opacity | 0.18 | 0.32 |
| Point color | `#818cf8` | `#6366f1` |
| Point size | 0.035 | 0.044 |
| Emissive intensity | 1.2 | 0.4 |

### Pipeline SVG Icons — Tinted Tile

Each emoji replaced with a 52×52 rounded tile (`borderRadius: 13`, `background: accent + "18"`, `border: accent + "2e"`). Icon is stroke + one filled shape at 15% opacity for depth.

| Stage | Icon Design |
|---|---|
| Data Ingestion | Database cylinder (ellipse top + two path arcs) |
| Exploratory Analysis | Magnifier with 3 scatter dots inside |
| Feature Engineering | 3 horizontal track lines with offset handles |
| Model Training | Stacked layers (Lucide `layers` style) |
| Evaluation | Ascending bar chart (3 rects + baseline) |
| Deployment | Cloud with upward arrow |
| Monitoring | Heartbeat/activity polyline |

Same `IconTile` at 44px appears in the expanded detail panel header.

### Hero Light Theme Blobs

`useIsDark()` hook drives blob opacity at render time:
- Blob 1: `0.13` → `0.22` in light
- Blob 2: `0.09` → `0.18` in light
- Blob 3: `0.07` → `0.14` in light

---

## Architecture Notes

### Why Docker over `.python-version`
`.python-version` file is checked by Render's build system but can be silently ignored when the platform updates its default Python. `FROM python:3.11-slim` in a Dockerfile is absolute — Render just runs the container without any version detection logic.

### useIsDark Pattern
Shared hook used by both `Hero.tsx` and `NeuralNetwork3D.tsx`. MutationObserver watches `attributeFilter: ["class"]` on `document.documentElement`. Returns `isDark: boolean`. Can be reused in any future component that needs theme-aware behavior.

---

## Pending Tasks

- **Render port-scan timeout** — resolved for ml-vision (Docker). ml-api was already working.
- **RESEND_API_KEY + NEWSAPI_KEY** — user needs to add to Vercel dashboard
- **PCA 3D scatter** (ML-Iris) — in_progress
- **Export HTML visual overhaul** (ML-Iris) — pending
- **ruff check + pytest + commit/push** (ML-Iris) — pending

---

## Standing Rules

- Conversation logs: `ML-Iris/Conversations/Conversation_YYYY-MM-DD_Topic_PartXX.md`
- Never expose `ramleo84@gmail.com` publicly on the website
- `vision_cache/` and `.mcp.json` must never be committed
- Portfolio project cards stay as grid — do NOT change to two-panel layout
- Vercel → ml-portfolio; Render → ml-unified backend
- Framer Motion + manual transform: outer `motion.div` (entrance) + inner `div` (tilt)
- `--bg-glass` for cards, `--bg-section` for section backgrounds
