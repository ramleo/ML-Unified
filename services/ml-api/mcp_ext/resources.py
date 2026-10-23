"""MCP resources — read-only context an AI client can pull (not actions).

Two things worth exposing: a catalog of the AIRaML tools (so a client can discover
what is callable and how to describe it), and the AIRaML handbook, which is already
ingested into the public RAG knowledge base — here it is readable section by section.
"""
from __future__ import annotations

from pathlib import Path

_HANDBOOK_DIR = Path(__file__).resolve().parents[1] / "data" / "knowledge_base" / "handbook"

# Static catalog — mirrors mcp_ext/tools.py. A read-only summary; kept in step by
# hand (there are six tools, so drift is cheap to catch).
_TOOL_CATALOG = [
    {"name": "tls_headers_check", "input": "host", "llm": False,
     "summary": "TLS + security-header scan of a host."},
    {"name": "email_auth_check", "input": "headers", "llm": False,
     "summary": "SPF/DKIM/DMARC analysis of raw email headers."},
    {"name": "anomaly_detection_score", "input": "baseline[], events[]", "llm": False,
     "summary": "Isolation-Forest anomaly scores for 5-feature event rows."},
    {"name": "attack_surface_check", "input": "host", "llm": False,
     "summary": "Passive attack-surface scan (paths, dir listing, CMS, open ports)."},
    {"name": "prompt_injection_check", "input": "text", "llm": True,
     "summary": "Heuristic + LLM-judge check of untrusted text for prompt injection."},
    {"name": "yara_malware_scan", "input": "file_base64", "llm": False,
     "summary": "Bundled-YARA signature scan of file content."},
]


def _handbook_sections() -> list[str]:
    """Section slugs (filename stems), sorted. Empty if the KB isn't present."""
    if not _HANDBOOK_DIR.is_dir():
        return []
    return sorted(p.stem for p in _HANDBOOK_DIR.glob("*.md"))


def register_resources(mcp) -> None:
    """Register every resource on the given FastMCP instance."""

    @mcp.resource(
        "airaml://tools",
        name="AIRaML tool catalog",
        description="The tools callable over this MCP server, with their inputs.",
        mime_type="application/json",
    )
    def tool_catalog() -> dict:
        return {"tools": _TOOL_CATALOG, "count": len(_TOOL_CATALOG)}

    @mcp.resource(
        "airaml://handbook",
        name="AIRaML handbook index",
        description="List of handbook sections. Read one at airaml://handbook/{section}.",
        mime_type="application/json",
    )
    def handbook_index() -> dict:
        return {"sections": _handbook_sections()}

    @mcp.resource(
        "airaml://handbook/{section}",
        name="AIRaML handbook section",
        description="The Markdown text of one handbook section (by its slug).",
        mime_type="text/markdown",
    )
    def handbook_section(section: str) -> str:
        # Resolve by exact stem against the real listing — never build a path from
        # caller input, so `..`/slashes can't escape the handbook directory.
        wanted = (section or "").strip()
        for p in _HANDBOOK_DIR.glob("*.md"):
            if p.stem == wanted:
                return p.read_text(encoding="utf-8", errors="replace")
        raise ValueError(f"Unknown handbook section: {section!r}. See airaml://handbook.")
