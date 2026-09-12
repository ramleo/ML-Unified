"""Property assertions for model output.

Exact string equality is the wrong test for a language model. A correct
extraction of a total of 1180.00 can arrive as "1180", "1,180.00",
"$1,180.00" or "USD 1180.00", and all four are right. A test that demands
one spelling fails on correct answers, which trains people to ignore it.

So each expected value declares HOW it should be compared, and the
comparison is a property of the value rather than of its formatting:

    amount   parse both to a number, agree within a cent
    date     parse both to a calendar date, agree exactly
    text     normalise case and whitespace, one contains the other

`text` containment is deliberately loose in both directions. A model
asked for a vendor may return "Northwind Trading" or "Northwind Trading
Ltd." — neither is wrong, and picking one as canonical would be a
judgement about phrasing, not about correctness.
"""
from __future__ import annotations

import re
from datetime import datetime

_AMOUNT_RE = re.compile(r"-?[\d,]+(?:\.\d{1,2})?")
_DATE_FORMATS = (
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y",
    "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y",
)


def as_amount(value: str) -> float | None:
    match = _AMOUNT_RE.search(str(value).replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def as_date(value: str):
    text = str(value).strip().rstrip(".")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _norm_text(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", str(value).lower())


def _squash(value: str) -> str:
    return " ".join(_norm_text(value).split())


def matches(kind: str, expected: str, actual: str) -> tuple[bool, str]:
    """Returns (passed, a short human reason). The reason is what a person
    reads at 3am, so it names both values rather than saying "mismatch"."""
    if actual is None or not str(actual).strip():
        return False, f"expected {expected!r}, got nothing"

    if kind == "amount":
        want, got = as_amount(expected), as_amount(actual)
        if got is None:
            return False, f"expected the number {expected!r}, got {actual!r}"
        if want is not None and abs(want - got) <= 0.011:
            return True, ""
        return False, f"expected {want}, got {got} (from {actual!r})"

    if kind == "date":
        want, got = as_date(expected), as_date(actual)
        if got is None:
            return False, f"expected the date {expected!r}, got {actual!r} which does not parse"
        if want == got:
            return True, ""
        return False, f"expected {want}, got {got}"

    want, got = _squash(expected), _squash(actual)
    if not want or not got:
        return False, f"expected {expected!r}, got {actual!r}"
    if want in got or got in want:
        return True, ""
    return False, f"expected something like {expected!r}, got {actual!r}"


def flagged(field: dict) -> bool:
    return (field.get("validation") or {}).get("status") == "flagged"
