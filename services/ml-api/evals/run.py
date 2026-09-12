"""Run the golden set and report.

    python -m evals.run                 # against the deployed Space
    EVAL_BASE_URL=http://localhost:7860 python -m evals.run
    python -m evals.run --only invoice_consistent
    python -m evals.run --dry-run       # build and score nothing, no calls

Exits non-zero when the run fails, which is what makes the nightly
workflow send mail. See .github/workflows/nightly-evals.yml.

Why nightly and not per commit: every golden costs real provider calls on
a free tier, and the output moves between runs by design. A suite like
that on every push would be slow, would go red for capacity reasons, and
would be switched off within a week.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import uuid

from . import _client
from ._pdf import build_pdf
from ._score import score
from .goldens import GOLDENS

# The share of expected VALUES that must match across the whole run. Not
# per document: one model missing one field on one night is noise, and a
# per-document gate would make the report a coin toss. Below this, either
# something regressed or a provider swap changed behaviour, and either way
# somebody should look.
THRESHOLD = float(os.environ.get("EVAL_THRESHOLD", "0.80"))

# Free tiers rate limit. A pause between documents costs nothing at 3am and
# turns a 429 storm into a clean run.
PAUSE_SECONDS = float(os.environ.get("EVAL_PAUSE_SECONDS", "6"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the document golden set.")
    parser.add_argument("--only", action="append", default=[],
                        help="run just this golden id (repeatable)")
    parser.add_argument("--dry-run", action="store_true",
                        help="build the PDFs and stop — makes no provider calls")
    args = parser.parse_args()

    goldens = [g for g in GOLDENS if not args.only or g["id"] in args.only]
    if not goldens:
        print(f"No golden matched {args.only}. Known: {[g['id'] for g in GOLDENS]}")
        return 2

    run_id = uuid.uuid4().hex[:12]
    print(f"Golden set: {len(goldens)} document(s)")
    print(f"Target:     {_client.BASE_URL}")
    print(f"Run id:     {run_id}   (stamped into each PDF so the cache cannot answer)")
    print(f"Threshold:  {THRESHOLD:.0%} of expected values\n")

    if args.dry_run:
        for golden in goldens:
            pdf = build_pdf(golden["lines"], run_id)
            print(f"  built {golden['id']:<34} {len(pdf):>7,} bytes")
        print("\nDry run — nothing was sent.")
        return 0

    verdicts = []
    for index, golden in enumerate(goldens):
        pdf = build_pdf(golden["lines"], run_id)
        started = time.time()
        result = _client.analyze(pdf, f"{golden['id']}.pdf")
        verdict = score(golden, result)
        verdict.seconds = round(time.time() - started, 1)
        verdicts.append(verdict)
        _print_one(verdict)
        if index < len(goldens) - 1:
            time.sleep(PAUSE_SECONDS)

    return _report(verdicts)


def _print_one(verdict) -> None:
    if verdict.inconclusive:
        mark, tail = "?", verdict.inconclusive_reason
    elif verdict.failed:
        mark, tail = "FAIL", f"{verdict.matched}/{verdict.total} values"
    else:
        mark, tail = "ok", f"{verdict.matched}/{verdict.total} values"

    provider = verdict.provider or "-"
    print(f"  [{mark:>4}] {verdict.id:<34} {provider:<18} {verdict.seconds:>5}s  {tail}")

    for problem in verdict.hard_failures:
        print(f"         ! {problem}")
    for name, why in verdict.misses:
        print(f"         - {name}: {why}")


def _report(verdicts) -> int:
    scored = [v for v in verdicts if not v.inconclusive]
    inconclusive = [v for v in verdicts if v.inconclusive]
    hard = [v for v in verdicts if v.failed]

    matched = sum(v.matched for v in scored)
    total = sum(v.total for v in scored)
    rate = matched / total if total else 0.0

    print("\n" + "-" * 72)
    print(f"Values matched : {matched}/{total}" + (f"  ({rate:.0%})" if total else ""))
    print(f"Hard failures  : {len(hard)}")
    print(f"Inconclusive   : {len(inconclusive)}")

    providers = sorted({v.provider for v in scored if v.provider})
    print(f"Served by      : {', '.join(providers) or '-'}")

    if inconclusive and not scored:
        print("\nFAIL — every document came back inconclusive. That is not a free "
              "tier having a bad night, that is the whole cascade being down.")
        return 1

    if hard:
        print(f"\nFAIL — {len(hard)} document(s) broke a rule a model has no vote on.")
        return 1

    if total and rate < THRESHOLD:
        print(f"\nFAIL — {rate:.0%} of expected values matched, below the "
              f"{THRESHOLD:.0%} threshold.")
        return 1

    if inconclusive:
        print(f"\nPASS, with {len(inconclusive)} inconclusive — a provider was "
              "unavailable, not a regression. Worth a second look if it repeats.")
        return 0

    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
