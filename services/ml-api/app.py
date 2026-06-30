#!/usr/bin/env python3
"""Slim FastAPI entry point — all logic lives in routers/core/."""
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse

from routers import shap as _shap_router
from routers import pipeline as _pipeline_router
from routers import training as _training_router
from routers import drift as _drift_router
from routers.core import inference as inference_router
from routers.core import automl as automl_router
from routers.core import monitoring as monitoring_router
from routers.pipeline_builder import router as _pb_router
from routers.rag.query import router as rag_router
from routers.rag.ingest import router as rag_ingest_router
from routers.rag import initialize_rag

from routers.core.shared import (
    _detect_gpu, MODELS, _fetch_hf_models, _load,
    FRONTEND, HERE,
)
from routers.core.monitoring import _req_log, _SKIP_PATHS


@asynccontextmanager
async def _lifespan(app: FastAPI):
    import threading
    def _bg():
        try:
            _fetch_hf_models()
            _load()
            print(f"Models loaded: {list(MODELS.keys())}", flush=True)
        except Exception as exc:
            import traceback
            print("ERROR: _load() failed:", exc, flush=True)
            traceback.print_exc()
    threading.Thread(target=_bg, daemon=True).start()
    threading.Thread(target=initialize_rag, args=("data/knowledge_base",), daemon=True).start()
    yield  # server binds and accepts requests immediately; models load in background


app = FastAPI(title="ML API", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _monitor(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    if request.url.path not in _SKIP_PATHS:
        _req_log.append({
            "ts":     time.time(),
            "path":   request.url.path,
            "method": request.method,
            "status": response.status_code,
            "ms":     ms,
        })
    return response


@app.get("/")
def index():
    if os.path.exists(FRONTEND):
        vision_url = os.environ.get("ML_VISION_URL", "").rstrip("/")
        eda_url    = os.environ.get("ML_EDA_URL", "").rstrip("/")
        with open(FRONTEND, encoding="utf-8") as f:
            html = f.read()
        html = html.replace("let VISION_API = '';", f"let VISION_API = '{vision_url}';", 1)
        html = html.replace("let EDA_API = '';",    f"let EDA_API = '{eda_url}';",       1)
        return HTMLResponse(
            html,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    return {"message": "ML API — see /docs"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    path = os.path.join(HERE, "frontend", "favicon.ico")
    if os.path.exists(path):
        return FileResponse(path, media_type="image/x-icon")
    return HTMLResponse(status_code=204)


@app.get("/icon.svg", include_in_schema=False)
def favicon_svg():
    path = os.path.join(HERE, "frontend", "icon.svg")
    if os.path.exists(path):
        return FileResponse(path, media_type="image/svg+xml",
                            headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return HTMLResponse(status_code=204)


@app.get("/health")
def health():
    return {"status": "ok", "models": list(MODELS.keys())}


@app.get("/system-info")
def system_info():
    return {"gpu": _detect_gpu()}


@app.get("/app-config")
def app_config():
    """Return runtime config consumed by the frontend."""
    return {
        "vision_url": os.environ.get("ML_VISION_URL", ""),
        "eda_url":    os.environ.get("ML_EDA_URL", ""),
    }


# ── Include all routers ───────────────────────────────────────────────────────
app.include_router(inference_router.router)
app.include_router(automl_router.router)
app.include_router(monitoring_router.router)
app.include_router(_shap_router.router)
app.include_router(_pipeline_router.router)
app.include_router(_training_router.router)
app.include_router(_drift_router.router)
app.include_router(_pb_router)
app.include_router(rag_router, prefix="/rag", tags=["rag"])
app.include_router(rag_ingest_router, prefix="/rag", tags=["rag"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
