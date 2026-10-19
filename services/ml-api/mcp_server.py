"""MCP server (Q2) — exposes a curated tool subset to AI clients over Streamable
HTTP, mounted at /mcp on the same FastAPI app.

Auth reuses the Q1 API keys: the client sends its `ak_live_…` key as a Bearer
token; the verifier hashes it and validates via the same token-gated frontend route
(`/api/keys/verify`) the REST `/v1/` layer uses — so one key works for both. Tools
call the same tested logic behind `/v1/`, so there is no second implementation.
"""
from __future__ import annotations

import asyncio
import hashlib

from fastmcp import FastMCP
from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken

from security.api_key import _verify as _verify_key_hash
from routers.tls_headers_check import run_tls_headers_scan
from routers.email_auth_check import run_email_auth_check
from routers.anomaly_detection import score as _anomaly_score, ScoreRequest


class ApiKeyVerifier(TokenVerifier):
    """Validates a Bearer token that is an AIRaML API key (ak_live_…) against the
    frontend verify route. Returns None → 401 for the MCP client."""

    async def verify_token(self, token: str) -> AccessToken | None:
        # Must be async — FastMCP awaits this. The verify call is blocking httpx,
        # so run it off the event loop.
        if not token:
            return None
        key_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        try:
            result = await asyncio.to_thread(_verify_key_hash, key_hash)
        except Exception:
            return None
        if not result.get("valid"):
            return None
        return AccessToken(token=token, client_id="airaml-api-key", scopes=[])


mcp = FastMCP(
    name="AIRaML",
    instructions="AIRaML tools over MCP. Authenticate with your AIRaML API key "
                 "(ak_live_…) as a Bearer token. Tools mirror the public /v1 REST API.",
    auth=ApiKeyVerifier(),
)


@mcp.tool(description="TLS and security-header scan of a host. Input: a hostname or URL.")
def tls_headers_check(host: str) -> dict:
    return run_tls_headers_scan(host)


@mcp.tool(description="SPF/DKIM/DMARC analysis of raw email headers.")
def email_auth_check(headers: str) -> dict:
    return run_email_auth_check(headers)


@mcp.tool(
    description="Isolation-Forest anomaly scores for event rows. baseline and events "
                "are lists of rows, each row 5 numbers: "
                "[req_per_min, payload_bytes, hour, path_randomness, error_rate]."
)
def anomaly_detection_score(
    baseline: list[list[float]],
    events: list[list[float]],
    contamination: float | None = None,
) -> dict:
    resp = _anomaly_score(ScoreRequest(baseline=baseline, events=events, contamination=contamination))
    return resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
