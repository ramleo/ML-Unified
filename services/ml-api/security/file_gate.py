"""
Pre-processing file safety gate — turns the already-shipped YARA scanner
(`routers/yara_scan.py`, previously only reachable as a standalone
user-invoked tool at `/yara-scan/builtin`) into protection actually wired
into other file-accepting routers: scan untrusted uploaded bytes with the
built-in rule set BEFORE running any real ML pipeline on them, the same
"real matched evidence, never a fabricated verdict" pattern the standalone
tool already uses — this module doesn't invent new detection logic, it
reuses `yara_scan.py`'s exact compiled ruleset directly (same precedent as
`mm_face_reid_demo.py` importing `mm_face_cloak.py`'s private helpers
rather than duplicating them).

This is deliberately a WARNING/advisory gate, not a hard block: a false
positive here (e.g. a legitimate file that happens to match a broad
heuristic like the entropy rule) would otherwise break a real user's
normal use of the tool it's wired into, which is worse than surfacing a
flag for the router to decide what to do with. Each wired-in router
chooses whether to reject or just log-and-continue.

Swap-in point for later: replace this module's internals with a call to a
paid scanning API (VirusTotal, ClamAV cloud) instead of local
`yara-python` — the `scan_upload_bytes()` signature and return shape stay
identical, so no router that calls it needs to change.
"""
from __future__ import annotations

from fastapi import HTTPException

from routers.yara_scan import ADVISORY_RULES, _get_builtin_rules, _run_match
from security.clamav_scan import clamav_scan
from security.events import log_security_event


def _yara_scan(data: bytes, path: str = "", client_ip: str = "") -> tuple[bool, list[dict]]:
    """Run the built-in YARA ruleset, distinguishing "the engine ran" from "the
    engine could not run at all". Returns `(ran, matches)`: `ran=False` means
    YARA itself failed (missing binding, broken ruleset) and produced no verdict;
    `ran=True` means it executed and `matches` is authoritative (possibly empty).
    Logs a flag event when it finds something. Never raises."""
    try:
        rules = _get_builtin_rules()
        matches = _run_match(rules, data)
    except Exception:
        return (False, [])
    if matches:
        log_security_event(
            "file_gate_flagged", path, client_ip,
            detail=", ".join(m["rule"] for m in matches),
        )
    return (True, matches)


def scan_upload_bytes(data: bytes, path: str = "", client_ip: str = "") -> list[dict]:
    """Returns the list of matched-rule dicts (empty if clean) — same shape
    as yara_scan.py's own `/yara-scan/builtin` response's "matches" field.
    Never raises on a scan failure; a broken rule set should not take down
    an unrelated upload feature, so this fails open (returns no matches)
    rather than blocking legitimate use if YARA itself has a problem. This is
    the ADVISORY path (e.g. the malware-in-image analyser); the blocking gate
    `gate_or_raise` uses `_yara_scan` directly so it can fail CLOSED instead."""
    _ran, matches = _yara_scan(data, path=path, client_ip=client_ip)
    return matches


def blocking_matches(matches: list[dict]) -> list[dict]:
    """The subset of `scan_upload_bytes()`'s matches that actually justify
    refusing a file: evidence of intent (EICAR, an embedded PE, a webshell),
    not a property every compressed file shares.

    This exists because /rag/mm-ingest treated a bare entropy match as a
    verdict and so rejected every real PDF, image, video and audio file it was
    ever given — the whole input of the Multimodal RAG tool. A caller that
    blocks should ask this function, not test `matches` for truthiness.
    """
    return [m for m in matches if m["rule"] not in ADVISORY_RULES]


def gate_or_raise(data: bytes, path: str = "", client_ip: str = "") -> None:
    """The blocking gate: scan `data` and REJECT it with HTTP 400 if it matches a
    real-threat rule (EICAR, embedded PE, a webshell). Advisory-only matches
    (entropy and other broad heuristics) are logged by `scan_upload_bytes` but
    never block, so legitimate PDFs/images/CSVs/audio/video are unaffected — this
    is `blocking_matches`' guarantee. Call this at every upload boundary that
    should PREVENT a malicious file, not merely record it. The one exception is a
    tool whose whole purpose is to analyse a possibly-malicious sample (e.g. the
    malware-in-image detector) — that keeps calling `scan_upload_bytes` directly.

    The rejection message is deliberately generic (no matched-rule names) so it
    can't be used to tune a payload past the scanner.

    Two engines run as a hybrid:

    1. **YARA — mandatory (fail CLOSED).** It runs in-process with no daemon, so a
       failure to run is a real fault, not a transient one. If YARA cannot execute,
       the upload is refused with 503 rather than waved through unscanned — every
       upload is guaranteed at least this baseline scan.
    2. **ClamAV — enforced once ready.** While the clamd daemon is still warming up
       (it loads its ~1 GB DB for 20-30 s after boot) it is unreachable and the gate
       proceeds on YARA alone; once clamd is reachable, a clean verdict is required
       (a detection OR a scan failure both block). See `clamav_scan.py`.

    Either engine's blocking hit rejects the file with 400.
    """
    # 1) YARA — mandatory. No verdict → refuse (fail closed).
    yara_ran, yara_matches = _yara_scan(data, path=path, client_ip=client_ip)
    if not yara_ran:
        log_security_event("file_gate_unavailable", path, client_ip, detail="yara_unavailable")
        raise HTTPException(
            status_code=503,
            detail="Upload temporarily unavailable: the safety scan could not run. Please retry.",
        )
    blocked = blocking_matches(yara_matches)

    # 2) ClamAV — enforced only once the daemon is reachable; warmup falls through.
    clam_scanned, clam_matches = clamav_scan(data, path=path, client_ip=client_ip)
    if clam_scanned:
        blocked += clam_matches

    if blocked:
        raise HTTPException(status_code=400, detail="File rejected: it failed a malware safety scan.")
