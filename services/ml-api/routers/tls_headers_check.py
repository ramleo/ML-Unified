"""
TLS / Security-Headers Scanner — cybersecurity shortlist pick #5.

Real Mozilla-Observatory-/SSL-Labs-style check, live network, zero ML:
given a domain, verify its TLS certificate health (expiry, self-signed/
untrusted chain, deprecated protocol version) and audit its HTTP response
for the standard security headers (CSP, HSTS, X-Frame-Options, etc.).
Same "live network check, honest qualitative verdict + warnings list,
never a fabricated safe/malicious binary" pattern as email_auth_check.py.

SSRF note: unlike email_auth_check.py (DNS TXT lookups only), this tool
opens a real TCP connection + HTTP GET to a user-supplied host. Before
connecting, every resolved address is checked against private/loopback/
link-local/reserved ranges and rejected if any match — prevents this
endpoint being used to port-scan the Space's own internal network or hit
cloud metadata endpoints (169.254.169.254, etc.).
"""

import logging
import socket
import ssl
from datetime import datetime, timezone

import certifi
import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from routers.security_shared import normalize_host, resolve_public_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tls-headers")

_CONNECT_TIMEOUT = 6.0
_DEPRECATED_PROTOCOLS = {"SSLv2", "SSLv3", "TLSv1", "TLSv1.1"}
_SECURITY_HEADERS = [
    ("Content-Security-Policy", "content_security_policy"),
    ("Strict-Transport-Security", "strict_transport_security"),
    ("X-Frame-Options", "x_frame_options"),
    ("X-Content-Type-Options", "x_content_type_options"),
    ("Referrer-Policy", "referrer_policy"),
    ("Permissions-Policy", "permissions_policy"),
]


def _check_tls(host: str, resolved_ip: str) -> dict:
    result = {
        "connected": False,
        "protocol": None,
        "cipher": None,
        "verified": False,
        "verify_error": None,
        "subject": None,
        "issuer": None,
        "not_after": None,
        "days_until_expiry": None,
        "expired": None,
        "deprecated_protocol": False,
    }

    # First attempt: real verification (default context, hostname check).
    # Uses certifi's CA bundle explicitly rather than the OS default store
    # — some environments (notably python.org macOS installers) ship
    # without a usable system CA bundle wired up, which would otherwise
    # cause every real, validly-signed certificate to fail verification.
    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        with socket.create_connection((resolved_ip, 443), timeout=_CONNECT_TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls_sock:
                cert = tls_sock.getpeercert()
                result["connected"] = True
                result["verified"] = True
                result["protocol"] = tls_sock.version()
                cipher = tls_sock.cipher()
                result["cipher"] = cipher[0] if cipher else None
                subject = dict(x[0] for x in cert.get("subject", []))
                issuer = dict(x[0] for x in cert.get("issuer", []))
                result["subject"] = subject.get("commonName")
                result["issuer"] = issuer.get("commonName")
                not_after_raw = cert.get("notAfter")
                if not_after_raw:
                    not_after = datetime.strptime(not_after_raw, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                    result["not_after"] = not_after.isoformat()
                    delta = (not_after - datetime.now(timezone.utc)).days
                    result["days_until_expiry"] = delta
                    result["expired"] = delta < 0
                result["deprecated_protocol"] = result["protocol"] in _DEPRECATED_PROTOCOLS
                return result
    except ssl.SSLCertVerificationError as exc:
        result["verify_error"] = str(exc)
    except (socket.timeout, ConnectionRefusedError, OSError) as exc:
        result["verify_error"] = f"Could not connect: {exc}"
        return result

    # Verification failed — reconnect once more without verification just
    # to read the negotiated protocol/cipher, which don't require a valid
    # chain. Chain metadata (subject/issuer/expiry) is deliberately left
    # unset here: it was never actually validated, so showing it would be
    # misleading — the verification failure itself is the real finding.
    try:
        ctx = ssl._create_unverified_context()
        with socket.create_connection((resolved_ip, 443), timeout=_CONNECT_TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls_sock:
                result["connected"] = True
                result["protocol"] = tls_sock.version()
                cipher = tls_sock.cipher()
                result["cipher"] = cipher[0] if cipher else None
                result["deprecated_protocol"] = result["protocol"] in _DEPRECATED_PROTOCOLS
    except (socket.timeout, ConnectionRefusedError, OSError, ssl.SSLError) as exc:
        result["verify_error"] = result["verify_error"] or f"Could not connect: {exc}"

    return result


def _check_headers(host: str) -> dict:
    result = {"reachable": False, "status_code": None, "raw": {}}
    for _, field in _SECURITY_HEADERS:
        result[field] = False
    try:
        resp = httpx.get(f"https://{host}", timeout=_CONNECT_TIMEOUT, follow_redirects=True)
        result["reachable"] = True
        result["status_code"] = resp.status_code
        for header_name, field in _SECURITY_HEADERS:
            value = resp.headers.get(header_name)
            result[field] = value is not None
            if value is not None:
                result["raw"][header_name] = value
    except httpx.HTTPError as exc:
        logger.info("Header fetch failed for %s: %s", host, exc)
    return result


def run_tls_headers_scan(raw_host: str) -> dict:
    host = normalize_host(raw_host)
    resolved_ip = resolve_public_ip(host)
    if resolved_ip is None:
        return {
            "host": host,
            "blocked": True,
            "reason": "This domain didn't resolve to any public IP address — it may be private/internal, "
                      "unreachable, or not a real domain. This scanner will not connect to private or "
                      "internal network addresses.",
        }

    tls = _check_tls(host, resolved_ip)
    headers = _check_headers(host)

    warnings: list[str] = []
    if not tls["connected"]:
        warnings.append(f"Could not establish a TLS connection: {tls['verify_error']}")
    else:
        if not tls["verified"]:
            warnings.append(f"Certificate chain did not verify: {tls['verify_error']}")
        if tls["expired"]:
            warnings.append("The TLS certificate has expired.")
        elif tls["days_until_expiry"] is not None and tls["days_until_expiry"] < 30:
            warnings.append(f"The TLS certificate expires in {tls['days_until_expiry']} days.")
        if tls["deprecated_protocol"]:
            warnings.append(f"Negotiated a deprecated TLS protocol version ({tls['protocol']}) — TLS 1.0/1.1/SSLv3 are formally deprecated (RFC 8996).")

    missing_headers = [name for name, field in _SECURITY_HEADERS if headers.get(field) is False]
    if headers["reachable"] and missing_headers:
        warnings.append(f"Missing security headers: {', '.join(missing_headers)}.")
    if not headers["reachable"]:
        warnings.append("Could not fetch the site over HTTPS to check security headers.")

    if tls["connected"] and (not tls["verified"] or tls.get("expired")):
        # A real TLS finding takes priority even if it also happens to
        # block the header fetch (an expired/untrusted cert usually
        # causes exactly that) — this is a genuine security issue, not
        # merely "couldn't scan."
        verdict = "critical issues"
    elif not tls["connected"] or not headers["reachable"]:
        verdict = "could not fully scan"
    elif len(warnings) >= 2:
        verdict = "weak configuration"
    elif len(warnings) == 1:
        verdict = "mostly good, one issue"
    else:
        verdict = "strong"

    return {
        "host": host,
        "blocked": False,
        "tls": tls,
        "headers": headers,
        "warnings": warnings,
        "verdict": verdict,
    }


class TlsHeadersScanRequest(BaseModel):
    host: str = Field(..., min_length=1, max_length=253)


@router.post("/check")
def tls_headers_check(req: TlsHeadersScanRequest):
    return run_tls_headers_scan(req.host)
