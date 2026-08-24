# Conversation — 2026-06-19 — ML-Unified — Part 102

---

## The Full Process — End to End

### What you have

Two separate deployable things:

```
ml-portfolio          (Next.js frontend)
ML-Unified backend    (FastAPI in Docker)
```

They are completely independent. The frontend is just a website. The backend is just an API. They talk to each other through one URL.

---

### How it works today

**Step 1 — Build and deploy the backend Docker image**

```bash
# From ML-Unified/services/ml-api/
docker build -t ml-api .
```

This image contains everything the backend needs — Python, all libraries, and the four built-in model `.pkl` files baked in. No internet access needed when it runs.

Push this image to whatever platform you want:
- Render: connect the GitHub repo, it reads `render.yaml`, builds and deploys automatically
- Railway: `railway up`
- HF Spaces: push the repo to the Space
- Locally: `docker run -p 8000:8000 ml-api`

The platform gives you a URL. Example: `https://ml-api.onrender.com`

**Step 2 — Set one env var on the frontend**

On your frontend deployment (Vercel, Netlify, anywhere):

```
NEXT_PUBLIC_ML_UNIFIED_URL = https://ml-api.onrender.com
```

That's it. Every link, button, and API call in the frontend now points at that backend.

**Step 3 — Deploy the frontend**

```bash
# ml-portfolio is a Next.js app, deploys to Vercel normally
git push
```

Vercel picks up the env var, bakes it into the build, and every `ML_UNIFIED_API` reference in the code resolves to your backend URL at build time.

---

### What happens when you switch platforms

Say Render runs out of free credits.

```
1. Deploy the same Docker image to Railway (or anywhere)
   → Railway gives you a new URL: https://ml-api.railway.app

2. Go to Vercel dashboard → Environment Variables
   → Change NEXT_PUBLIC_ML_UNIFIED_URL to https://ml-api.railway.app

3. Trigger a frontend redeploy (or it happens automatically)
```

Zero code changes. The backend image is identical. The frontend just points somewhere else.

---

### What "baked in" means for the models

Before the fix, the Docker image had an empty `models/` directory. The backend had to download the four built-in pipelines from HuggingFace at startup. That meant:
- Startup took longer
- It failed silently if HF was unreachable
- It only worked on HF Spaces (the download was gated on `SPACE_ID`)
- On Render, models were actually never loaded — the built-in datasets were broken

Now `COPY models/ models/` puts the pipelines inside the image itself at build time. The container starts, `_load()` finds the files immediately, models are ready in seconds. No network calls.

---

### What user-trained models need (separate concern)

When a user trains a new model through AutoML, the pipeline is saved to disk inside the running container. If the container restarts, that trained model is lost — containers are stateless by design.

Currently `_upload_model_to_hf` handles persistence on HF Spaces by uploading the trained `.pkl` to HF XET storage. On Render, trained models don't persist across restarts.

This is a separate problem from platform independence — it's about **state persistence**, not about which platform runs the code. Solutions would be an S3 bucket, a persistent volume mount, or a database — all platform-agnostic. That work hasn't been done yet.

---

### Summary of what's done vs what's not

| Concern | Status |
|---|---|
| Frontend has no hardcoded backend URL | Done |
| Data manipulation tools run in browser | Done |
| Backend runs from Docker image, no internet needed at startup | Done |
| Switching platforms requires zero code changes | Done |
| User-trained models persist across container restarts | Not done |

---

## Q&A

---

**Q: What does "What still legitimately needs the backend" mean?**

Those tools require actual machine learning computation that can't run in a browser:

**AutoML training** — scikit-learn, XGBoost, LightGBM, CatBoost running 5-fold cross-validation on your uploaded data. These are compiled C++/C libraries. They don't exist in JavaScript.

**Optuna tuning** — runs 30 trials of hyperparameter search, each trial trains and evaluates the model. Same libraries, same constraint.

**SHAP** — takes a trained scikit-learn/XGBoost model object and computes Shapley values against it. The model object lives on the backend; SHAP needs direct access to it.

**Ensemble** — trains VotingClassifier or StackingClassifier combining multiple fitted models. Again, Python ML objects.

**Contrast with what we moved client-side:**

