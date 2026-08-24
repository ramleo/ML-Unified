# Conversation – 2026-06-01 (Part 2): Bug Fixes & Deployment Flow

## Issues Found & Fixed This Session

---

### 1. bootstrap.py Had Its Own Wizard (Separate from init.py)

**Problem:** `bootstrap.py` has its own `collect_inputs()` function (lines 37–93) completely separate from `init.py`. When we added the Render API key prompt to `init.py` and `start.sh`, we missed `bootstrap.py`'s own wizard — so the key was never asked when using `curl bootstrap.py`.

**Fix:**
- Added Render API key prompt in `bootstrap.py`'s `collect_inputs()` after platform selection
- Added `render_api_key` to the returned dict
- Added `render_api_key` to `bootstrap.py`'s `write_config()` → stored in `.ml_config.json`

---

### 2. pip Cache Warnings in bootstrap.py

**Problem:**
```
WARNING: Cache entry deserialization failed, entry ignored
WARNING: Cache entry deserialization failed, entry ignored
```
Harmless but noisy — pip's local cache had stale entries.

**Fix:** Added `--no-cache-dir` to both pip install calls in bootstrap.py:
```python
subprocess.run([pip, "install", "--upgrade", "pip", "--no-cache-dir", "-q"], check=True)
subprocess.run([pip, "install", "-r", str(req), "--no-cache-dir", "-q"], check=True)
```

---

### 3. Auto-Predict on Every Keystroke (Frontend Bug)

**Problem:** The generated `index.html` called `debouncedPredict(420)` on every keystroke in a number field and `debouncedPredict(300)` on every slider move. This caused the app to fire a `/predict` API call continuously while typing.

**Root cause in `auto_pipeline.py` (lines 1994–2026):**
```javascript
inp.addEventListener('input', function() {
  ...
  debouncedPredict(420);  // ← fired on every keystroke
});
sl.addEventListener('input', function() {
  ...
  debouncedPredict(300);  // ← fired on every slider move
});
```

**Reference:** `ML-Insurance_with-Frontend` (https://github.com/ramleo/ML-Insurance_with-Frontend) uses "sync only, no auto-predict" for both — prediction only fires on button click.

**Fix:** Removed `debouncedPredict` calls from both listeners. Also removed the now-unused `_debounceTimer` and `debouncedPredict` function entirely. Both listeners are now sync-only (slider ↔ input sync).

**Files fixed:**
- `auto_pipeline.py` — generator fixed (affects all future projects)
- `bootstrap.py` — re-embedded updated `auto_pipeline.py`
- `Temp-Insurance_20260601_105725/index.html` — already-generated project patched directly

---

### 4. Two Staging Folders in Temp Directory

**Problem:** Two `.ml_staging_Temp-Insurance_*` folders visible in VS Code sidebar.

**Cause:** `bootstrap.py` was run twice (once on 20260531, once on 20260601). The cleanup `trap` in bootstrap.py didn't fire because the process was killed (Ctrl+C or force-quit) before it completed.

**Fix:** Safe to delete manually:
```bash
rm -rf "/Users/wrks/Downloads/Claude-documentation/Projects/Temp/.ml_staging_Temp-Insurance_20260531"*
```

---

### 5. Why bootstrap.py Doesn't Use Docker

**Clarification:** `bootstrap.py` is the "no Docker, no git" path — runs natively on the host. Docker only runs via `./run.sh` (requires `git clone` first).

| Path | Docker? | Requires git? |
|---|---|---|
| `./run.sh` | ✅ Yes | ✅ Yes (`git clone` first) |
| `./start.sh` | ❌ No | ✅ Yes (`git clone` first) |
| `python3 bootstrap.py` | ❌ No | ❌ No (`curl` only) |

---

## Commits This Session

| Hash | Repo | Description |
|---|---|---|
| `b41cf19` | ML-Pipeline-Auto | Auto-start app after pipeline + expose port 8000 in Docker |
| `11c13d9` | ML-Pipeline-Auto | Auto-deploy to Render via API after pipeline completes |
| `dbb6544` | ML-Pipeline-Auto | Fix bootstrap.py: Render API key prompt + suppress pip cache warnings |
| `fb43af1` | ML-Pipeline-Auto | Fix auto-predict: sliders sync only, predict on button click only |
| `c399828` | Temp-Insurance | Fix auto-predict in already-generated project |

---

## How Render Deployment Works End-to-End

```
./run.sh  (or python3 bootstrap.py)
  → wizard asks: Render API key → rnd_xxxxxxxxxxxx
  → stored in .ml_config.json (gitignored, never committed)
  → auto_pipeline.py runs → pushes generated project to GitHub
  → _deploy_render() called:
      GET  api.render.com/v1/owners  → get account ID
      POST api.render.com/v1/services → create web service (free tier)
  → Render pulls from GitHub → deploys in ~2 min
  → Live at: https://my-project.onrender.com
```

- Each user provides their OWN Render API key → deploys to THEIR account
- If no key provided → falls back to manual instructions

---

## Reference Frontend

`https://github.com/ramleo/ML-Insurance_with-Frontend` — used as the correct UI reference for:
- Predict on button click only (no auto-predict)
- Slider ↔ input sync without triggering prediction
- Overall UI/UX patterns to match in generated frontend

---

## Pending

- Automation tests (Insurance 2000 rows + Iris) — approved, not yet built
- Staging folder cleanup (manual delete)
