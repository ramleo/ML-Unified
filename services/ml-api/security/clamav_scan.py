"""ClamAV deep-scan layer for the upload gate — the full-AV complement to YARA.

`file_gate.py` runs a small built-in YARA ruleset as an instant first pass.
This module adds a real antivirus engine — ClamAV, with its full signature
database baked into the image at build time (see the Dockerfile) — as a
second, deeper pass, reached over a local TCP socket to the `clamd` daemon.

Everything here FAILS OPEN. clamd loads its ~1 GB database for 20-30 s after
boot; during that window, or if clamd is not installed / unreachable, or the
stream is larger than clamd's configured StreamMaxLength, this returns no
matches rather than blocking a legitimate upload. A ClamAV *detection* is
authoritative and always blocks; its absence never does. This mirrors
`scan_upload_bytes`'s own fail-open contract so an AV problem can never take
down an upload feature — the worst case is a silent fall-back to YARA-only.
"""
from __future__ import annotations

import io
import os

from security.events import log_security_event

_HOST = os.environ.get("CLAMAV_HOST", "127.0.0.1")
_PORT = int(os.environ.get("CLAMAV_PORT", "3310"))
_TIMEOUT = float(os.environ.get("CLAMAV_TIMEOUT", "30"))
_ENABLED = os.environ.get("CLAMAV_ENABLED", "1") != "0"


def clamav_scan(data: bytes, path: str = "", client_ip: str = "") -> tuple[bool, list[dict]]:
    """Scan `data` with ClamAV, distinguishing "the daemon ran a scan" from "the
    daemon is not available yet". Returns `(scanned, matches)`:

    - `scanned=False` → clamd is unreachable / not installed / still warming up
      (it loads its ~1 GB DB for 20-30 s after boot) / scanning is disabled. The
      caller should fall back to YARA alone. `matches` is [].
    - `scanned=True`  → clamd was reachable and produced a verdict, so ClamAV is
      now ENFORCED: a detection OR a scan failure while reachable both return a
      blocking match. A clean verdict returns `(True, [])`.

    Reachability is decided by a `ping()` first, which is what separates the
    warmup window (fail open) from a ready daemon (fail closed). Never raises.
    """
    if not _ENABLED or not data:
        return (False, [])
    try:
        import clamd  # pure-Python client; imported lazily so the app boots without it

        client = clamd.ClamdNetworkSocket(host=_HOST, port=_PORT, timeout=_TIMEOUT)
        client.ping()  # reachability gate: warmup/unreachable raises here → not scanned
    except Exception:
        return (False, [])

    # clamd is ready — from here a missing clean verdict must BLOCK (fail closed).
    try:
        result = client.instream(io.BytesIO(data))
    except Exception:
        log_security_event("clamav_scan_error", path, client_ip, detail="scan failed while clamd reachable")
        return (True, [{"rule": "clamav:scan-error", "engine": "clamav"}])

    stream = result.get("stream") if isinstance(result, dict) else None
    status, name = stream if isinstance(stream, tuple) and len(stream) == 2 else ("OK", None)
    if status == "FOUND":
        log_security_event("clamav_detected", path, client_ip, detail=str(name or "unknown"))
        return (True, [{"rule": f"clamav:{name}", "engine": "clamav"}])
    return (True, [])


def clamav_scan_bytes(data: bytes, path: str = "", client_ip: str = "") -> list[dict]:
    """Fail-open wrapper around `clamav_scan` for advisory callers: returns only
    the match list, with an unreachable daemon treated as no matches. The gate
    (`gate_or_raise`) uses `clamav_scan` directly so it can enforce once ready."""
    _scanned, matches = clamav_scan(data, path=path, client_ip=client_ip)
    return matches


def clamav_status() -> dict:
    """Live health probe for /health — pings clamd and reports its version string,
    which includes the loaded signature-DB revision (e.g. "ClamAV 1.4.3/27456/...").
    `reachable: true` with a version is positive proof the daemon is up and the DB
    loaded; `reachable: false` means the gate is currently falling open to YARA.
    Never raises.
    """
    if not _ENABLED:
        return {"enabled": False, "reachable": False}
    try:
        import clamd

        client = clamd.ClamdNetworkSocket(host=_HOST, port=_PORT, timeout=5)
        return {"enabled": True, "reachable": True, "version": client.version()}
    except Exception as exc:
        return {"enabled": True, "reachable": False, "error": type(exc).__name__}
