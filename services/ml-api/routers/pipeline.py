from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# Key params to surface per estimator type
_KEY_PARAMS: dict[str, list[str]] = {
    "RandomForestClassifier":      ["n_estimators", "max_depth", "max_features", "min_samples_split"],
    "RandomForestRegressor":       ["n_estimators", "max_depth", "max_features", "min_samples_split"],
    "GradientBoostingClassifier":  ["n_estimators", "learning_rate", "max_depth", "subsample"],
    "GradientBoostingRegressor":   ["n_estimators", "learning_rate", "max_depth", "subsample"],
    "XGBClassifier":               ["n_estimators", "learning_rate", "max_depth", "subsample"],
    "XGBRegressor":                ["n_estimators", "learning_rate", "max_depth", "subsample"],
    "LGBMClassifier":              ["n_estimators", "learning_rate", "num_leaves", "max_depth"],
    "LGBMRegressor":               ["n_estimators", "learning_rate", "num_leaves", "max_depth"],
    "CatBoostClassifier":          ["iterations", "learning_rate", "depth"],
    "CatBoostRegressor":           ["iterations", "learning_rate", "depth"],
    "LogisticRegression":          ["C", "max_iter", "solver", "penalty"],
    "LinearRegression":            [],
    "Ridge":                       ["alpha"],
    "Lasso":                       ["alpha"],
    "SVC":                         ["C", "kernel", "gamma"],
    "KMeans":                      ["n_clusters", "init", "max_iter"],
    "DBSCAN":                      ["eps", "min_samples", "metric"],
    "SimpleImputer":               ["strategy"],
    "StandardScaler":              ["with_mean", "with_std"],
    "MinMaxScaler":                [],
    "RobustScaler":                [],
    "OneHotEncoder":               ["handle_unknown", "drop"],
    "OrdinalEncoder":              [],
    "LabelEncoder":                [],
}

_STEP_LABELS: dict[str, str] = {
    "SimpleImputer":              "Imputer",
    "StandardScaler":             "Standard Scaler",
    "MinMaxScaler":               "Min-Max Scaler",
    "RobustScaler":               "Robust Scaler",
    "OneHotEncoder":              "One-Hot Encoder",
    "OrdinalEncoder":             "Ordinal Encoder",
    "LabelEncoder":               "Label Encoder",
    "ColumnTransformer":          "Column Transformer",
    "RandomForestClassifier":     "Random Forest",
    "RandomForestRegressor":      "Random Forest",
    "GradientBoostingClassifier": "Gradient Boosting",
    "GradientBoostingRegressor":  "Gradient Boosting",
    "XGBClassifier":              "XGBoost",
    "XGBRegressor":               "XGBoost",
    "LGBMClassifier":             "LightGBM",
    "LGBMRegressor":              "LightGBM",
    "CatBoostClassifier":         "CatBoost",
    "CatBoostRegressor":          "CatBoost",
    "LogisticRegression":         "Logistic Regression",
    "LinearRegression":           "Linear Regression",
    "Ridge":                      "Ridge Regression",
    "Lasso":                      "Lasso Regression",
    "SVC":                        "Support Vector Machine",
    "KMeans":                     "K-Means",
    "DBSCAN":                     "DBSCAN",
}


def _fmt_val(v) -> str:
    if v is None:
        return "None"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def _key_params(estimator) -> dict:
    cls = type(estimator).__name__
    keys = _KEY_PARAMS.get(cls, [])
    try:
        all_p = estimator.get_params(deep=False)
    except Exception:
        return {}
    return {k: _fmt_val(all_p[k]) for k in keys if k in all_p}


def _describe_step(estimator) -> dict:
    cls = type(estimator).__name__
    return {
        "type":   cls,
        "label":  _STEP_LABELS.get(cls, cls),
        "params": _key_params(estimator),
    }


def _describe_transformer(name: str, tobj, cols, field_labels: dict) -> dict:
    col_labels = [field_labels.get(c, c) for c in cols] if isinstance(cols, list) else []
    steps = []
    if hasattr(tobj, "steps"):
        steps = [_describe_step(s) for _, s in tobj.steps]
    else:
        steps = [_describe_step(tobj)]
    return {"name": name, "columns": col_labels, "steps": steps}


@router.get("/{model_id}")
def get_pipeline(model_id: str):
    from app import MODELS  # lazy — avoids circular import at load time

    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")

    m        = MODELS[model_id]
    pipeline = m["pipeline"]
    schema   = m["schema"]

    field_labels = {f["name"]: f.get("label", f["name"]) for f in schema.get("fields", [])}
    input_fields = [f.get("label", f["name"]) for f in schema.get("fields", [])]

    steps = []
    for _, estimator in pipeline.steps:
        cls = type(estimator).__name__
        if hasattr(estimator, "transformers"):
            # ColumnTransformer
            transformers = [
                _describe_transformer(tname, tobj, cols, field_labels)
                for tname, tobj, cols in estimator.transformers
                if tname != "remainder"
            ]
            steps.append({
                "kind":         "preprocessor",
                "type":         cls,
                "label":        _STEP_LABELS.get(cls, cls),
                "transformers": transformers,
            })
        else:
            steps.append({
                "kind":   "estimator",
                **_describe_step(estimator),
            })

    return {
        "model_id":     model_id,
        "title":        schema["title"],
        "task":         schema["task"],
        "input_fields": input_fields,
        "steps":        steps,
    }
