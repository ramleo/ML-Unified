"""Q2 MCP extras — the tools/resources/prompts/auth that mcp_server.py wires onto
the FastMCP instance. Kept in a package (NOT named `mcp`, which would shadow the
installed MCP SDK that FastMCP imports) so mcp_server.py stays slim and under the
file-length limit.
"""
from mcp_ext.auth import ApiKeyVerifier
from mcp_ext.tools import register_tools
from mcp_ext.resources import register_resources
from mcp_ext.prompts import register_prompts

__all__ = ["ApiKeyVerifier", "register_tools", "register_resources", "register_prompts"]
