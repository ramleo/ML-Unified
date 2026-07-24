"""PII awareness for user-uploaded documents (resumes, invoices, etc.) — flags
common personally-identifiable patterns on a citation so a user knows a chunk
contains one before sharing/screenshotting it. Detection only: nothing is
masked or stripped from the stored text or the LLM's context, since the
uploader already has (and needs) full access to their own document."""
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
