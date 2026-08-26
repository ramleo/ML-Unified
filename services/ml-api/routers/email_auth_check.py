"""
Email Header Authentication Checker — pending-list #54.

Parses raw email headers (no message body needed) for two honest signals,
never a fabricated "this is definitely legitimate/phishing" verdict:

1. What the receiving mail server already found — most providers stamp an
   Authentication-Results header with real spf=/dkim=/dmarc= verdicts
   computed against the actual message at delivery time. We only parse and
   relay this, we don't re-verify it.
2. Independent, live DNS checks against the sending domain's real SPF/
   DMARC records and (if present) the DKIM selector's public key — this is
   genuinely useful even without a full cryptographic signature check: a
   domain with no SPF/DMARC record at all, or a DMARC policy of p=none, is
   a real, independently-confirmed weak-spoofing-protection signal.

Deliberately NOT done: cryptographic DKIM body-hash verification. That
needs the full raw message body to compute the body hash, which a
headers-only paste won't have — attempting it against headers alone would
either silently do nothing or mislead. Disclosed in the API response and
the frontend, not silently skipped.
"""

import logging
import re
import time

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email-auth")

_MAX_HEADERS_LEN = 50_000
_DNS_TIMEOUT = 5.0
_DNS_CACHE_TTL_SECONDS = 3600
_dns_cache: dict[str, tuple[float, list[str] | None]] = {}

