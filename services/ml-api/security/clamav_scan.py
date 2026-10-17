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


def clamav_scan_bytes(data: bytes, path: str = "", client_ip: str = "") -> list[dict]:
    """Scan `data` with ClamAV over the local clamd TCP socket.

    Returns a one-element blocking-match list (same shape as
    `scan_upload_bytes`'s matches) on a detection, or [] when the file is
    clean, clamd is unavailable/not-yet-ready, or the stream exceeds clamd's
    StreamMaxLength. Never raises — any error is a fail-open [].
    """
    if not _ENABLED or not data:
        return []
    try:
        import clamd  # pure-Python client; imported lazily so the app boots without it

        client = clamd.ClamdNetworkSocket(host=_HOST, port=_PORT, timeout=_TIMEOUT)
        result = client.instream(io.BytesIO(data))
    except Exception:
        # clamd not ready / not installed / unreachable / stream too long → fail open.
        return []

    stream = result.get("stream") if isinstance(result, dict) else None
    status, name = stream if isinstance(stream, tuple) and len(stream) == 2 else ("OK", None)
    if status == "FOUND":
        log_security_event("clamav_detected", path, client_ip, detail=str(name or "unknown"))
        return [{"rule": f"clamav:{name}", "engine": "clamav"}]
    return []
