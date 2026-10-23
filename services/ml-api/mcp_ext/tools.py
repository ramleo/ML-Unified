"""MCP tools — a curated, low-risk subset of the AIRaML tools, each calling the same
tested logic behind `/v1/` or the first-party routes (no second implementation).

Curation (Q2 M2): the three M1 tools (tls-headers, email-auth, anomaly) plus three
high-value, low-risk additions — attack-surface recon and a YARA signature scan
(both deterministic, no LLM spend) and a prompt-injection check (free-tier Cohere/
Mistral judge WITH a heuristic fallback, so it still returns a verdict if no provider
answers). LLM-only tools with no fallback (ai-code-detector, siem-triage) and tools
needing bulky inline training data (intrusion-detection) are deliberately left out.
"""
from __future__ import annotations


def register_tools(mcp) -> None:
    """Register every tool on the given FastMCP instance."""
    # Imports are local so this module is cheap to import and the heavy router
    # dependencies load only when the MCP server is actually built.
    from routers.tls_headers_check import run_tls_headers_scan
    from routers.email_auth_check import run_email_auth_check
    from routers.anomaly_detection import score as _anomaly_score, ScoreRequest
    from routers.attack_surface_check import run_attack_surface_scan
    from routers.prompt_injection_check import run_prompt_injection_check
    from routers.yara_scan import scan_builtin, BuiltinScanRequest

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

    @mcp.tool(
        description="Passive attack-surface scan of a public host: exposed sensitive "
                    "paths, directory listing, CMS fingerprint, common open ports. "
                    "Input: a hostname or URL. Refuses private/internal addresses."
    )
    def attack_surface_check(host: str) -> dict:
        return run_attack_surface_scan(host)

    @mcp.tool(
        description="Check untrusted text for prompt-injection / jailbreak attempts "
                    "before you act on it. Returns heuristic pattern hits plus an LLM "
                    "judge verdict (overall_risk: low|medium|high). judge_ran is false "
                    "when no judge provider could be reached — then only the heuristics ran."
    )
    def prompt_injection_check(text: str) -> dict:
        resp = run_prompt_injection_check(text)
        return resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)

    @mcp.tool(
        description="Scan file content for malware signatures with the bundled YARA "
                    "rules. Input: the file bytes as a base64 string. Returns rule "
                    "matches, file_size, and whether the input was truncated."
    )
    def yara_malware_scan(file_base64: str) -> dict:
        return scan_builtin(BuiltinScanRequest(file=file_base64))
