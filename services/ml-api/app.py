#!/usr/bin/env python3
"""Slim FastAPI entry point — all logic lives in routers/core/."""
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from security.origin_policy import get_cors_kwargs, enforce_origin
from security.rate_limit import limiter
from security.body_size import enforce_body_size

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
from routers.rag.mm_ingest import router as rag_mm_ingest_router
from routers.rag.mm_video_store import router as rag_mm_video_store_router
from routers.rag.mm_similar import router as rag_mm_similar_router
from routers.rag.mm_inpaint import router as rag_mm_inpaint_router
from routers.rag.mm_ai_fill import router as rag_mm_ai_fill_router
from routers.rag.mm_deblur import router as rag_mm_deblur_router
from routers.rag.mm_steganography import router as rag_mm_steganography_router
from routers.rag.mm_moire import router as rag_mm_moire_router
from routers.rag.mm_text_to_image import router as rag_mm_text_to_image_router
from routers.rag.mm_watermark import router as rag_mm_watermark_router
from routers.rag.mm_plant_growth import router as rag_mm_plant_growth_router
from routers.rag.mm_qr_phishing import router as rag_mm_qr_phishing_router
from routers.rag.mm_photo_search import router as rag_mm_photo_search_router
from routers.rag.mm_adversarial import router as rag_mm_adversarial_router
from routers.rag.mm_plant_growth_species import router as rag_mm_plant_growth_species_router
from routers.rag.mm_liveness import router as rag_mm_liveness_router
from routers.rag.mm_face_cloak import router as rag_mm_face_cloak_router
from routers.rag.mm_style_cloak import router as rag_mm_style_cloak_router
from routers.rag.mm_face_reid_demo import router as rag_mm_face_reid_demo_router
from routers.rag.mm_crime_scene_reconstruction import router as rag_mm_crime_scene_router
from routers.rag.mm_rotoscope import router as rag_mm_rotoscope_router
from routers.rag.mm_astro_anomaly import router as rag_mm_astro_anomaly_router
from routers.rag.mm_wildlife_reid import router as rag_mm_wildlife_reid_router
from routers.rag.mm_ppe_compliance import router as rag_mm_ppe_compliance_router
from routers.rag.mm_robust_training import router as rag_mm_robust_training_router
from routers.rag.mm_depth import router as rag_mm_depth_router
from routers.rag.mm_captcha import router as rag_mm_captcha_router
from routers.rag.mm_malware_image import router as rag_mm_malware_image_router
from routers.rag.contradictions import router as rag_contradictions_router
from routers.rag.evaluate_mm import router as rag_mm_eval_router
from routers.rag.evaluate import router as rag_eval_router
from routers.rag.agent import router as rag_agent_router
from routers.rag.share import router as rag_share_router
from routers.rag.health import router as rag_health_router
from routers.rag.analytics import router as rag_analytics_router
from routers.rag import initialize_rag
from routers.vision import router as vision_router, init_vision_models
from routers.document import router as document_router
from routers.email_auth_check import router as email_auth_router
from routers.prompt_injection_check import router as prompt_injection_router
from routers.ai_code_detector import router as ai_code_detector_router
from routers.siem_triage import router as siem_triage_router
from routers.tls_headers_check import router as tls_headers_router
from routers.attack_surface_check import router as attack_surface_router
from routers.yara_scan import router as yara_scan_router
from routers.security_status import router as security_status_router

from routers.core.shared import (
    _detect_gpu, MODELS, _fetch_hf_models, _load,
    HERE,
)
from routers.core.monitoring import _req_log, _SKIP_PATHS
from security.log_redact import install as _install_log_redaction

# uvicorn only configures its own loggers — without this every logger.info()
# in routers/ is silently dropped and never shows up in HF Space logs.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

# Gemini's key travels in the URL, and httpx logs whole URLs. The filter
# attaches to the handlers basicConfig just created, so the call belongs here
# rather than at import time — before any router can log a request.
_install_log_redaction()


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
        init_vision_models()
    threading.Thread(target=_bg, daemon=True).start()
    kb_dir = os.path.join(os.environ.get("DATA_DIR", "data"), "knowledge_base")
    threading.Thread(target=initialize_rag, args=(kb_dir,), daemon=True).start()
    yield  # server binds and accepts requests immediately; models load in background