Feature Engineering, Preprocessing, Feature Selection — these are *math on numbers in a CSV*. Addition, logarithms, correlation coefficients, variance. Any language can do that, so we wrote it in JavaScript and it runs in the browser.

**The point:** "legitimately needs the backend" means those four tools have a valid reason to call the Docker backend — not because of a hardcoding mistake, but because they genuinely need Python ML libraries to function. They're not platform *independent* in the sense of "runs anywhere without a backend", but they are platform independent in the sense that the Docker image runs identically on Render, HF Spaces, Railway, or your laptop. You just point `NEXT_PUBLIC_ML_UNIFIED_URL` at wherever you deployed it.

---

**Q: Then how to handle those?**

They're already handled — that's exactly what Docker + the env var does.

Those four tools call `ML_UNIFIED_API` (the env var) for every request. The backend is a Docker image that runs identically anywhere. So the workflow when a platform runs out of credits is:

```
1. Build the same Docker image
2. Push it to a new platform (Railway, HF Spaces, a VPS, localhost)
3. Update NEXT_PUBLIC_ML_UNIFIED_URL on the frontend to the new URL
4. Done — AutoML, Optuna, SHAP, Ensemble all work again, no code changes
```

The difference between these and the client-side tools is **where the compute runs**, not whether they're platform independent:

| Tool | Compute runs in | Platform independent via |
|---|---|---|
| Feature Engineering | Browser | Client-side JS — no backend at all |
| Preprocessing | Browser | Client-side JS — no backend at all |
| Feature Selection | Browser | Client-side JS — no backend at all |
| AutoML | Docker backend | Docker image + env var |
| Optuna | Docker backend | Docker image + env var |
| SHAP | Docker backend | Docker image + env var |
| Ensemble | Docker backend | Docker image + env var |

Both groups are platform independent — they just achieve it differently. The client-side tools need no backend at all. The ML training tools need a backend, but that backend is a portable Docker container that you can run anywhere.

---

## Detailed Explanations

---

### 1. How It Works Today — In Detail

**The Frontend (ml-portfolio)**

This is a Next.js app deployed on Vercel. When you run `git push`, Vercel pulls the code and builds it. During the build, Next.js reads every `NEXT_PUBLIC_*` environment variable and **bakes it directly into the JavaScript bundle**. After the build, there is no server — just static HTML, CSS, and JS files served from Vercel's CDN.

So when a user opens your portfolio in a browser:
- The browser downloads the JS bundle from Vercel's CDN
- That bundle already has `ML_UNIFIED_API = "https://your-backend-url.com"` hardcoded inside it (baked in at build time)
- When the user clicks "Launch App" or runs AutoML, the browser sends an HTTP request directly to that URL
- Vercel is not involved in that request at all — it goes straight from the user's browser to your backend

This is why changing `NEXT_PUBLIC_ML_UNIFIED_URL` requires a redeploy — the value is frozen into the bundle at build time, not read at runtime.

**The Backend (ML-Unified)**

This is a FastAPI app running inside a Docker container. When Render (or any platform) deploys it:

1. The platform clones your GitHub repo
2. It runs `docker build` using `services/ml-api/Dockerfile`
3. The Dockerfile installs Python, all libraries, copies your code, and now also copies the `.pkl` model files into the image
4. The result is a self-contained image — everything needed to run the API is inside it
5. The platform starts the container: `uvicorn app:app --host 0.0.0.0 --port 8000`
6. On startup, `_lifespan()` runs in a background thread: calls `_load()` which scans the `schemas/` directory, finds the four built-in JSON schemas, loads the corresponding `.pkl` pipelines from `models/`, and puts them into the `MODELS` dict in memory
7. The container is now ready. Every API call (`/predict`, `/train`, `/preprocess`, etc.) is handled by this running Python process

The container is **stateless** by default — its filesystem is the Docker image. Nothing written to disk inside the container survives a restart.

**How a request flows end to end**

