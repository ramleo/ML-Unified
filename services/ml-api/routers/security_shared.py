"""
Shared SSRF-guard helpers for live-network security tools that open a
real socket to a user-supplied host (tls_headers_check.py,
attack_surface_check.py) — unlike email_auth_check.py, which only does
DNS TXT lookups. Extracted here rather than duplicated so this
security-critical logic has exactly one implementation to review/fix.
"""

import ipaddress
import socket


def normalize_host(raw: str) -> str:
    host = raw.strip().lower()
    host = host.split("://", 1)[-1]
    host = host.split("/", 1)[0]
    host = host.split(":", 1)[0]
    return host


def resolve_public_ip(host: str) -> str | None:
    """Resolves the hostname and returns the first public IP found, or
    None if resolution fails or every resolved address is private/
    internal — the caller must refuse to connect in that case. Prevents
    these tools being used to port-scan the Space's own internal network
    or hit cloud metadata endpoints (169.254.169.254, etc.)."""
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return None
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            continue
        return ip_str
    return None