app = FastAPI(title="ML API", lifespan=_lifespan)

# Was allow_origins=["*"] — a real, confirmed gap (any origin could call
# every one of this backend's ~50 public routers). Now an explicit
# allowlist + Vercel-preview regex; see security/origin_policy.py.
app.add_middleware(CORSMiddleware, **get_cors_kwargs())

# Hard block, not just CORS headers: Hugging Face Spaces' own proxy
# injects its own permissive CORS policy in front of this app, so
# CORSMiddleware's headers alone are NOT actually enforced on the live
# Space (confirmed live — a disallowed-origin request still got CORS
# headers back). enforce_origin instead outright rejects (403) a
# disallowed Origin before any router runs, which the proxy can't
# override since it isn't a header negotiation.
app.add_middleware(BaseHTTPMiddleware, dispatch=enforce_origin)

# Rate limiting (security/rate_limit.py) — was ZERO rate limiting on any
# route before this. default_limits on the Limiter gives every route a
# baseline limit; SlowAPIMiddleware is what actually enforces that default
# for routes with no explicit @limiter.limit(...) decorator.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Global request-body size cap (security/body_size.py) — defense-in-depth
# beneath the handful of routers that already cap uploads individually.
app.add_middleware(BaseHTTPMiddleware, dispatch=enforce_body_size)

app.mount("/static", StaticFiles(directory=os.path.join(HERE, "frontend")), name="static")


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
def index(mode: str = "ml"):
    fname = {"eda": "eda.html", "vision": "vision.html"}.get(mode, "index.html")
    fpath = os.path.join(HERE, "frontend", fname)
    if os.path.exists(fpath):
        vision_url = os.environ.get("ML_VISION_URL", "").rstrip("/")
        eda_url    = os.environ.get("ML_EDA_URL", "").rstrip("/")
        with open(fpath, encoding="utf-8") as f:
            html = f.read()
        html = html.replace("'__VISION_URL__'", f"'{vision_url}'", 1)
        html = html.replace("'__EDA_URL__'",    f"'{eda_url}'",    1)
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
app.include_router(rag_mm_ingest_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_video_store_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_similar_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_inpaint_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_ai_fill_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_deblur_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_steganography_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_moire_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_text_to_image_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_watermark_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_plant_growth_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_plant_growth_species_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_qr_phishing_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_photo_search_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_adversarial_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_liveness_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_captcha_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_malware_image_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_face_cloak_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_face_reid_demo_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_crime_scene_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_rotoscope_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_astro_anomaly_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_wildlife_reid_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_ppe_compliance_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_style_cloak_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_robust_training_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_depth_router, prefix="/rag", tags=["rag"])
app.include_router(rag_contradictions_router, prefix="/rag", tags=["rag"])
app.include_router(rag_mm_eval_router, prefix="/rag", tags=["rag"])
app.include_router(rag_eval_router, prefix="/rag", tags=["rag"])
app.include_router(rag_agent_router, prefix="/rag", tags=["rag"])
app.include_router(rag_share_router, prefix="/rag", tags=["rag"])
app.include_router(rag_health_router, prefix="/rag", tags=["rag"])
app.include_router(rag_analytics_router, prefix="/rag", tags=["rag"])
app.include_router(vision_router)
app.include_router(document_router)
app.include_router(email_auth_router, tags=["email-auth"])
app.include_router(prompt_injection_router, tags=["prompt-injection"])
app.include_router(ai_code_detector_router, tags=["ai-code-detect"])
app.include_router(siem_triage_router, tags=["siem-triage"])
app.include_router(tls_headers_router, tags=["tls-headers"])
app.include_router(attack_surface_router, tags=["attack-surface"])
app.include_router(yara_scan_router, tags=["yara-scan"])
app.include_router(security_status_router, tags=["security-status"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
