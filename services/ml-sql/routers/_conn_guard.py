"""Refuse /sql/connect targets that are not a public database host (E14).

/sql/connect makes this Space open a connection to whatever the caller names.
Left open, that lets anyone use the Space to reach addresses only it can
reach — its own loopback services, the platform's private network, cloud
metadata at 169.254.169.254 — and to probe which ports answer. A visitor's
real database is always on a public address, so everything else is refused.

Checked before connecting:
  - scheme matches the chosen database type;
  - exactly one explicit host (no multi-host lists, no `?host=` override —
    asyncpg reads that, and it also accepts a Unix socket path there);
  - every address the host resolves to is globally routable.

Known gap, accepted: DNS can answer differently between this check and the
driver's own lookup (rebinding). Connecting to the checked IP instead would
break TLS SNI, which managed Postgres hosts (Neon, Supabase) route on, so the
check resolves and trusts the answer. The per-IP limit in _guard.py bounds
how fast anyone could try.
"""
from __future__ import annotations

import asyncio
import ipaddress
from urllib.parse import parse_qs, urlparse

# First entry is the one named in the error message (matches the UI example).
_SCHEMES = {
    "postgresql": ("postgresql", "postgres"),
    "mysql": ("mysql",),
    "mssql": ("mssql", "sqlserver"),
}


class UnsafeTarget(ValueError):
    pass


def _is_public(ip: str) -> bool:
    addr = ipaddress.ip_address(ip.split("%", 1)[0])
    # Python 3.11 does not unwrap IPv4-mapped IPv6 (::ffff:127.0.0.1) itself.
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


async def check_connect_target(conn_str: str, db_type: str) -> None:
    p = urlparse(conn_str.strip())
    allowed = _SCHEMES.get(db_type, _SCHEMES["postgresql"])
    if p.scheme.lower() not in allowed:
        raise UnsafeTarget(f"Connection string must start with {allowed[0]}://")
    if "," in p.netloc:
        raise UnsafeTarget("Only one database host is allowed.")
    if any(k.lower() in ("host", "hostaddr") for k in parse_qs(p.query)):
        raise UnsafeTarget("Set the host in the address, not as a query parameter.")
    host = p.hostname
    if not host:
        raise UnsafeTarget("The connection string needs a host name.")
    try:
        _ = p.port  # raises on a malformed port
    except ValueError:
        raise UnsafeTarget("Invalid port.") from None

    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None)
    except OSError:
        raise UnsafeTarget(f"Could not resolve host {host!r}.") from None
    ips = {info[4][0] for info in infos}
    if not ips or not all(_is_public(ip) for ip in ips):
        raise UnsafeTarget("That host is not a public address, so it cannot be connected to from here.")