```
User browser
  │
  ├── Opens ml-portfolio on Vercel CDN
  │     └── Gets HTML + JS bundle (ML_UNIFIED_API baked in)
  │
  ├── Clicks "Launch App" on AutoML card
  │     └── browser opens https://your-backend-url.com/?mode=ml
  │           └── FastAPI serves frontend/index.html from inside the container
  │
  └── Uploads CSV and clicks Train
        └── Browser POST https://your-backend-url.com/train
              └── FastAPI runs AutoML pipeline (scikit-learn, XGBoost, etc.)
              └── Saves trained model to models/ inside the container
              └── Returns results JSON to browser
```

---

### 2. What Happens When You Switch Platforms — Step by Step

Say you're on Render and the free tier runs out.

**Step 1 — Deploy backend to the new platform**

The Docker image is already built and stored. You don't need to change a single line of code.

**Example: switching to Railway**

```bash
# Install Railway CLI, log in
railway login

# In ML-Unified/services/ml-api/
railway up
```

Railway reads your Dockerfile, builds the image (identical to what Render built), and gives you a URL like `https://ml-api-production.up.railway.app`.

**Example: switching to HuggingFace Spaces**

Push the repo to a HF Space that has Docker runtime enabled. HF reads the Dockerfile, builds the same image.

**Example: running locally**

```bash
docker build -t ml-api .
docker run -p 8000:8000 ml-api
# Backend is now at http://localhost:8000
```

**Step 2 — Point the frontend at the new backend**

Go to Vercel dashboard → your ml-portfolio project → Settings → Environment Variables.

Change:
```
NEXT_PUBLIC_ML_UNIFIED_URL = https://ml-api-production.up.railway.app
```

**Step 3 — Redeploy the frontend**

Trigger a redeploy on Vercel (one click, or push a commit). Vercel rebuilds the JS bundle with the new URL baked in. Takes about 60 seconds.

That's it. The frontend now talks to Railway. No code was changed anywhere.

**Why this works without code changes**

Before our fix, `urls.ts` had:
```ts
export const ML_UNIFIED_API =
  process.env.NEXT_PUBLIC_ML_UNIFIED_URL ?? "https://ml-unified.onrender.com";
```

The fallback `?? "https://ml-unified.onrender.com"` meant: if you forgot to set the env var, it silently called Render. Now it's:
```ts
export const ML_UNIFIED_API = (process.env.NEXT_PUBLIC_ML_UNIFIED_URL ?? "").replace(/\/$/, "");
```

No fallback. The env var is the only source of truth. Set it to Railway, the app calls Railway. Set it to localhost, the app calls localhost. The code itself has no opinion about where the backend lives.

---

### 3. Can We Handle Model Persistence Across Restarts?

Yes. This is solvable.

**The Problem**

When a user trains a new model through AutoML, the trained pipeline is saved here inside the running container:

```
/app/models/custom_model_pipeline.pkl
/app/models/custom_model_fe.pkl
/app/schemas/custom_model.json
```

If the container restarts (Render restarts it on deploy, on crash, or daily on the free tier), these files disappear. The built-in models (titanic, iris, etc.) survive because they're baked into the Docker image. User-trained models are not — they were created after the image was built.

**Option A — Persistent Volume Mount (simplest)**

Most platforms let you attach a persistent disk to a container. The disk survives restarts and redeployments.

```
Platform      │ How it works
──────────────┼───────────────────────────────────────
Render        │ "Disk" add-on, mount at /app/models and /app/schemas
Railway       │ Persistent Volume, mount at /app/models
HF Spaces     │ Already handled via _upload_model_to_hf (HF XET storage)
Local Docker  │ docker run -v ./models:/app/models -v ./schemas:/app/schemas ml-api
```

No code changes needed. The container writes to `/app/models` as it does today — but now that path is backed by a real disk that persists.

The downside: persistent volumes are usually paid features. Also, volumes are tied to one platform — you can't easily move them when switching.

**Option B — External Object Storage (S3 or equivalent)**

Store trained models in an S3 bucket (or S3-compatible: Cloudflare R2, Backblaze B2, MinIO). Any platform can read from the same bucket.

```
After training:   upload pipeline.pkl → S3
On startup:       download all user model pkls from S3 → /app/models/
```

This is true platform independence for model persistence. The bucket is separate from any platform. Switch from Render to Railway — the new container pulls the same models from S3 on startup.

Cloudflare R2 is free up to 10 GB with no egress fees.

**Option C — HuggingFace XET (already partially implemented, now fully implemented)**

