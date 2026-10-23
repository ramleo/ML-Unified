"""MCP server (Q2) — exposes a curated set of tools, resources and prompts to AI
clients over Streamable HTTP, mounted at /mcp on the same FastAPI app.

Auth reuses the Q1 API keys: the client sends its `ak_live_…` key as a Bearer token;
the verifier hashes it and validates via the same token-gated frontend route
(`/api/keys/verify`) the REST `/v1/` layer uses — so one key works for both. Tools
call the same tested logic behind the first-party routes, so there is no second
implementation. The tools/resources/prompts/auth live in the `mcp_ext` package
(see there); this module just wires them onto one FastMCP instance and exports it.
"""
from __future__ import annotations

from fastmcp import FastMCP

from mcp_ext import ApiKeyVerifier, register_tools, register_resources, register_prompts

mcp = FastMCP(
    name="AIRaML",
    instructions="AIRaML tools over MCP. Authenticate with your AIRaML API key "
                 "(ak_live_…) as a Bearer token. Tools mirror the public /v1 REST API; "
                 "resources (airaml://tools, airaml://handbook) give read-only context; "
                 "prompts bundle common workflows.",
    auth=ApiKeyVerifier(),
)

register_tools(mcp)
register_resources(mcp)
register_prompts(mcp)
