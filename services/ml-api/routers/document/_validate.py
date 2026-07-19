"""Agentic self-correction loop for document field extraction.

Two-pass validation:
  1. Rule-based checks (regex, format, presence) — free, instant
  2. LLM consistency check — cross-field logic (totals, date order, etc.)

Validation result is attached to each field as:
  {"status": "ok"|"corrected"|"flagged"|"low_confidence", "note": "..."}
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Patterns ──────────────────────────────────────────────────────────────────

_DATE_PATTERNS = [
    r"\d{4}-\d{2}-\d{2}",
    r"\d{2}/\d{2}/\d{4}",
    r"\d{2}-\d{2}-\d{4}",
    r"\d{1,2}\s+\w+\s+\d{4}",
    r"\w+\s+\d{1,2},?\s+\d{4}",
]
_DATE_RE = re.compile("|".join(_DATE_PATTERNS), re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"[\d\s\-\+\(\)]{7,}")
_AMOUNT_RE = re.compile(r"[\d,]+(?:\.\d{1,2})?")

_DATE_NAMES = {"date", "dob", "issue_date", "expiry_date", "effective_date",
               "termination_date", "delivery_date", "period", "transaction_date"}
_EMAIL_NAMES = {"email", "contact_email", "email_address"}
_PHONE_NAMES = {"phone", "mobile", "telephone", "contact_phone"}
_AMOUNT_NAMES = {"total", "subtotal", "tax", "amount", "balance",
                 "opening_balance", "closing_balance", "grand_total"}


def _parse_amount(s: str) -> float | None:
    """Extract first numeric amount from a string."""
    s = s.replace(",", "").strip()
    m = _AMOUNT_RE.search(s)
    if m:
        try:
            return float(m.group())
        except ValueError:
            pass
    return None


# ── Rule-based checks ─────────────────────────────────────────────────────────

def _rule_check(field: dict) -> dict | None:
    """Return validation dict if rule check finds an issue, else None."""
    name = field.get("name", "")
    value = str(field.get("value", "")).strip()
    confidence = float(field.get("confidence", 1.0))

    if confidence < 0.55:
        return {"status": "low_confidence", "note": f"Confidence {confidence:.0%} — manual review recommended"}

    # Date format check
    if any(d in name for d in _DATE_NAMES) or "date" in name:
        if value and not _DATE_RE.search(value):
            return {"status": "flagged", "note": f"Value '{value}' does not look like a recognisable date"}

    # Email format check
    if name in _EMAIL_NAMES or "email" in name:
        if value and not _EMAIL_RE.match(value):
            return {"status": "flagged", "note": f"'{value}' does not appear to be a valid email address"}

    # Phone format check
    if name in _PHONE_NAMES or "phone" in name or "mobile" in name:
        digits = re.sub(r"\D", "", value)
        if value and len(digits) < 7:
            return {"status": "flagged", "note": f"Phone '{value}' has fewer than 7 digits"}

    return None


def _check_invoice_totals(fields: list[dict]) -> dict[str, dict]:
    """For invoices: verify total ≈ subtotal + tax."""
    by_name = {f["name"]: f for f in fields}
    issues: dict[str, dict] = {}

    subtotal_f = by_name.get("subtotal")
    tax_f = by_name.get("tax_amount") or by_name.get("tax") or by_name.get("vat")
    total_f = by_name.get("total") or by_name.get("grand_total") or by_name.get("total_amount")

    if subtotal_f and total_f:
        sub = _parse_amount(subtotal_f["value"])
        tot = _parse_amount(total_f["value"])
        tax = _parse_amount(tax_f["value"]) if tax_f else 0.0
        if sub is not None and tot is not None:
            expected = sub + (tax or 0.0)
            if abs(expected - tot) > 0.02 * max(tot, 1):
                note = (f"Total {tot} ≠ subtotal {sub}"
                        + (f" + tax {tax}" if tax else "")
                        + f" = {expected:.2f}")
                issues[total_f["name"]] = {"status": "flagged", "note": note}

    return issues


def _check_balance_equation(fields: list[dict]) -> dict[str, dict]:
    """For bank statements: closing ≈ opening + credits − debits."""
    by_name = {f["name"]: f for f in fields}
    issues: dict[str, dict] = {}

    opening = by_name.get("opening_balance")
    closing = by_name.get("closing_balance")
    credits = by_name.get("total_credits")
    debits = by_name.get("total_debits")
    if not (opening and closing and credits and debits):
        return issues

    o = _parse_amount(opening["value"])
    c = _parse_amount(closing["value"])
    cr = _parse_amount(credits["value"])
    db = _parse_amount(debits["value"])
    if None in (o, c, cr, db):
        return issues
    expected = o + cr - db
    if abs(expected - c) > 0.02 * max(abs(c), 1):
        issues[closing["name"]] = {
            "status": "flagged",
            "note": f"Closing {c} ≠ opening {o} + credits {cr} − debits {db} = {expected:.2f}",
        }
    return issues


def _check_line_items_sum(fields: list[dict]) -> dict[str, dict]:
    """Line-item amounts should sum to the subtotal (pre-tax)."""
    by_name = {f["name"]: f for f in fields}
    issues: dict[str, dict] = {}

    items_f = by_name.get("line_items") or by_name.get("items")
    subtotal_f = by_name.get("subtotal")
    if not (items_f and subtotal_f):
        return issues
    try:
        items = json.loads(str(items_f["value"]))
    except Exception:
        return issues
    if not isinstance(items, list) or not items:
        return issues

    total = 0.0
    for item in items:
        if not isinstance(item, dict):
            return issues
        for key in ("amount", "total", "total_price", "line_total"):
            if key in item:
                amt = _parse_amount(str(item[key]))
                if amt is not None:
                    total += amt
                break
        else:
            return issues  # no amount key on an item — can't verify

    sub = _parse_amount(subtotal_f["value"])
    if sub is not None and abs(total - sub) > 0.02 * max(sub, 1):
        issues[items_f["name"]] = {
            "status": "flagged",
            "note": f"Line items sum to {total:.2f} but subtotal is {sub}",
        }
    return issues


# Unambiguous formats only — dd/mm vs mm/dd guessing would produce false flags
_DATE_FORMATS = ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%B %d %Y", "%b %d, %Y")

_DATE_ORDER_RULES: dict[str, list[tuple[str, str, str]]] = {
    "invoice":        [("date", "due_date", "Invoice date is after the due date")],
    "contract":       [("effective_date", "termination_date", "Effective date is after termination date")],
    "id_card":        [("issue_date", "expiry_date", "Issue date is after expiry date")],
    "purchase_order": [("date", "delivery_date", "Order date is after delivery date")],
}


def _parse_date(s: str):
    from datetime import datetime
    s = s.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _check_date_order(fields: list[dict], doc_type: str) -> dict[str, dict]:
    by_name = {f["name"]: f for f in fields}
    issues: dict[str, dict] = {}
    for earlier, later, note in _DATE_ORDER_RULES.get(doc_type, []):
        e_f, l_f = by_name.get(earlier), by_name.get(later)
        if not (e_f and l_f):
            continue
        e_d, l_d = _parse_date(str(e_f["value"])), _parse_date(str(l_f["value"]))
        if e_d and l_d and e_d > l_d:
            issues[later] = {"status": "flagged",
                             "note": f"{note} ({e_f['value']} > {l_f['value']})"}
    return issues


# ── LLM consistency check ─────────────────────────────────────────────────────

def _llm_consistency_check(fields: list[dict], doc_type: str) -> dict[str, dict]:
    """Ask the LLM to verify cross-field consistency and suggest corrections.

    Returns {field_name: {status, note, corrected_value?}} for any field
    the LLM flags. Fields not mentioned are considered OK.
    """
    from ._llm import _cascade, _parse_json  # local import to avoid circular

    field_summary = [
        {"name": f["name"], "label": f["label"], "value": f["value"],
         "confidence": round(f.get("confidence", 1.0), 2)}
        for f in fields
    ]

    system = "You are a document validation expert. Respond only with valid JSON."
    prompt = (
        f"You are reviewing extracted fields from a {doc_type} document.\n"
        "Check for:\n"
        "  1. Cross-field consistency (e.g. invoice total = subtotal + tax)\n"
        "  2. Implausible values (e.g. a year-2099 invoice date)\n"
        "  3. Fields whose value seems swapped with another field\n"
        "  4. Any field you are confident has an obvious correction\n\n"
        f"Extracted fields:\n{json.dumps(field_summary, indent=2)}\n\n"
        "Return JSON with ONLY the fields that have issues:\n"
        '{"issues": [{"name": "<field_name>", "status": "flagged"|"corrected", '
        '"note": "<brief explanation>", "corrected_value": "<new value or null>"}]}\n'
        "If everything looks correct, return: {\"issues\": []}"
    )

    raw = _cascade([{"role": "user", "content": prompt}], system)
    data = _parse_json(raw)
    issues: dict[str, dict] = {}
    for item in data.get("issues", []):
        name = item.get("name", "").strip()
        if not name:
            continue
        entry: dict[str, Any] = {
            "status": item.get("status", "flagged"),
            "note": item.get("note", ""),
        }
        cv = item.get("corrected_value")
        if cv and str(cv).strip().lower() not in {"null", "none", ""}:
            entry["corrected_value"] = str(cv).strip()
        issues[name] = entry
    return issues


# ── Public API ────────────────────────────────────────────────────────────────

def validate_and_correct(fields: list[dict], doc_type: str) -> list[dict]:
    """Run rule checks + LLM consistency pass. Returns fields with validation attached.

    Each field gets a 'validation' key:
      {"status": "ok"|"corrected"|"flagged"|"low_confidence", "note": "..."}
    Corrected fields also get their 'value' updated in-place.
    """
    if not fields:
        return fields

    # Pass 1 — rule-based
    rule_issues: dict[str, dict] = {}
    for f in fields:
        issue = _rule_check(f)
        if issue:
            rule_issues[f["name"]] = issue

    # Pass 2 — deterministic cross-field arithmetic (free, instant)
    arithmetic_issues: dict[str, dict] = {}
    if doc_type in ("invoice", "receipt", "purchase_order"):
        arithmetic_issues.update(_check_invoice_totals(fields))
        arithmetic_issues.update(_check_line_items_sum(fields))
    elif doc_type == "bank_statement":
        arithmetic_issues.update(_check_balance_equation(fields))
    arithmetic_issues.update(_check_date_order(fields, doc_type))

    # Pass 3 — LLM consistency (only when we have enough fields to check)
    llm_issues: dict[str, dict] = {}
    if len(fields) >= 3:
        try:
            llm_issues = _llm_consistency_check(fields, doc_type)
        except Exception as exc:
            logger.warning("LLM consistency check failed: %s", exc)

    # Merge: rule > arithmetic > llm (more specific overrides)
    all_issues = {**llm_issues, **arithmetic_issues, **rule_issues}

    # Apply to fields
    for f in fields:
        issue = all_issues.get(f["name"])
        if issue:
            f["validation"] = {"status": issue["status"], "note": issue["note"]}
            cv = issue.get("corrected_value")
            existing = f.get("value", "").strip()
            # Don't overwrite structured JSON values — LLM flattens them incorrectly
            is_json = existing and existing[0] in ("{", "[")
            if cv and issue["status"] == "corrected" and not is_json:
                f["value"] = cv
        else:
            f["validation"] = {"status": "ok", "note": ""}

    return fields