`_upload_model_to_hf` and `_fetch_hf_models` already did this — but only when `SPACE_ID` was set (i.e., only on HF Spaces).

**This is now fixed (commit `8b3d282`).** Both functions now gate on `HF_TOKEN` instead of `SPACE_ID`:

```python
# Before (only ran on HF Spaces):
def _fetch_hf_models():
    if not os.environ.get("SPACE_ID"):
        return

# After (runs anywhere HF_TOKEN is set):
def _fetch_hf_models():
    token = os.environ.get("HF_TOKEN")
    if not token:
        return
```

Same change in `_upload_model_to_hf` — the `SPACE_ID` guard is removed entirely.

Now Render, Railway, or any other platform can persist trained models to HF XET and reload them on startup, using HF as a free model store.

---

## Future: When Model Files Grow Large

**The LFS situation**

The `.gitattributes` file has:
```
services/ml-api/models/*.pkl filter=lfs diff=lfs merge=lfs -text
```

The pkl files are tracked via Git LFS. Currently they are tiny (1.4 MB total), but the LFS tracking was set up anticipating growth.

The issue: when Docker builds from a git repo clone, if the build server doesn't have LFS configured, it gets pointer files (a few bytes of text) instead of actual pkl content. `COPY models/ models/` would copy pointers, not real pipelines.

**When to act based on model size**

| Model size | Approach |
|---|---|
| Now (1.4 MB) | Files baked in Docker image via `COPY models/ models/` — works as long as build server has LFS support or files are removed from LFS |
| Grows to ~50 MB | Switch to `_fetch_hf_models()` on startup (HF_TOKEN gate — already implemented), remove from git entirely |
| Grows to 200 MB+ | Bake into image during `docker build` using `--build-arg HF_TOKEN`, models come from HF at build time, not from git |

**Build-time download approach (for large models)**

```dockerfile
FROM python:3.11-slim
# ... install dependencies ...

ARG HF_TOKEN
RUN python -c "
from huggingface_hub import hf_hub_download
import os, shutil
files = ['models/titanic_pipeline.pkl', 'models/iris_pipeline.pkl', ...]
for f in files:
    cached = hf_hub_download(repo_id='wram1708/ml-unified', repo_type='space', filename=f, token=os.environ['HF_TOKEN'])
    os.makedirs(os.path.dirname(f), exist_ok=True)
    shutil.copy2(cached, f)
"
COPY app.py .
# ... rest of Dockerfile
```

Build with:
```bash
docker build --build-arg HF_TOKEN=hf_xxx -t ml-api .
```

Models are baked into the image at build time, from HF — not from git. Container starts instantly. No size limit, no git bloat.

---

## Complete Model Sync Behavior (post commit `8b3d282`)

**Today (small files, in git)**
```
Docker build → COPY models/ models/ → built-ins in image
HF_TOKEN set → _fetch_hf_models() runs → os.path.exists skips built-ins
                                        → downloads only user-trained models
HF_TOKEN not set → silent skip, built-ins still available from image
```

**When models grow large (remove from git)**
```
Docker build → models/ is empty
HF_TOKEN set → _fetch_hf_models() downloads everything on startup
HF_TOKEN not set → no models → app warns but starts
```

**After training a new model on any platform**
```
HF_TOKEN set → _upload_model_to_hf() runs → pipeline.pkl uploaded to HF
                Container restarts → _fetch_hf_models() finds it → loads it
HF_TOKEN not set → model lost on restart (expected, user is warned)
```

**One env var to set on every platform: `HF_TOKEN`**. That's the only operational requirement for full model persistence anywhere.

---

## Commits This Session

| Hash | Repo | Description |
|---|---|---|
| `99871db` | ml-portfolio | feat(feature-selection): rewrite as real client-side interactive tool |
| `1d10e2f` | ml-portfolio | feat(feature-selection): add RFE and Select K Best methods |
| `f87d3de` | ml-portfolio | fix(platform): remove hardcoded Render URLs from navigation links |
| `4f4e972` | ML-Unified | fix(docker): bake built-in models into image |
| `8b3d282` | ML-Unified | fix(models): make HF model sync platform-agnostic via HF_TOKEN |
