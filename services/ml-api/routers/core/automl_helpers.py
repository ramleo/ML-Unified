"""Pure AutoML helper functions (no FastAPI, no shared imports)."""
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression, Ridge as RidgeRegressor, Lasso, ElasticNet
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.svm import SVC, SVR
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import (
    RandomForestClassifier, GradientBoostingClassifier,
    RandomForestRegressor, GradientBoostingRegressor,
    ExtraTreesClassifier, ExtraTreesRegressor,
)
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline

# Re-export so callers only need to import from automl_helpers
from routers.core.fe_transformer import FeatureEngineeringTransformer  # noqa: F401

_AUTOML_MAX_CV_ROWS = 5000


def _cv_sample(X: pd.DataFrame, y, max_rows: int = _AUTOML_MAX_CV_ROWS):
    """Subsample for cross-validation on large datasets."""
    if len(X) <= max_rows:
        return X, y
    import numpy as _np  # noqa: PLC0415
    idx = _np.random.RandomState(42).choice(len(X), max_rows, replace=False)
    if hasattr(y, "iloc"):
        return X.iloc[idx].reset_index(drop=True), y.iloc[idx].reset_index(drop=True)
    return X.iloc[idx].reset_index(drop=True), y[idx]


def _extract_feature_importances(pipeline, num_cols: list, cat_cols: list) -> list:
    model = pipeline.named_steps.get("model")
    if model is None or not hasattr(model, "feature_importances_"):
        return []
    importances = model.feature_importances_
    prep = pipeline.named_steps["prep"]

    all_feats = list(num_cols)
    if cat_cols:
        try:
            ohe = prep.named_transformers_["cat"].named_steps["enc"]
            for i, col in enumerate(cat_cols):
                n_cats = len(ohe.categories_[i])
                all_feats.extend([col] * n_cats)
        except (KeyError, AttributeError):
            all_feats.extend(cat_cols)

    imp_map: dict = {}
    for i, feat in enumerate(all_feats):
        if i >= len(importances):
            break
        imp_map[feat] = imp_map.get(feat, 0.0) + float(importances[i])

    total = sum(imp_map.values()) or 1.0
    return [
        {"feature": k, "importance": round(v / total * 100, 1)}
        for k, v in sorted(imp_map.items(), key=lambda x: -x[1])
    ][:10]


