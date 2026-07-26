"""Domain-specific structured entity extraction (MMRAG-03) — pulls out
money amounts, dates, and percentages from a chunk's own text at ingest
time, the same way pii.py flags PII categories: cheap regex, computed once
per chunk, never a per-query LLM call.

Deliberately scoped to entities regex can extract reliably — money/date/
percent show up prominently in exactly the document types this tool
targets (invoices, resumes, contracts, reports). Person/organization names
are NOT attempted here: a regex heuristic for those (e.g. capitalized word
sequences) produces too many false positives on section headers and titles
to be worth shipping — a real accuracy/cost tradeoff, not an oversight.
"""
from __future__ import annotations

import json
import re
from typing import Optional

_MONEY_RE = re.compile(
    r"[$€£¥]\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion|k|M|B))?"
    r"|\b\d[\d,]*(?:\.\d+)?\s?(?:USD|EUR|GBP|dollars)\b",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s?%")
_DATE_RE = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
    r"|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)

# Bounds chunk metadata size — a chunk mentioning many dates/amounts only
# needs to signal "this chunk has these", not catalogue every occurrence.
_MAX_PER_TYPE = 4


def extract_entities(text: str) -> list[dict]:
    """Returns a deduped, order-preserving list of {"type", "value"} — at
    most _MAX_PER_TYPE per type."""
    found: list[dict] = []
    for etype, pattern in (("money", _MONEY_RE), ("date", _DATE_RE), ("percent", _PERCENT_RE)):
        seen: set[str] = set()
        for m in pattern.finditer(text):
            if len(seen) >= _MAX_PER_TYPE:
                break
            value = m.group().strip()
            if value.lower() in seen:
                continue
            seen.add(value.lower())
            found.append({"type": etype, "value": value})
    return found


def encode_entities(entities: list[dict]) -> Optional[str]:
    """JSON-encodes for Chroma-metadata-safe (scalar string) storage —
    mirrors pii_types' comma-join, but entity VALUES (not just category
    names) need to survive the round trip, so a delimited string alone
    isn't enough."""
    return json.dumps(entities) if entities else None


def decode_entities(raw: Optional[str]) -> list[dict]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
