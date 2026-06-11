"""
Model quality gate — run in CI after tests, before deploy.

Loads each pre-built model pipeline and scores it against a small holdout
fixture. Exits with code 1 if any model falls below its accuracy/MAE threshold,
preventing a degraded model from being deployed.

Thresholds are set at observed-score minus ~7% slack to catch outright model
corruption or accidental replacement without failing on minor sklearn version
differences.

Usage:
    python scripts/check_model_quality.py
"""

import sys
import json
import pathlib
import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, mean_absolute_error

ROOT     = pathlib.Path(__file__).parent.parent
MODELS   = ROOT / "services/ml-api/models"
SCHEMAS  = ROOT / "services/ml-api/schemas"
FIXTURES = ROOT / "services/ml-api/tests/fixtures"


def load_schema(model_id: str) -> dict:
    with open(SCHEMAS / f"{model_id}.json") as f:
        return json.load(f)


def prep_input(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    """Replicate the same pre-processing the /predict endpoint applies."""
    df = df.copy()
    for col in schema.get("ensure_cols", []):
        df[col] = None
    for col in schema.get("id_cols", []):
        df[col] = float("nan")
    return df


def check_classification(model_id: str, feat_cols: list[str], target_col: str,
                          threshold: float) -> bool:
    schema   = load_schema(model_id)
    pipeline = joblib.load(MODELS / f"{model_id}_pipeline.pkl")
    le       = joblib.load(MODELS / f"{model_id}_labels.pkl")
    df       = pd.read_csv(FIXTURES / f"{model_id}_holdout.csv")

    X        = prep_input(df[feat_cols], schema)
    y_true   = le.transform(df[target_col].astype(str))
    y_pred   = pipeline.predict(X)

    acc = accuracy_score(y_true, y_pred)
    status = "PASS" if acc >= threshold else "FAIL"
    print(f"  [{status}] {model_id:12s}  accuracy={acc*100:.1f}%  threshold={threshold*100:.0f}%")
    return acc >= threshold


def check_regression(model_id: str, feat_cols: list[str], target_col: str,
                     mae_threshold: float) -> bool:
    schema   = load_schema(model_id)
    pipeline = joblib.load(MODELS / f"{model_id}_pipeline.pkl")
    df       = pd.read_csv(FIXTURES / f"{model_id}_holdout.csv")

    X      = prep_input(df[feat_cols], schema)
    y_true = df[target_col].values
    y_pred = pipeline.predict(X)

    mae    = mean_absolute_error(y_true, y_pred)
    status = "PASS" if mae <= mae_threshold else "FAIL"
    print(f"  [{status}] {model_id:12s}  MAE={mae:.1f}  threshold={mae_threshold:.0f}")
    return mae <= mae_threshold


CHECKS = [
    # (fn,                  model_id,    feat_cols,                                                        target,          threshold)
    (check_classification, "iris",
        ["SepalLengthCm", "SepalWidthCm", "PetalLengthCm", "PetalWidthCm"], "Species", 0.80),

    (check_classification, "diabetes",
        ["Pregnancies", "Glucose", "BloodPressure", "SkinThickness",
         "Insulin", "BMI", "DiabetesPedigreeFunction", "Age"], "Outcome", 0.70),

    (check_classification, "titanic",
        ["Pclass", "Sex", "Age", "SibSp", "Parch", "Fare", "Embarked"], "Survived", 0.70),

    (check_regression, "insurance",
        ["Age", "Annual Income", "Number of Dependents", "Health Score",
         "Previous Claims", "Vehicle Age", "Credit Score", "Insurance Duration",
         "Gender", "Marital Status", "Education Level", "Occupation", "Location",
         "Policy Type", "Smoking Status", "Exercise Frequency", "Property Type"],
        "Premium Amount", 100.0),
]


def main() -> int:
    print("Model quality gate")
    print("=" * 50)
    failures = 0
    for fn, model_id, feat_cols, target, threshold in CHECKS:
        try:
            passed = fn(model_id, feat_cols, target, threshold)
            if not passed:
                failures += 1
        except Exception as exc:
            print(f"  [ERROR] {model_id}: {exc}")
            failures += 1

    print("=" * 50)
    if failures:
        print(f"FAILED: {failures} model(s) below threshold — aborting deploy.")
        return 1
    print(f"All {len(CHECKS)} models passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
