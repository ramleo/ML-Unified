"""
Attack-Surface / Exposed-Path Scanner — cybersecurity deeper-triage pick.

Real, well-precedented recon technique: checking a domain for common
misconfiguration tells. Entirely passive — GET/HEAD requests and plain TCP
connects only, never active exploitation. Same "live network check,
honest findings list, never a fabricated score" pattern as
email_auth_check.py / tls_headers_check.py.

Four independent checks:
1. Exposed sensitive paths (.git/.env/.DS_Store/etc.) — only flagged when
   the response content actually looks like the real file, not just a 200
   status (many sites 200 every path with a custom error page).
2. Directory listing (Apache/nginx autoindex tell).
3. Passive CMS fingerprinting via the standard <meta name="generator">
   tag — never guesses a CMS/version that isn't actually declared.
4. Common open ports — plain TCP connect only, no banner grab, no
   protocol interaction.

SSRF-hardened via routers/security_shared.py, same as tls_headers_check.py
— this tool has the identical risk profile (opens real sockets to a
user-supplied host).
"""

import logging
import re
import socket
from concurrent.futures import ThreadPoolExecutor

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from routers.security_shared import normalize_host, resolve_public_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attack-surface")

_CONNECT_TIMEOUT = 5.0

_SENSITIVE_PATHS: list[tuple[str, re.Pattern]] = [
    ("/.git/HEAD", re.compile(r"ref:\s*refs/")),
    ("/.git/config", re.compile(r"\[core\]")),
    ("/.env", re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*=", re.MULTILINE)),
    ("/.DS_Store", re.compile(r"Bud1")),  # real DS_Store magic bytes
    ("/.svn/entries", re.compile(r"^\d+$", re.MULTILINE)),
    ("/backup.zip", re.compile(r"^PK")),  # real ZIP magic bytes
    ("/.aws/credentials", re.compile(r"\[default\]|aws_access_key_id")),
]

_LISTING_DIRS = ["/uploads/", "/backup/", "/images/", "/files/"]
_LISTING_TELL = re.compile(r"<title>\s*index of", re.IGNORECASE)

_GENERATOR_META = re.compile(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE)

_COMMON_PORTS = [
    (21, "FTP"), (22, "SSH"), (23, "Telnet"), (25, "SMTP"),
    (3306, "MySQL"), (5432, "PostgreSQL"), (6379, "Redis"), (27017, "MongoDB"),
]


def _check_sensitive_paths(host: str) -> list[dict]:
    found = []
    with httpx.Client(timeout=_CONNECT_TIMEOUT, follow_redirects=False) as client:
        for path, content_pattern in _SENSITIVE_PATHS:
            try:
                resp = client.get(f"https://{host}{path}")
                if resp.status_code != 200:
                    continue
                if content_pattern.search(resp.text):
                    found.append({"path": path, "status_code": resp.status_code})
            except (httpx.HTTPError, UnicodeDecodeError):
                continue
    return found


def _check_directory_listing(host: str) -> list[str]:
    found = []
    with httpx.Client(timeout=_CONNECT_TIMEOUT, follow_redirects=False) as client:
        for path in _LISTING_DIRS:
            try:
                resp = client.get(f"https://{host}{path}")
                if resp.status_code == 200 and _LISTING_TELL.search(resp.text):
                    found.append(path)
            except httpx.HTTPError:
                continue
    return found


def _check_cms_fingerprint(host: str) -> dict | None:
    try:
        # follow_redirects=False (E20): the host was checked public by
        # resolve_public_ip, but a redirect could bounce us to an internal
        # address that check never saw. The generator meta tag lives on the
        # landing page, so a redirect is not needed to find it — matches the
        # other two checks here, which already refuse to follow redirects.
        resp = httpx.get(f"https://{host}", timeout=_CONNECT_TIMEOUT, follow_redirects=False)
        match = _GENERATOR_META.search(resp.text)
        if match:
            return {"generator": match.group(1)}
    except httpx.HTTPError:
        pass
    return None


def _check_one_port(resolved_ip: str, port: int, name: str) -> dict:
    try:
        with socket.create_connection((resolved_ip, port), timeout=2.0):
            return {"port": port, "service": name, "open": True}
    except (socket.timeout, ConnectionRefusedError, OSError):
        return {"port": port, "service": name, "open": False}


def _check_open_ports(resolved_ip: str) -> list[dict]:
    """Runs all port checks concurrently — sequential would take up to
    2s * len(_COMMON_PORTS) when a firewall silently drops (rather than
    actively refuses) a probe, which measured ~18s total for this check
    alone during real testing against a live host."""
    with ThreadPoolExecutor(max_workers=len(_COMMON_PORTS)) as pool:
        results = list(pool.map(lambda pn: _check_one_port(resolved_ip, pn[0], pn[1]), _COMMON_PORTS))
    return sorted(results, key=lambda r: r["port"])


def run_attack_surface_scan(raw_host: str) -> dict:
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

    exposed_paths = _check_sensitive_paths(host)
    directory_listings = _check_directory_listing(host)
    cms = _check_cms_fingerprint(host)
    open_ports = _check_open_ports(resolved_ip)
    open_port_list = [p for p in open_ports if p["open"]]

    findings: list[str] = []
    if exposed_paths:
        findings.append(f"Exposed sensitive path(s): {', '.join(p['path'] for p in exposed_paths)}.")
    if directory_listings:
        findings.append(f"Directory listing enabled at: {', '.join(directory_listings)}.")
    if open_port_list:
        port_descriptions = [f"{p['port']} ({p['service']})" for p in open_port_list]
        findings.append(f"Common service port(s) open: {', '.join(port_descriptions)}.")

    return {
        "host": host,
        "blocked": False,
        "exposed_paths": exposed_paths,
        "directory_listings": directory_listings,
        "cms": cms,
        "open_ports": open_ports,
        "findings": findings,
    }


class AttackSurfaceScanRequest(BaseModel):
    host: str = Field(..., min_length=1, max_length=253)


@router.post("/scan")
def attack_surface_scan(req: AttackSurfaceScanRequest):
    return run_attack_surface_scan(req.host)
