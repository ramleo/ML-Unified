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

from routers.yara_scan import ADVISORY_RULES, _get_builtin_rules, _run_match
from security.events import log_security_event


def scan_upload_bytes(data: bytes, path: str = "", client_ip: str = "") -> list[dict]:
    """Returns the list of matched-rule dicts (empty if clean) — same shape
    as yara_scan.py's own `/yara-scan/builtin` response's "matches" field.
    Never raises on a scan failure; a broken rule set should not take down
    an unrelated upload feature, so this fails open (returns no matches)
    rather than blocking legitimate use if YARA itself has a problem."""
    try:
        rules = _get_builtin_rules()
        matches = _run_match(rules, data)
    except Exception:
        return []
    if matches:
        log_security_event(
            "file_gate_flagged", path, client_ip,
            detail=", ".join(m["rule"] for m in matches),
        )
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
