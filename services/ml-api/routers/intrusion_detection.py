"""
Real supervised network-intrusion classification with scikit-learn's
RandomForestClassifier, over the NSL-KDD benchmark's numeric connection
features.

The honesty pattern matches the Log Anomaly Detector: the CALLER owns the
labelled data and the ground truth, this endpoint does the genuine ML half.
The frontend ships a small, pre-encoded subset of NSL-KDD (train + a held-out
test split with true labels it keeps), sends the numeric matrices here; this
fits a RandomForest on the training rows and predicts the test rows. The model
never sees the test labels, so the caller can score the predictions against its
own ground truth and show a real confusion matrix and per-class precision/recall
— including the classes NSL-KDD is famously bad at (R2L, U2R).

This endpoint is dataset-agnostic on purpose: it takes numeric feature rows and
integer class labels and returns predictions, per-row confidence (max class
probability) and the model's feature importances. Nothing is persisted.
"""
from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sklearn.ensemble import RandomForestClassifier

router = APIRouter()

# Guardrails — bound the work per request regardless of what the caller sends.
_MIN_TRAIN = 50
_MAX_TRAIN = 8000
_MAX_TEST = 3000
_MAX_FEATURES = 128


class ClassifyRequest(BaseModel):
    train_X: list[list[float]] = Field(..., description="Training feature rows.")
    train_y: list[int] = Field(..., description="Training class labels (ints).")
    test_X: list[list[float]] = Field(..., description="Rows to classify.")
    n_estimators: int = Field(default=200, ge=10, le=300)
    random_state: int = 42


class RowResult(BaseModel):
    pred: int
    confidence: float  # 0..1, the model's max class probability for this row


class ClassifyResponse(BaseModel):
    results: list[RowResult]
    feature_importances: list[float]
    classes: list[int]
    n_train: int
    n_test: int


def _matrix(rows: list[list[float]], label: str, width: int | None) -> np.ndarray:
    if not rows:
        raise HTTPException(status_code=400, detail=f"{label} is empty.")
    arr = np.asarray(rows, dtype=float)
    if arr.ndim != 2:
        raise HTTPException(status_code=400, detail=f"{label} must be a 2-D array of numbers.")
    if width is not None and arr.shape[1] != width:
        raise HTTPException(
            status_code=400,
            detail=f"{label} has {arr.shape[1]} features but expected {width}.",
        )
    if arr.shape[1] > _MAX_FEATURES:
        raise HTTPException(status_code=400, detail=f"Too many features (max {_MAX_FEATURES}).")
    if not np.isfinite(arr).all():
        raise HTTPException(status_code=400, detail=f"{label} contains non-finite values.")
    return arr


@router.post("/intrusion-detection/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest) -> ClassifyResponse:
    train_X = _matrix(req.train_X, "train_X", None)
    test_X = _matrix(req.test_X, "test_X", train_X.shape[1])

    if len(train_X) < _MIN_TRAIN:
        raise HTTPException(status_code=400, detail=f"Need at least {_MIN_TRAIN} training rows.")
    if len(train_X) > _MAX_TRAIN:
        raise HTTPException(status_code=400, detail=f"train_X too large (max {_MAX_TRAIN}).")
    if len(test_X) > _MAX_TEST:
        raise HTTPException(status_code=400, detail=f"test_X too large (max {_MAX_TEST}).")
    if len(req.train_y) != len(train_X):
        raise HTTPException(status_code=400, detail="train_y length must match train_X.")

    y = np.asarray(req.train_y, dtype=int)
    if len(np.unique(y)) < 2:
        raise HTTPException(status_code=400, detail="train_y needs at least two distinct classes.")

    model = RandomForestClassifier(
        n_estimators=req.n_estimators,
        random_state=req.random_state,
        n_jobs=-1,
    )
    model.fit(train_X, y)

    proba = model.predict_proba(test_X)        # (n_test, n_classes)
    best = proba.argmax(axis=1)
    classes = model.classes_                    # maps proba column -> class label
    preds = classes[best]
    confidence = proba[np.arange(len(test_X)), best]

    results = [
        RowResult(pred=int(preds[i]), confidence=round(float(confidence[i]), 4))
        for i in range(len(test_X))
    ]

    return ClassifyResponse(
        results=results,
        feature_importances=[round(float(v), 5) for v in model.feature_importances_],
        classes=[int(c) for c in classes],
        n_train=int(len(train_X)),
        n_test=int(len(test_X)),
    )
