"""
Real unsupervised anomaly detection over HTTP-request metadata, using
scikit-learn's IsolationForest — the classic "isolate the odd point in few
random splits" estimator, the same algorithm the demo dashboard narrates.

The honesty line for the tool that calls this: a Hobby-tier serverless site
cannot stream its OWN real request logs into a public tool, so the CALLER
generates a labelled, simulated traffic stream (a normal baseline plus a few
planted attack patterns whose ground truth it keeps) and sends the numeric
features here. This endpoint does the genuine machine-learning half: it fits
an IsolationForest on the baseline of normal traffic ONLY, then scores each
event. The model never sees the labels, so the caller can compare the model's
flags against its own ground truth and report real precision/recall — a demo
that can be caught being wrong, not a rigged highlight reel.

The features are ordinary request metadata a real WAF would have:
  0 req_per_min    requests in the last minute from this event's IP
  1 payload_bytes  request body size
  2 hour           hour of day, 0..23 (off-hours bursts look odd)
  3 path_randomness share of the path that looks like a random token, i.e. the
                    fraction of digit characters (a fuzzer/scanner hitting random
                    hex-ish paths scores high, an app's own named routes score 0)
  4 error_rate     fraction of 4xx/5xx responses from this IP in the window

IsolationForest gives a verdict and a continuous score, but NOT a cheap
per-feature "why". So alongside the model verdict we compute, separately and
honestly labelled, the single feature that deviates most from the baseline
(largest |z|). It is presented as "most unusual feature", not as "the reason
the model flagged this" — the two are different signals and the UI says so.
"""
from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sklearn.ensemble import IsolationForest

router = APIRouter()

FEATURE_NAMES = ["req_per_min", "payload_bytes", "hour", "path_randomness", "error_rate"]
_N_FEATURES = len(FEATURE_NAMES)

# Guardrails — this is a demo detector, not a firehose ingester. These bounds
# keep one request cheap and bound the work regardless of what the caller sends.
_MAX_BASELINE = 5000
_MIN_BASELINE = 20   # IsolationForest needs a real baseline to learn "normal"
_MAX_EVENTS = 2000


class ScoreRequest(BaseModel):
    # Each row is exactly _N_FEATURES numbers, in FEATURE_NAMES order.
    baseline: list[list[float]] = Field(..., description="Normal-traffic rows to learn from.")
    events: list[list[float]] = Field(..., description="Rows to score.")
    # None -> IsolationForest's own "auto" threshold. A caller that knows its
    # planted attack ratio can pass it, but the model still never sees labels.
    contamination: float | None = Field(default=None, ge=0.0, le=0.5)
    # Fixed by default so the same simulated scenario scores identically on a
    # re-run — a demo that jumps around every refresh reads as noise, not a model.
    random_state: int = 42


class EventResult(BaseModel):
    is_anomaly: bool
    # 0..1, higher = more anomalous. A monotonic transform of the raw score,
    # for colouring rows; the verdict is is_anomaly, not a hand-picked cutoff.
    severity: float
    # Raw IsolationForest decision_function: < 0 is the model's anomaly side.
    decision: float
    # Honest, model-independent: the feature furthest from baseline, and how
    # many standard deviations out. Helps a human read the row; NOT the model's
    # internal reason.
    top_feature: str
    top_feature_z: float


class ScoreResponse(BaseModel):
    results: list[EventResult]
    feature_names: list[str]
    n_baseline: int
    n_flagged: int


def _validate_rows(rows: list[list[float]], label: str) -> np.ndarray:
    if not rows:
        raise HTTPException(status_code=400, detail=f"{label} is empty.")
    arr = np.asarray(rows, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != _N_FEATURES:
        raise HTTPException(
            status_code=400,
            detail=f"Each {label} row must have exactly {_N_FEATURES} numbers "
                   f"({', '.join(FEATURE_NAMES)}).",
        )
    if not np.isfinite(arr).all():
        raise HTTPException(status_code=400, detail=f"{label} contains non-finite values.")
    return arr


@router.post("/anomaly-detection/score", response_model=ScoreResponse)
def score(req: ScoreRequest) -> ScoreResponse:
    baseline = _validate_rows(req.baseline, "baseline")
    events = _validate_rows(req.events, "events")

    if len(baseline) < _MIN_BASELINE:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {_MIN_BASELINE} baseline rows to learn normal traffic.",
        )
    if len(baseline) > _MAX_BASELINE:
        raise HTTPException(status_code=400, detail=f"baseline too large (max {_MAX_BASELINE}).")
    if len(events) > _MAX_EVENTS:
        raise HTTPException(status_code=400, detail=f"events too large (max {_MAX_EVENTS}).")

    # Fit on the normal baseline ONLY — the model must learn "normal" without
    # ever seeing the attacks it will later be asked to spot.
    model = IsolationForest(
        n_estimators=200,
        contamination=req.contamination if req.contamination is not None else "auto",
        random_state=req.random_state,
    )
    model.fit(baseline)

    # decision_function: higher = more normal, < 0 = model's anomaly side.
    decisions = model.decision_function(events)
    predictions = model.predict(events)  # -1 anomaly, 1 normal

    # Map decision -> 0..1 severity with a sigmoid centred at the model's own
    # threshold (0), so the colour ramp tracks the verdict instead of an
    # arbitrary min/max of whatever batch happened to arrive.
    severities = 1.0 / (1.0 + np.exp(10.0 * decisions))

    # Per-feature deviation from baseline, for the honest "most unusual feature"
    # readout. std can be 0 for a constant feature; guard it.
    mean = baseline.mean(axis=0)
    std = baseline.std(axis=0)
    std_safe = np.where(std < 1e-9, 1.0, std)
    z = np.abs((events - mean) / std_safe)
    top_idx = z.argmax(axis=1)

    results = [
        EventResult(
            is_anomaly=bool(predictions[i] == -1),
            severity=round(float(severities[i]), 4),
            decision=round(float(decisions[i]), 4),
            top_feature=FEATURE_NAMES[int(top_idx[i])],
            top_feature_z=round(float(z[i, top_idx[i]]), 2),
        )
        for i in range(len(events))
    ]

    return ScoreResponse(
        results=results,
        feature_names=FEATURE_NAMES,
        n_baseline=len(baseline),
        n_flagged=sum(1 for r in results if r.is_anomaly),
    )
