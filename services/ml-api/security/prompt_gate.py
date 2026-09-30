"""Prompt-injection detection for INGESTED document text (indirect injection) —
FLAG + LOG, never block (per the agreed design: a legitimate document can contain
phrasing like "ignore previous instructions", so rejecting on a heuristic would
break real use). The defensive value here is visibility: a flagged document is
recorded and surfaced, and its text should be treated as data by the LLM.

Reuses the heuristic layer of the standalone tool
(`routers/prompt_injection_check.detect_heuristics`) — the same "reuse, don't
duplicate" pattern as `security/file_gate` reusing `routers/yara_scan`. Only the
STRONG categories (direct_override, jailbreak) count as a flag; the weaker
indirect/other patterns are too noisy to raise automatically on arbitrary
document text. The LLM-judge layer is deliberately NOT run here — it would add an
LLM call, latency and budget pressure to every ingest; this is the free, instant
pattern layer only.

Content-free: logs the matched categories and a count, never the matched text or
any document content.
"""
from __future__ import annotations

from security.events import log_security_event

_STRONG = {"direct_override", "jailbreak"}
_MAX_SCAN_CHARS = 100_000  # bound regex cost on very large documents


def scan_text_for_injection(text: str, path: str = "", client_ip: str = "") -> dict | None:
    """Scan extracted document text for strong prompt-injection patterns.

    Returns a small, content-free warning dict if any strong pattern matched
    (and logs a `prompt_injection_flagged` security event), else None. Never
    raises — a detector problem must never break ingestion.
    """
    if not text:
        return None
    try:
        from routers.prompt_injection_check import detect_heuristics
        hits = [h for h in detect_heuristics(text[:_MAX_SCAN_CHARS]) if h.category in _STRONG]
    except Exception:
        return None
    if not hits:
        return None
    categories = sorted({h.category for h in hits})
    log_security_event(
        "prompt_injection_flagged", path, client_ip,
        detail=f"{','.join(categories)} x{len(hits)}",
    )
    return {
        "prompt_injection_suspected": True,
        "categories": categories,
        "count": len(hits),
        "note": ("This document contains text that resembles instructions to an AI "
                 "assistant. It was processed as data — review the source if unexpected."),
    }
