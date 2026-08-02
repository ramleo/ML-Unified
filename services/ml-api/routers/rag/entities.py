"""Domain-specific structured entity extraction (MMRAG-03/MMRAG-26) — pulls
out money amounts, dates, percentages, and named entities from a chunk's own
text at ingest time, the same way pii.py flags PII categories: computed once
per chunk, never a per-query LLM call.

Money/date/percent stay regex-based (cheap, reliable, no reason to replace).
Person/organization/location were originally left out because a regex
heuristic (capitalized word sequences) produced too many false positives on
section headers and titles — that reasoning doesn't apply to a real NER
model, so MMRAG-26 adds a small local spaCy pass (en_core_web_sm) for those
three types: no API calls, no per-use cost, one-time model download baked
into the Docker image at build time (see Dockerfile).
"""
from __future__ import annotations

import json
import logging
import re
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_nlp = None
_load_error: Optional[str] = None
_lock = threading.Lock()

_SPACY_LABEL_MAP = {"PERSON": "person", "ORG": "org", "GPE": "location", "LOC": "location"}


def _ensure_loaded() -> bool:
    """Lazy-load spaCy on first use — only the NER component is needed, so
    the parser/lemmatizer pipes are disabled for speed."""
    global _nlp, _load_error
    if _nlp is not None:
        return True
    with _lock:
        if _nlp is not None:
            return True
        try:
            import spacy

            _nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
            return True
        except Exception as exc:
            logger.warning("spaCy load failed — named-entity extraction disabled: %s", exc)
            _load_error = str(exc)
            return False

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
    r"|\b\d{4}-\d{2}-\d{2}\b"
    # relative payment/date terms ("net-30", "30 days", "45 days from issue") —
    # calendar dates alone miss the exact term-mismatch phrasing contracts and
    # invoices actually use (MMRAG-20 follow-up: entity-based candidate
    # prioritization was blind to these, only ever matching on money).
    r"|\bnet[\s-]?\d{1,3}\b"
    r"|\b\d{1,3}\s?-?\s?days?\b",
    re.IGNORECASE,
)

# Bounds chunk metadata size — a chunk mentioning many dates/amounts only
# needs to signal "this chunk has these", not catalogue every occurrence.
_MAX_PER_TYPE = 4


def extract_entities(text: str) -> list[dict]:
    """Returns a deduped, order-preserving list of {"type", "value"} — at
    most _MAX_PER_TYPE per type. Regex types (money/date/percent) always
    run; person/org/location additionally run through spaCy NER when the
    model is available — best-effort, silently skipped if spaCy failed to
    load (same "never blocks the main path" contract as this module's other
    optional-resource siblings, e.g. mm_similar.py's CLIP loader)."""
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

    if _ensure_loaded():
        seen_by_type: dict[str, set[str]] = {}
        try:
            for ent in _nlp(text[:5000]).ents:  # cap input length — chunk text is already short
                etype = _SPACY_LABEL_MAP.get(ent.label_)
                if not etype:
                    continue
                seen = seen_by_type.setdefault(etype, set())
                if len(seen) >= _MAX_PER_TYPE:
                    continue
                value = ent.text.strip()
                if not value or value.lower() in seen:
                    continue
                seen.add(value.lower())
                found.append({"type": etype, "value": value})
        except Exception as exc:
            logger.warning("spaCy NER pass failed on a chunk — skipping: %s", exc)

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


ENTITY_TYPES = ("money", "date", "percent", "person", "org", "location")


def entity_type_flags(entities: list[dict]) -> dict[str, bool]:
    """Scalar has_<type> booleans for the types actually present — Chroma
    metadata must be scalar, so the JSON entity list itself can't be
    filtered on directly. Only set (True) for types that occur; a type
    with no match simply has no key, the same "absent means doesn't
    match" convention chunk_type_filter already relies on, rather than
    every chunk needing an explicit has_money: False stored everywhere."""
    present = {e["type"] for e in entities}
    return {f"has_{t}": True for t in ENTITY_TYPES if t in present}
