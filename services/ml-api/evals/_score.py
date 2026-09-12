"""Turning one analysed golden into a verdict.

Three kinds of check, held to three different standards, because they fail
for three different reasons.

HARD — the deterministic shell. Which provider served, whether the cache
answered instead of a model, and which of eight document types was chosen.
A model has no vote on any of these, so any failure fails the run.

The paid check is the one that matters most. The document cascade fell
through to the only billed key on the Space for weeks and the sole symptom
was an invoice from Google. Here it is a hard failure, and it also bounds
what a nightly run can ever cost.

SCORED — the extracted values. Compared as properties, not strings (see
_check.py). A model can miss one field on one night without that meaning
anything is broken, so these produce a fraction and the run is judged on
the aggregate against a threshold.

INCONCLUSIVE — nobody served. A free tier out of capacity is not a
regression, and marking it as one teaches people to ignore the report. It
is counted and shown separately, and the runner still fails if everything
came back this way, because a whole cascade being down IS worth knowing.
"""
from __future__ import annotations

from ._check import flagged, matches

PAID_PROVIDERS = ("gemini",)


class Verdict:
    def __init__(self, golden_id: str) -> None:
        self.id = golden_id
        self.hard_failures: list[str] = []
        self.value_results: list[tuple[str, bool, str]] = []
        self.inconclusive_reason = ""
        self.provider = ""
        self.seconds = 0.0

    @property
    def matched(self) -> int:
        return sum(1 for _, ok, _ in self.value_results if ok)

    @property
    def total(self) -> int:
        return len(self.value_results)

    @property
    def score(self) -> float:
        return self.matched / self.total if self.total else 0.0

    @property
    def inconclusive(self) -> bool:
        return bool(self.inconclusive_reason)

    @property
    def failed(self) -> bool:
        return bool(self.hard_failures)

    @property
    def misses(self) -> list[tuple[str, str]]:
        return [(name, why) for name, ok, why in self.value_results if not ok]


def score(golden: dict, result) -> Verdict:
    verdict = Verdict(golden["id"])
    verdict.provider = result.provider

    # -- Did anything happen at all -------------------------------------------
    if result.error:
        verdict.inconclusive_reason = f"the request did not complete: {result.error}"
        return verdict
    if not result.done:
        verdict.inconclusive_reason = "the stream ended without a done event"
        return verdict
    if not result.fields:
        verdict.inconclusive_reason = result.warning or "no fields were extracted"
        return verdict

    # -- Hard: the deterministic shell ----------------------------------------
    if result.cached:
        # If this fires the eval has stopped testing anything. The PDF
        # builder stamps a unique reference per run precisely to prevent it.
        verdict.hard_failures.append(
            f"served from cache ({result.provider}) — this run exercised no model"
        )

    if not result.provider:
        verdict.inconclusive_reason = "fields came back but no provider was named"
        return verdict

    for paid in PAID_PROVIDERS:
        if paid in result.provider.lower():
            verdict.hard_failures.append(
                f"the PAID provider ({result.provider}) served this document — "
                "the free providers ahead of it in the cascade are failing silently"
            )

    if result.doc_type != golden["doc_type"]:
        verdict.hard_failures.append(
            f"classified as {result.doc_type!r}, expected {golden['doc_type']!r}"
        )

    # -- Hard: arithmetic the validator owns ----------------------------------
    for name in golden.get("must_flag", []):
        field = result.field(name)
        if field is None:
            continue  # nothing extracted, nothing to check the sum against
        if not flagged(field):
            verdict.hard_failures.append(
                f"{name} does not add up but the validator passed it"
            )

    for name in golden.get("must_not_flag", []):
        field = result.field(name)
        if field is None:
            continue
        if flagged(field):
            note = (field.get("validation") or {}).get("note", "")
            verdict.hard_failures.append(
                f"{name} is correct but the validator flagged it: {note}"
            )

    # -- Scored: the extracted values -----------------------------------------
    for name, (kind, expected) in golden["values"].items():
        field = result.field(name)
        actual = field.get("value") if field else None
        ok, why = matches(kind, expected, actual)
        verdict.value_results.append((name, ok, why))

    return verdict
