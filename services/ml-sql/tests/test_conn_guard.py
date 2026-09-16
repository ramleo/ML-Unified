"""E14 regression: /sql/connect refuses any target that is not a public host.

Left open, /sql/connect let a caller point this Space at addresses only it can
reach — its own loopback, the platform's private network, cloud metadata at
169.254.169.254 — and probe ports. `check_connect_target` refuses anything
whose scheme is wrong, whose host is missing/ambiguous, or that resolves to a
non-global address. Live, the metadata target used to hang 20s (the old code
really reaching 169.254.169.254); this pins the refusals so a regression is
caught before it ships.

DNS is mocked so the suite is hermetic and offline: literal IPs resolve to
themselves, and a small map controls what the few hostnames resolve to. The
module reaches the resolver through `asyncio.get_running_loop().getaddrinfo`,
so a shim over just that call keeps the real event loop untouched.
"""
from __future__ import annotations

import asyncio
import ipaddress

import pytest
import routers._conn_guard as cg
from routers._conn_guard import UnsafeTarget, check_connect_target


def _make_resolver(mapping):
    def resolve(host):
        bare = host.split("%", 1)[0]
        try:
            ipaddress.ip_address(bare)
            return [bare]  # a literal IP resolves to itself, no DNS
        except ValueError:
            pass
        if host in mapping:
            return mapping[host]
        raise OSError(f"cannot resolve {host!r}")
    return resolve


def _run(monkeypatch, conn_str, db_type, mapping):
    resolve = _make_resolver(mapping)

    class _FakeLoop:
        async def getaddrinfo(self, host, port):
            ips = resolve(host)  # raises OSError → UnsafeTarget, like the real call
            return [(0, 0, 0, "", (ip, 0)) for ip in ips]

    class _ShimAsyncio:
        # Only get_running_loop is used at runtime; leave the global asyncio alone.
        get_running_loop = staticmethod(lambda: _FakeLoop())

    monkeypatch.setattr(cg, "asyncio", _ShimAsyncio)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(check_connect_target(conn_str, db_type))
    finally:
        loop.close()


# Each entry: (id, conn_str, db_type, dns_map). All must be refused.
_REFUSED = [
    ("loopback name",        "postgresql://localhost:5432/db",        "postgresql", {"localhost": ["127.0.0.1"]}),
    ("loopback v4",          "postgresql://127.0.0.1:5432/db",        "postgresql", {}),
    ("loopback v6",          "postgresql://[::1]:5432/db",            "postgresql", {}),
    ("ipv4-mapped v6",       "postgresql://[::ffff:127.0.0.1]/db",    "postgresql", {}),
    ("cloud metadata",       "postgresql://169.254.169.254/db",       "postgresql", {}),
    ("private 10/8",         "postgresql://10.0.0.1/db",              "postgresql", {}),
    ("private 192.168/16",   "postgresql://192.168.1.1/db",           "postgresql", {}),
    ("cgnat 100.64/10",      "postgresql://100.64.0.1/db",            "postgresql", {}),
    ("unspecified 0.0.0.0",  "postgresql://0.0.0.0/db",               "postgresql", {}),
    ("decimal-encoded lo",   "postgresql://2130706433/db",            "postgresql", {"2130706433": ["127.0.0.1"]}),
    ("public name → lo",     "postgresql://sneaky.example.com/db",    "postgresql", {"sneaky.example.com": ["127.0.0.1"]}),
    ("multi-host list",      "postgresql://h1,h2:5432/db",            "postgresql", {"h1": ["1.2.3.4"], "h2": ["5.6.7.8"]}),
    ("?host= socket",        "postgresql://real.example.com/db?host=/tmp", "postgresql", {"real.example.com": ["1.2.3.4"]}),
    ("no host",              "postgresql:///db",                      "postgresql", {}),
    ("wrong scheme",         "http://example.com/db",                 "postgresql", {"example.com": ["93.184.216.34"]}),
    ("mysql scheme on pg",   "mysql://example.com/db",                "postgresql", {"example.com": ["93.184.216.34"]}),
    ("malformed port",       "postgresql://example.com:notaport/db",  "postgresql", {"example.com": ["93.184.216.34"]}),
    ("unresolvable host",    "postgresql://nope.invalid/db",          "postgresql", {}),
]


@pytest.mark.parametrize("conn_str,db_type,dns_map", [c[1:] for c in _REFUSED], ids=[c[0] for c in _REFUSED])
def test_unsafe_targets_are_refused(monkeypatch, conn_str, db_type, dns_map):
    with pytest.raises(UnsafeTarget):
        _run(monkeypatch, conn_str, db_type, dns_map)


# Each entry: (id, conn_str, db_type, dns_map). All must be allowed (no raise).
_ALLOWED = [
    ("public postgres",   "postgresql://example.com:5432/db",                        "postgresql", {"example.com": ["93.184.216.34"]}),
    ("postgres alias",    "postgres://example.com/db",                               "postgresql", {"example.com": ["93.184.216.34"]}),
    ("supabase pooler",   "postgresql://aws-0-us-east-1.pooler.supabase.com/postgres", "postgresql", {"aws-0-us-east-1.pooler.supabase.com": ["1.2.3.4"]}),
    ("public mysql",      "mysql://db.example.com:3306/app",                         "mysql",      {"db.example.com": ["8.8.8.8"]}),
    ("public mssql",      "mssql://db.example.com/app",                              "mssql",      {"db.example.com": ["8.8.8.8"]}),
    ("sqlserver alias",   "sqlserver://db.example.com/app",                          "mssql",      {"db.example.com": ["8.8.8.8"]}),
]


@pytest.mark.parametrize("conn_str,db_type,dns_map", [c[1:] for c in _ALLOWED], ids=[c[0] for c in _ALLOWED])
def test_public_targets_are_allowed(monkeypatch, conn_str, db_type, dns_map):
    _run(monkeypatch, conn_str, db_type, dns_map)  # must not raise


def test_a_host_with_one_public_and_one_private_address_is_refused(monkeypatch):
    """DNS returning several addresses is only safe if every one is public —
    a single private answer must sink it, or a split-horizon name slips through."""
    with pytest.raises(UnsafeTarget):
        _run(monkeypatch, "postgresql://mixed.example.com/db", "postgresql",
             {"mixed.example.com": ["93.184.216.34", "127.0.0.1"]})
