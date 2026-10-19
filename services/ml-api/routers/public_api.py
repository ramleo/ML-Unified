"""Public API — the stable `/v1/` subset third parties call with an API key (Q1 M2).

Thin, versioned wrappers over logic the first-party site already uses, so the
public contract is decoupled from internal routes. Every route here requires a
valid `X-API-Key` (see security.api_key.require_api_key). First cut is deliberately
cheap/no-LLM — zero provider spend — to prove the key + quota + metering layer.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from security.api_key import require_api_key
from routers.tls_headers_check import run_tls_headers_scan
from routers.email_auth_check import run_email_auth_check
from routers.anomaly_detection import score as _anomaly_score, ScoreRequest, ScoreResponse

# Key check applies to every route in this router.
router = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)], tags=["public-api (v1)"])

# A second, UNGATED router just for the public spec — people must be able to read
# how to call the API before they have a key.
meta_router = APIRouter(tags=["public-api (v1)"])


@meta_router.get("/v1/openapi.json", include_in_schema=False)
def v1_openapi(request: Request):
    """Trimmed OpenAPI 3.1 spec covering only the /v1/* public routes, with the
    X-API-Key security scheme — importable into Postman / client generators."""
    full = request.app.openapi()
    paths = {p: v for p, v in full.get("paths", {}).items() if p.startswith("/v1/")}
    return {
        "openapi": full.get("openapi", "3.1.0"),
        "info": {
            "title": "AIRaML Public API",
            "version": "1.0.0",
            "description": "Stable, API-key-authenticated subset of the AIRaML tools. "
                           "Send your key in the `X-API-Key` header.",
        },
        "servers": [{"url": "https://wram1708-ml-unified.hf.space"}],
        "paths": paths,
        "components": {
            **full.get("components", {}),
            "securitySchemes": {
                "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            },
        },
        "security": [{"ApiKeyAuth": []}],
    }


class TlsHeadersBody(BaseModel):
    host: str = Field(..., min_length=1, max_length=253, description="Hostname or URL to scan.")


class EmailAuthBody(BaseModel):
    headers: str = Field(..., min_length=1, max_length=100_000,
                         description="Raw email headers to analyse (SPF/DKIM/DMARC).")


@router.post("/tls-headers/check", summary="TLS + security-header scan of a host")
def v1_tls_headers(body: TlsHeadersBody):
    return run_tls_headers_scan(body.host)


@router.post("/email-auth/check", summary="SPF/DKIM/DMARC analysis of email headers")
def v1_email_auth(body: EmailAuthBody):
    return run_email_auth_check(body.headers)


@router.post("/anomaly-detection/score", response_model=ScoreResponse,
             summary="Isolation-Forest anomaly scores for event rows")
def v1_anomaly_score(body: ScoreRequest):
    return _anomaly_score(body)
