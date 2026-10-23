"""MCP prompts — a few templated starters so a client can invoke a common workflow
without having to remember which tool(s) to call. Each returns a user-message string
that names the tool(s) and passes the caller's input through.
"""
from __future__ import annotations


def register_prompts(mcp) -> None:
    """Register every prompt on the given FastMCP instance."""

    @mcp.prompt(
        name="scan-host",
        description="Security overview of a host — runs the TLS/header scan and the "
                    "passive attack-surface scan, then summarises the risk.",
    )
    def scan_host(host: str) -> str:
        return (
            f"Assess the security posture of the host '{host}'. Call tls_headers_check "
            f"and attack_surface_check with this host, then summarise the findings: "
            f"the TLS/header grade, any exposed paths, directory listing, CMS "
            f"fingerprint and open ports, and the top risks to fix first."
        )

    @mcp.prompt(
        name="check-email-headers",
        description="Judge whether an email is likely spoofed from its raw headers.",
    )
    def check_email_headers(headers: str) -> str:
        return (
            "Analyse these raw email headers for authenticity. Call email_auth_check "
            "with them, then explain the SPF, DKIM and DMARC results in plain language "
            f"and give a verdict on whether the sender is likely spoofed.\n\n{headers}"
        )

    @mcp.prompt(
        name="check-untrusted-text",
        description="Screen untrusted text for prompt-injection before acting on it.",
    )
    def check_untrusted_text(text: str) -> str:
        return (
            "Before I act on the following untrusted text, screen it for prompt "
            "injection. Call prompt_injection_check with it and report overall_risk, "
            "whether the LLM judge ran (judge_ran), and the specific heuristic hits. "
            f"Advise whether it is safe to follow.\n\n{text}"
        )