def _optuna_tune(
    algorithm: str, task: str, X_cv, y_cv, transformers: list,
    cv_split, n_trials: int, is_imbal: bool, on_trial,
    opt_metric: str = "auto",
    sampler: str = "tpe",
    secondary_metric: str = "none",
) -> tuple[dict, float, list, dict, list]:
    import optuna  # noqa: PLC0415
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    from xgboost import XGBClassifier, XGBRegressor          # noqa: PLC0415
    from lightgbm import LGBMClassifier, LGBMRegressor        # noqa: PLC0415
    from catboost import CatBoostClassifier, CatBoostRegressor  # noqa: PLC0415
    if task == "regression":
        if opt_metric == "rmse":
            scoring = "neg_root_mean_squared_error"
        elif opt_metric == "r2":
            scoring = "r2"
        else:  # "auto" or "mae"
            scoring = "neg_mean_absolute_error"
    else:  # classification
        if opt_metric == "accuracy":
            scoring = "accuracy"
        elif opt_metric == "f1_weighted":
            scoring = "f1_weighted"
        elif opt_metric == "f1_macro":
            scoring = "f1_macro"
        elif opt_metric == "roc_auc":
            scoring = "roc_auc"
        else:  # "auto"
            scoring = "f1_macro" if is_imbal else "f1_weighted"

    _sec_scoring_map = {}
    if task == "regression":
        _sec_scoring_map = {"mae": "neg_mean_absolute_error", "rmse": "neg_root_mean_squared_error", "r2": "r2"}
    else:
        _sec_scoring_map = {"accuracy": "accuracy", "f1_weighted": "f1_weighted", "f1_macro": "f1_macro"}
    _secondary_scoring = _sec_scoring_map.get(secondary_metric) if secondary_metric != "none" else None

    def objective(trial):
        cw = "balanced" if is_imbal else None
        if algorithm == "Random Forest":
            params: dict = {
                "n_estimators":      trial.suggest_int("n_estimators", 50, 300),
                "max_depth":         trial.suggest_categorical("max_depth", [None, 5, 10, 15, 20]),
                "min_samples_split": trial.suggest_int("min_samples_split", 2, 10),
                "min_samples_leaf":  trial.suggest_int("min_samples_leaf", 1, 4),
                "max_features":      trial.suggest_categorical("max_features", ["sqrt", "log2"]),
            }
            est = (RandomForestClassifier(random_state=42, class_weight=cw, **params)
                   if task == "classification"
                   else RandomForestRegressor(random_state=42, **params))
        elif algorithm == "XGBoost":
            params = {
                "n_estimators":      trial.suggest_int("n_estimators", 50, 500),
                "max_depth":         trial.suggest_int("max_depth", 3, 12),
                "learning_rate":     trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
                "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "min_child_weight":  trial.suggest_int("min_child_weight", 1, 10),
                "gamma":             trial.suggest_float("gamma", 0.0, 5.0),
                "reg_alpha":         trial.suggest_float("reg_alpha", 0.0, 5.0),
                "reg_lambda":        trial.suggest_float("reg_lambda", 0.1, 5.0),
            }
            est = (XGBClassifier(random_state=42, eval_metric="logloss", verbosity=0, **params)
                   if task == "classification"
                   else XGBRegressor(random_state=42, verbosity=0, **params))
        elif algorithm == "LightGBM":
            params = {
                "n_estimators":      trial.suggest_int("n_estimators", 50, 500),
                "num_leaves":        trial.suggest_int("num_leaves", 20, 200),
                "learning_rate":     trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
                "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
                "reg_alpha":         trial.suggest_float("reg_alpha", 0.0, 5.0),
                "reg_lambda":        trial.suggest_float("reg_lambda", 0.0, 5.0),
            }
            est = (LGBMClassifier(random_state=42, verbose=-1, class_weight=cw, **params)
                   if task == "classification"
                   else LGBMRegressor(random_state=42, verbose=-1, **params))
        else:  # CatBoost
            params = {
                "iterations":    trial.suggest_int("iterations", 50, 400),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "depth":         trial.suggest_int("depth", 4, 10),
                "l2_leaf_reg":   trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
            }
            est = (CatBoostClassifier(random_seed=42, verbose=0, **params)
                   if task == "classification"
                   else CatBoostRegressor(random_seed=42, verbose=0, **params))

        pl    = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")), ("model", est)])
        score = float(cross_val_score(pl, X_cv, y_cv, cv=cv_split, scoring=scoring).mean())
        on_trial(trial.number + 1, score)
        if _secondary_scoring:
            try:
                _sec = float(cross_val_score(pl, X_cv, y_cv, cv=cv_split, scoring=_secondary_scoring).mean())
                trial.set_user_attr("secondary_score", _sec)
            except Exception:
                pass
        return score

    if sampler == "gp":
        _sampler = optuna.samplers.GPSampler(seed=42)
    elif sampler == "auto":
        _sampler = optuna.samplers.AutoSampler()
    else:
        _sampler = optuna.samplers.TPESampler(seed=42, multivariate=True, n_startup_trials=10)

    study = optuna.create_study(
        direction="maximize",
        sampler=_sampler,
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=0),
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    trial_history = [
        {"trial": t.number + 1, "value": round(float(t.value), 4)}
        for t in study.trials
        if t.value is not None
    ]

    try:
        raw_imp = optuna.importance.get_param_importances(study)
        param_importance = {k: round(float(v), 4) for k, v in raw_imp.items()}
    except Exception:
        param_importance = {}

    secondary_trials = []
    if _secondary_scoring:
        secondary_trials = [
            {"trial": t.number + 1, "value": round(float(t.user_attrs["secondary_score"]), 4)}
            for t in study.trials
            if "secondary_score" in t.user_attrs
        ]

    if not trial_history:
        raise RuntimeError("All Optuna trials failed — no completed trials")
    return study.best_params, study.best_value, trial_history, param_importance, secondary_trials


