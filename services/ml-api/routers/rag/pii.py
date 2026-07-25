"""PII awareness for user-uploaded documents (resumes, invoices, etc.) — flags
common personally-identifiable patterns on a citation so a user knows a chunk
contains one before sharing/screenshotting it. detect_pii_types() is
detection-only, used for the owner's own view. redact_pii() actually removes
matched text — used only for shared-link viewers (see query.py), never for
the document's own uploader, who already has full access to their document."""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def detect_pii_types(text: str) -> list[str]:
    """Returns which PII categories appear in text, e.g. ["email", "phone"].
    Credit-card matches are Luhn-checked to avoid flagging ordinary
    multi-digit numbers (invoice IDs, phone numbers) as card numbers."""
    types: list[str] = []
    if _EMAIL_RE.search(text):
        types.append("email")
    if _PHONE_RE.search(text):
        types.append("phone")
    if _SSN_RE.search(text):
        types.append("ssn")
    for m in _CARD_RE.finditer(text):
        digits = re.sub(r"[ -]", "", m.group())
        if len(digits) in range(13, 20) and _luhn_valid(digits):
            types.append("credit_card")
            break
    return types


def redact_pii(text: str) -> str:
    """Replace detected PII with a labeled placeholder. Applied only to what
    a shared-link viewer's query sees (both the LLM's context and the
    citation text shown to them) — never to the uploader's own view."""
    text = _EMAIL_RE.sub("[REDACTED EMAIL]", text)
    text = _SSN_RE.sub("[REDACTED SSN]", text)
    text = _PHONE_RE.sub("[REDACTED PHONE]", text)

    def _card_sub(m: re.Match) -> str:
        digits = re.sub(r"[ -]", "", m.group())
        if len(digits) in range(13, 20) and _luhn_valid(digits):
            return "[REDACTED CARD]"
        return m.group()

    return _CARD_RE.sub(_card_sub, text)
