"""
Global request-body size cap — defense-in-depth beneath the handful of
individual routers that already cap uploads at 5MB (e.g.
`mm_malware_image.py`, `yara_scan.py`). Before this existed, a request to
any OTHER route (most of which don't expect large bodies at all) had no
size limit whatsoever — a large-body request could reach a router and be
fully read into memory before any application code got a chance to reject
it.

Checked via the `Content-Length` header before the body is read, so an
oversized request is rejected cheaply. A request with no declared
Content-Length (chunked transfer) is not blocked here — Starlette/uvicorn
have their own transport-level limits for that case.
"""
import os

from fastapi import Request
from fastapi.responses import JSONResponse

from security.events import log_security_event

MAX_BODY_BYTES = int(os.environ.get("MAX_REQUEST_BODY_BYTES", str(10 * 1024 * 1024)))  # 10MB


async def enforce_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_BODY_BYTES:
                log_security_event(
                    "oversized_request", request.url.path, request.client.host if request.client else "?",
                    detail=f"content-length={content_length}",
                )
                return JSONResponse(status_code=413, content={"detail": "Request body too large."})
        except ValueError:
            pass
    return await call_next(request)