def _build_tuned_estimator(algorithm: str, task: str, best_params: dict, is_imbal: bool):
    from xgboost import XGBClassifier, XGBRegressor          # noqa: PLC0415
    from lightgbm import LGBMClassifier, LGBMRegressor        # noqa: PLC0415
    from catboost import CatBoostClassifier, CatBoostRegressor  # noqa: PLC0415
    cw = "balanced" if is_imbal else None
    if algorithm == "Random Forest":
        return (RandomForestClassifier(random_state=42, class_weight=cw, **best_params)
                if task == "classification"
                else RandomForestRegressor(random_state=42, **best_params))
    if algorithm == "XGBoost":
        return (XGBClassifier(random_state=42, eval_metric="logloss", verbosity=0, **best_params)
                if task == "classification"
                else XGBRegressor(random_state=42, verbosity=0, **best_params))
    if algorithm == "LightGBM":
        return (LGBMClassifier(random_state=42, verbose=-1, class_weight=cw, **best_params)
                if task == "classification"
                else LGBMRegressor(random_state=42, verbose=-1, **best_params))
    return (CatBoostClassifier(random_seed=42, verbose=0, **best_params)
            if task == "classification"
            else CatBoostRegressor(random_seed=42, verbose=0, **best_params))


def _rule_explanation(winner: str, cv_results: list, task: str,
                      selection_metric: str, is_imbalanced: bool,
                      feature_importance: list, n_rows: int) -> str:
    if task == "regression":
        sorted_r = sorted(cv_results, key=lambda x: x["score"])
        best_fmt = f"MAE of {sorted_r[0]['score']:.2f}"
        others   = [f"{r['algorithm']} ({r['score']:.2f})" for r in sorted_r[1:]]
    else:
        sorted_r = sorted(cv_results, key=lambda x: -x["score"])
        best_fmt = f"{selection_metric} of {sorted_r[0]['score'] * 100:.1f}%"
        others   = [f"{r['algorithm']} ({r['score'] * 100:.1f}%)" for r in sorted_r[1:]]

    text = f"{winner} achieved the best {best_fmt}"
    if others:
        text += f", outperforming {' and '.join(others)}"
    text += "."
    if is_imbalanced:
        text += " F1-macro was used as the selection criterion because your dataset has class imbalance."
    if feature_importance:
        top3 = [f["feature"] for f in feature_importance[:3]]
        text += f" The most influential features are: {', '.join(top3)}."
    return text


def _build_prompt(winner, cv_results, task, selection_metric, is_imbalanced, feature_importance, n_rows):
    def _fmt_score(r):
        score_str = f"{r['score'] * 100:.2f}%" if task == "classification" else f"{r['score']:.4f}"
        folds = r.get("fold_scores", [])
        if folds:
            fold_str = ", ".join(f"{s * 100:.2f}%" if task == "classification" else f"{s:.4f}" for s in folds)
            variance = max(folds) - min(folds)
            var_str = f"{variance * 100:.2f}%" if task == "classification" else f"{variance:.4f}"
            return f"  {r['algorithm']}: {selection_metric} = {score_str}  [folds: {fold_str}, spread: {var_str}]"
        return f"  {r['algorithm']}: {selection_metric} = {score_str}"

    results_text = "\n".join(_fmt_score(r) for r in cv_results)
    algo_list = ", ".join(r["algorithm"] for r in cv_results)
    fi_text = "\n".join(
        f"  {i+1}. {f['feature']} ({f['importance']:.1f}%)"
        for i, f in enumerate(feature_importance[:5])
    ) if feature_importance else "  Not available"
    imbalance_note = (
        " The dataset has class imbalance, so F1-macro was used as the selection metric instead of accuracy."
        if is_imbalanced else ""
    )
    lower_is_better = task == "regression"
    return (
        f"You are an expert ML engineer explaining AutoML results to a data analyst.\n\n"
        f"Dataset: {n_rows:,} rows | Task: {task}{imbalance_note}\n"
        f"Selection metric: {selection_metric} ({'lower is better' if lower_is_better else 'higher is better'})\n"
        f"Algorithms tested (5-fold cross-validation):\n{results_text}\n\n"
        f"Winner: {winner}\n\nTop features by importance:\n{fi_text}\n\n"
        f"Analyze ALL models, not just the winner. Consider fold spread (high spread = unstable model).\n\n"
        f"Return ONLY a valid JSON object with exactly these 6 fields. No markdown, no code fences, no extra text — just the raw JSON:\n\n"
        f"{{\n"
        f'  "why_won": "2-3 sentences on why {winner} outperformed the others — reference the actual score margins and fold stability.",\n'
        f'  "score_analysis": "2-3 sentences comparing ALL {len(cv_results)} models — discuss how competitive the race was, which models were close, and what the fold spread reveals about stability.",\n'
        f'  "key_drivers": "2-3 sentences on what the top features reveal about prediction drivers and any patterns.",\n'
        f'  "recommendations": ["Specific next step referencing actual scores.", "Specific next step.", "Specific next step."],\n'
        f'  "model_comparison": [\n'
        f'    {{"algorithm": "<name>", "fitness_score": <0-100 integer rating for this dataset>, "reason": "1 sentence why this score."}}\n'
        f'    // one entry per algorithm: {algo_list}\n'
        f'  ],\n'
        f'  "actionable_insights": [\n'
        f'    {{"title": "3-5 word title", "detail": "1-2 specific sentences tied to the actual numbers."}},\n'
        f'    {{"title": "3-5 word title", "detail": "1-2 specific sentences tied to the actual numbers."}},\n'
        f'    {{"title": "3-5 word title", "detail": "1-2 specific sentences tied to the actual numbers."}}\n'
        f'  ]\n'
        f"}}\n\n"
        f"Be specific to the numbers provided. No generic filler. Avoid jargon."
    )