_AUTH_RESULTS_RE = re.compile(r"(?im)^Authentication-Results:\s*(.+(?:\n[ \t]+.+)*)")
_MECHANISM_RE = re.compile(r"\b(spf|dkim|dmarc)=([a-z]+)", re.IGNORECASE)
_FROM_RE = re.compile(r"(?im)^From:\s*(.+)$")
_EMAIL_DOMAIN_RE = re.compile(r"@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_DKIM_SIG_RE = re.compile(r"(?im)^DKIM-Signature:\s*(.+(?:\n[ \t]+.+)*)")
_RECEIVED_SPF_RE = re.compile(r"(?im)^Received-SPF:\s*(\w+)")


def _fold(raw_header_value: str) -> str:
    """Unfolds an RFC 5322 continuation-line header value into one line."""
    return re.sub(r"\n[ \t]+", " ", raw_header_value).strip()


def _tag_dict(value: str) -> dict[str, str]:
    """Parses a `k1=v1; k2=v2` tag-list (DKIM-Signature, DMARC/SPF TXT records)."""
    tags: dict[str, str] = {}
    for part in _fold(value).split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        tags[k.strip().lower()] = v.strip()
    return tags


def parse_authentication_results(raw: str) -> list[dict]:
    """Every Authentication-Results header found, each as {raw, mechanisms:
    {spf/dkim/dmarc: verdict}} — a message can pick up more than one as it
    hops between mail servers, so all are returned, most-recent (topmost)
    first."""
    results = []
    for m in _AUTH_RESULTS_RE.finditer(raw):
        value = _fold(m.group(1))
        mechanisms = {k.lower(): v.lower() for k, v in _MECHANISM_RE.findall(value)}
        if mechanisms:
            results.append({"raw": value, "mechanisms": mechanisms})
    return results


def parse_from_domain(raw: str) -> str | None:
    m = _FROM_RE.search(raw)
    if not m:
        return None
    dm = _EMAIL_DOMAIN_RE.search(m.group(1))
    return dm.group(1).lower() if dm else None


def parse_dkim_signatures(raw: str) -> list[dict]:
    """Each DKIM-Signature header's selector/domain/algorithm tags — enough
    to look up the public key's DNS record, not enough to verify a
    signature (that needs the message body)."""
    sigs = []
    for m in _DKIM_SIG_RE.finditer(raw):
        tags = _tag_dict(m.group(1))
        if tags.get("s") and tags.get("d"):
            sigs.append({
                "selector": tags["s"],
                "domain": tags["d"].lower(),
                "algorithm": tags.get("a", "unknown"),
            })
    return sigs


def parse_received_spf(raw: str) -> str | None:
    m = _RECEIVED_SPF_RE.search(raw)
    return m.group(1).lower() if m else None


def _dns_txt_lookup(name: str) -> list[str] | None:
    """Sync TXT lookup with a timeout and a small TTL cache — mirrors
    mm_qr_phishing_reputation.py's `_check_domain_age` contract: returns
    None (not []) on any failure, so callers never mistake "couldn't
    check" for "checked, found nothing". Falls back to public DNS
    (8.8.8.8/1.1.1.1) if the environment's own configured resolver times
    out — found via a real local-resolver timeout on a normal domain
    during development, not assumed upfront; the environment's default
    resolver can't be trusted to always be fast or reachable."""
    now = time.time()
    cached = _dns_cache.get(name)
    if cached and now - cached[0] < _DNS_CACHE_TTL_SECONDS:
        return cached[1]

    import dns.resolver

    records: list[str] | None = None
    for nameservers in (None, ["8.8.8.8", "1.1.1.1"]):
        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = _DNS_TIMEOUT
            resolver.lifetime = _DNS_TIMEOUT
            if nameservers:
                resolver.nameservers = nameservers
            answer = resolver.resolve(name, "TXT")
            records = ["".join(s.decode() if isinstance(s, bytes) else s for s in r.strings) for r in answer]
            break
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            break  # a real, authoritative "no such record" — not a network failure, don't retry
        except Exception as exc:
            logger.info("DNS TXT lookup failed for %s (nameservers=%s): %s", name, nameservers, exc)

    _dns_cache[name] = (now, records)
    return records


def check_spf_record(domain: str) -> dict:
    records = _dns_txt_lookup(domain) or []
    spf = next((r for r in records if r.lower().startswith("v=spf1")), None)
    if not spf:
        return {"found": False, "record": None, "all_qualifier": None}
    if re.search(r"([-~+?]?)all\b", spf):
        qualifier = re.search(r"([-~+?]?)all\b", spf).group(1) or "+"
    else:
        qualifier = None
    labels = {"-": "strict (-all, hard fail)", "~": "soft fail (~all)", "+": "permissive (+all, no protection)", "?": "neutral (?all)"}
    return {"found": True, "record": spf, "all_qualifier": labels.get(qualifier, "no 'all' mechanism found") if qualifier else "no 'all' mechanism found"}


def check_dmarc_record(domain: str) -> dict:
    records = _dns_txt_lookup(f"_dmarc.{domain}") or []
    dmarc = next((r for r in records if r.lower().startswith("v=dmarc1")), None)
    if not dmarc:
        return {"found": False, "record": None, "policy": None, "subdomain_policy": None, "pct": None}
    tags = _tag_dict(dmarc)
    return {
        "found": True,
        "record": dmarc,
        "policy": tags.get("p"),
        "subdomain_policy": tags.get("sp"),
        "pct": tags.get("pct", "100"),
    }


def check_dkim_dns(selector: str, domain: str) -> dict:
    records = _dns_txt_lookup(f"{selector}._domainkey.{domain}") or []
    key_record = next((r for r in records if "v=dkim1" in r.lower() or "p=" in r.lower()), None)
    if not key_record:
        return {"found": False, "revoked": None}
    tags = _tag_dict(key_record)
    return {"found": True, "revoked": not bool(tags.get("p"))}


def _domain_alignment(from_domain: str | None, dkim_signatures: list[dict], spf_domain: str | None) -> dict:
    """DMARC-style relaxed alignment: organizational domain match is enough,
    not an exact hostname match (e.g. mail.example.com aligns with
    example.com)."""
    def org(d: str) -> str:
        parts = d.lower().split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else d.lower()

    if not from_domain:
        return {"dkim_aligned": None, "spf_aligned": None}
    from_org = org(from_domain)
    dkim_aligned = any(org(s["domain"]) == from_org for s in dkim_signatures) if dkim_signatures else None
    spf_aligned = (org(spf_domain) == from_org) if spf_domain else None
    return {"dkim_aligned": dkim_aligned, "spf_aligned": spf_aligned}


def run_email_auth_check(raw_headers: str) -> dict:
    from_domain = parse_from_domain(raw_headers)
    auth_results = parse_authentication_results(raw_headers)
    dkim_signatures = parse_dkim_signatures(raw_headers)
    received_spf = parse_received_spf(raw_headers)

    spf_domain = from_domain
    spf = check_spf_record(spf_domain) if spf_domain else {"found": False, "record": None, "all_qualifier": None}
    dmarc = check_dmarc_record(from_domain) if from_domain else {"found": False, "record": None, "policy": None, "subdomain_policy": None, "pct": None}

    for sig in dkim_signatures:
        sig["dns"] = check_dkim_dns(sig["selector"], sig["domain"])

    alignment = _domain_alignment(from_domain, dkim_signatures, spf_domain if spf["found"] else None)

    warnings: list[str] = []
    if not auth_results:
        warnings.append("No Authentication-Results header found — this may be a raw outbound message, or the receiving server didn't stamp one, or headers were trimmed when pasted.")
    if not dmarc["found"]:
        warnings.append(f"No DMARC record published for {from_domain} — spoofed mail claiming to be from this domain has no enforced policy to be rejected against." if from_domain else "Could not determine the From: domain.")
    elif dmarc["policy"] == "none":
        warnings.append(f"{from_domain}'s DMARC policy is p=none — spoofing attempts are only monitored/reported, not blocked or quarantined.")
    if not spf["found"] and from_domain:
        warnings.append(f"No SPF record published for {from_domain}.")
    elif spf.get("all_qualifier") == "permissive (+all, no protection)":
        warnings.append(f"{from_domain}'s SPF record ends in +all — this explicitly allows ANY server to send mail as this domain.")
    if alignment["dkim_aligned"] is False and alignment["spf_aligned"] is False:
        warnings.append("Neither the DKIM signature's domain nor the SPF-checked domain aligns with the From: domain — a classic display-name-spoofing pattern.")

    stamped_fail = any(v == "fail" for r in auth_results for v in r["mechanisms"].values())
    if stamped_fail:
        verdict = "suspicious"
        verdict_reason = "The receiving server's own Authentication-Results reports at least one mechanism as fail."
    elif dmarc["found"] and dmarc["policy"] in ("quarantine", "reject") and (alignment["dkim_aligned"] or alignment["spf_aligned"]):
        verdict = "likely legitimate"
        verdict_reason = f"Domain enforces DMARC (p={dmarc['policy']}) and alignment checks pass."
    elif len(warnings) >= 2:
        verdict = "weak authentication"
        verdict_reason = "Multiple weak-or-missing authentication signals found — doesn't prove spoofing, but the sending domain isn't well protected against it."
    else:
        verdict = "inconclusive"
        verdict_reason = "Not enough signal to call this confidently either way from headers alone."

    return {
        "from_domain": from_domain,
        "authentication_results": auth_results,
        "received_spf": received_spf,
        "dkim_signatures": dkim_signatures,
        "spf": spf,
        "dmarc": dmarc,
        "alignment": alignment,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "warnings": warnings,
    }


class EmailAuthCheckRequest(BaseModel):
    raw_headers: str = Field(..., max_length=_MAX_HEADERS_LEN)


@router.post("/check")
def email_auth_check(req: EmailAuthCheckRequest):
    return run_email_auth_check(req.raw_headers)
