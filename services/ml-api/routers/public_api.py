"""Public API — the stable `/v1/` subset third parties call with an API key (Q1 M2).

Thin, versioned wrappers over logic the first-party site already uses, so the
public contract is decoupled from internal routes. Every route here requires a
valid `X-API-Key` (see security.api_key.require_api_key). First cut is deliberately
cheap/no-LLM — zero provider spend — to prove the key + quota + metering layer.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from security.api_key import require_api_key
from routers.tls_headers_check import run_tls_headers_scan
from routers.email_auth_check import run_email_auth_check
from routers.anomaly_detection import score as _anomaly_score, ScoreRequest, ScoreResponse

# Key check applies to every route in this router.
router = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)], tags=["public-api (v1)"])


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