def _llm_explanation(api_key: str, winner: str, cv_results: list, task: str,
                     selection_metric: str, is_imbalanced: bool,
                     feature_importance: list, n_rows: int, provider: str = "gemini-2.5",
                     custom_base_url: str = "", custom_model: str = ""):
    import json as _json  # noqa: PLC0415
    prompt = _build_prompt(winner, cv_results, task, selection_metric, is_imbalanced, feature_importance, n_rows)
    raw_text = None
    try:
        if provider == "openai":
            import openai  # noqa: PLC0415
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=custom_model or "gpt-4o-mini", max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = resp.choices[0].message.content.strip()
        elif provider in ("groq", "groq-mixtral"):
            import openai  # noqa: PLC0415
            client = openai.OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
            default_model = "llama-3.1-8b-instant" if provider == "groq-mixtral" else "llama-3.3-70b-versatile"
            resp = client.chat.completions.create(
                model=custom_model or default_model, max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = resp.choices[0].message.content.strip()
        elif provider == "custom":
            import openai  # noqa: PLC0415
            if not custom_base_url or not custom_model:
                return None
            client = openai.OpenAI(api_key=api_key or "none", base_url=custom_base_url)
            resp = client.chat.completions.create(
                model=custom_model, max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = resp.choices[0].message.content.strip()
        elif provider in ("gemini-3.5", "gemini-2.5"):
            import urllib.request as _urllib  # noqa: PLC0415
            import json as _json2  # noqa: PLC0415
            default_model = "gemini-2.0-flash" if provider == "gemini-3.5" else "gemini-2.5-flash"
            _model = custom_model or default_model
            _url = f"https://generativelanguage.googleapis.com/v1beta/models/{_model}:generateContent?key={api_key}"
            _body = _json2.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
            _req = _urllib.Request(_url, data=_body, headers={"Content-Type": "application/json"})
            with _urllib.urlopen(_req, timeout=30) as _r:
                _data = _json2.loads(_r.read())
            raw_text = _data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            import anthropic  # noqa: PLC0415
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model=custom_model or "claude-haiku-4-5-20251001",
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = msg.content[0].text.strip()
    except Exception as e:
        print(f"[LLM error] provider={provider} error={e}")
        return None
    if raw_text is None:
        return None
    import re as _re
    cleaned = raw_text.strip()
    cleaned = _re.sub(r'^```[a-z]*\n?', '', cleaned)
    cleaned = _re.sub(r'\n?```$', '', cleaned).strip()
    try:
        parsed = _json.loads(cleaned)
        return {
            "why_won":            str(parsed.get("why_won", "")),
            "score_analysis":     str(parsed.get("score_analysis", "")),
            "key_drivers":        str(parsed.get("key_drivers", "")),
            "recommendations":    parsed.get("recommendations", []),
            "model_comparison":   parsed.get("model_comparison", []),
            "actionable_insights": parsed.get("actionable_insights", []),
        }
    except (_json.JSONDecodeError, Exception):
        return {"why_won": raw_text, "score_analysis": "", "key_drivers": "", "recommendations": []}
