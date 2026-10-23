"""Bearer-token auth for the MCP server — reuses the Q1 API keys.

The client sends its `ak_live_…` key as a Bearer token; the verifier hashes it and
validates via the same token-gated frontend route (`/api/keys/verify`) the REST
`/v1/` layer uses, so one key works for both. Moved out of mcp_server.py unchanged.
"""
from __future__ import annotations

import asyncio
import hashlib

from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken

from security.api_key import _verify as _verify_key_hash


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
