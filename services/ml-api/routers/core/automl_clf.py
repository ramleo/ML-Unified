"""Classification training helpers for the AutoML /train endpoint."""
import os

import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    RandomForestClassifier, GradientBoostingClassifier,
    ExtraTreesClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, f1_score, roc_auc_score,
    precision_score, recall_score, confusion_matrix as sk_confusion_matrix,
)
from sklearn.model_selection import (
    cross_val_score, StratifiedKFold, learning_curve,
)
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC

from routers.core.automl_helpers import (
    _cv_sample, _extract_feature_importances, _optuna_tune, _build_tuned_estimator,
    _rule_explanation, _llm_explanation,
)
from routers.core.shared import _detect_gpu


def run_classification(
    p, X, y, algorithm, selected_models, tune, n_trials,
    transformers, num_cols, cat_cols,
    XGBClassifier, LGBMClassifier, CatBoostClassifier,
    use_smote=True,
):
    from sklearn.preprocessing import LabelEncoder as _LE
    le    = _LE()
    y_enc = le.fit_transform(y.astype(str))

    automl_result = None
    _effective_algorithm = algorithm

    cls_counts = pd.Series(y_enc).value_counts()
    min_ratio  = float(cls_counts.min()) / len(y_enc)
    is_imbal   = min_ratio < 0.20
    sel_metric = "f1_macro" if is_imbal else "f1_weighted"
    sel_label  = "F1-macro" if is_imbal else "F1 (weighted)"
    cw         = "balanced" if is_imbal else None

    if algorithm == "AutoML":
        automl_result, estimator, _effective_algorithm = _automl_clf(
            p, X, y_enc, selected_models, tune, n_trials, transformers,
            is_imbal, sel_metric, sel_label, cw,
            XGBClassifier, LGBMClassifier, CatBoostClassifier,
        )
    else:
        estimator = _single_clf_estimator(
            algorithm, cw, XGBClassifier, LGBMClassifier, CatBoostClassifier,
        )

    from sklearn.model_selection import train_test_split as _tts
    preprocessor = ColumnTransformer(transformers, remainder="drop")
    split    = 0.2 if len(X) >= 10 else 0.1
    X_train, X_test, y_train, y_test = _tts(X, y_enc, test_size=split, random_state=42, stratify=y_enc)
    if automl_result:
        automl_result["n_train"] = len(X_train)
        automl_result["n_test"]  = len(X_test)

    # SMOTE: apply when imbalanced + minority class has >= 20 samples
    import pandas as _pd
    min_class_count = int(_pd.Series(y_train).value_counts().min())
    smote_applied = False
    if use_smote and is_imbal and min_class_count >= 20:
        try:
            from imblearn.over_sampling import SMOTE as _SMOTE
            from imblearn.pipeline import Pipeline as _ImbPipeline
            _k = min(5, min_class_count - 1)
            pipeline = _ImbPipeline([
                ("prep",  preprocessor),
                ("smote", _SMOTE(random_state=42, k_neighbors=_k)),
                ("model", estimator),
            ])
            smote_applied = True
        except ImportError:
            pipeline = Pipeline([("prep", preprocessor), ("model", estimator)])
    else:
        pipeline = Pipeline([("prep", preprocessor), ("model", estimator)])

    if automl_result:
        automl_result["smote_applied"] = smote_applied

    train_pct = (79 if (tune and automl_result) else 68 if automl_result else 20)
    p.update(train_pct, f"Training {_effective_algorithm} classifier{'  [+SMOTE]' if smote_applied else ''}…")
    pipeline.fit(X_train, y_train)
    p.update(82, "Evaluating on test set…")
    y_pred       = pipeline.predict(X_test)
    is_imbal_result = automl_result.get("is_imbalanced", False) if automl_result else False
    f1_w = f1_score(y_test, y_pred, average="weighted", zero_division=0)
    f1_m = f1_score(y_test, y_pred, average="macro",    zero_division=0)
    acc  = accuracy_score(y_test, y_pred)
    score        = f1_m if is_imbal_result else f1_w
    metric       = f"{score:.3f}"
    metric_label = "F1-macro" if is_imbal_result else "F1 (weighted)"
    extra_metrics = [{"label": "Accuracy", "value": f"{acc * 100:.1f}%"}]
    auc = None
    try:
        n_cls = len(set(y_enc))
        if n_cls == 2:
            proba = pipeline.predict_proba(X_test)[:, 1]
            auc   = roc_auc_score(y_test, proba)
        else:
            proba = pipeline.predict_proba(X_test)
            auc   = roc_auc_score(y_test, proba, multi_class="ovr", average="macro")
        extra_metrics.append({"label": "ROC-AUC", "value": f"{auc:.3f}"})
    except Exception:
        pass

    if automl_result:
        prec_w = precision_score(y_test, y_pred, average="weighted", zero_division=0)
        rec_w  = recall_score(y_test, y_pred, average="weighted", zero_division=0)
        wm = {
            "accuracy":    round(float(acc),    4),
            "f1_weighted": round(float(f1_w),   4),
            "precision":   round(float(prec_w), 4),
            "recall":      round(float(rec_w),  4),
        }
        if auc is not None:
            wm["roc_auc"] = round(float(auc), 4)
        automl_result["winner_metrics"] = wm
        automl_result["confusion_matrix"] = sk_confusion_matrix(y_test, y_pred).tolist()
        automl_result["class_names"] = [str(c) for c in le.classes_]

        X_cv, y_cv = _cv_sample(X, y_enc)
        _lc_folds  = 3 if len(X) > 5000 else 5
        automl_result["lc_cv_folds"] = _lc_folds
        try:
            p.update(83, "Computing learning curve…")
            lc_sizes, lc_train_sc, lc_val_sc = learning_curve(
                clone(pipeline), X_cv, y_cv,
                cv=StratifiedKFold(n_splits=_lc_folds, shuffle=True, random_state=42),
                train_sizes=[0.2, 0.4, 0.6, 0.8, 1.0], scoring=sel_metric, n_jobs=1,
            )
            automl_result["learning_curve"] = {
                "train_sizes":  [int(s) for s in lc_sizes],
                "train_scores": [round(float(s.mean()), 4) for s in lc_train_sc],
                "val_scores":   [round(float(s.mean()), 4) for s in lc_val_sc],
                "metric_label": sel_label, "cv_folds": _lc_folds,
            }
        except Exception as _lc_err:
            print(f"Learning curve failed: {_lc_err}", flush=True)
            automl_result["lc_skip_reason"] = "Could not generate — likely OOM or timeout on current resources"

        p.update(84, "Extracting feature importances…")
        automl_result["feature_importance"] = _extract_feature_importances(pipeline, num_cols, cat_cols)
        rule_exp = _rule_explanation(
            automl_result["winner"], automl_result["cv_results"], "classification",
            automl_result["selection_metric"], automl_result["is_imbalanced"],
            automl_result["feature_importance"], len(X),
        )
        app_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if app_key:
            p.update(86, "Generating AI explanation…")
            llm_exp = _llm_explanation(
                app_key, automl_result["winner"], automl_result["cv_results"],
                "classification", automl_result["selection_metric"],
                automl_result["is_imbalanced"], automl_result["feature_importance"], len(X),
            )
            automl_result["explanation"]        = llm_exp or {"why_won": rule_exp, "score_analysis": "", "key_drivers": "", "recommendations": []}
            automl_result["explanation_source"] = "app_key" if llm_exp else "rule"
        else:
            automl_result["explanation"]        = {"why_won": rule_exp, "score_analysis": "", "key_drivers": "", "recommendations": []}
            automl_result["explanation_source"] = "rule"
        automl_result["can_upgrade"] = automl_result["explanation_source"] == "rule"

    return {
        "le": le, "pipeline": pipeline, "metric": metric, "metric_label": metric_label,
        "extra_metrics": extra_metrics, "automl_result": automl_result,
        "effective_algorithm": _effective_algorithm,
    }


def _automl_clf(p, X, y_enc, selected_models, tune, n_trials, transformers,
                is_imbal, sel_metric, sel_label, cw,
                XGBClassifier, LGBMClassifier, CatBoostClassifier):
    cv_split = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    X_cv, y_cv = _cv_sample(X, y_enc)
    cv_results = []
    _pct_steps = [12, 26, 40, 55, 70]
    _model_idx = 0

    _CLF_MAP = {
        "Random Forest": lambda: RandomForestClassifier(n_estimators=100, random_state=42, class_weight=cw),
        "XGBoost":       lambda: XGBClassifier(n_estimators=100, random_state=42, eval_metric="logloss", verbosity=0),
        "LightGBM":      lambda: LGBMClassifier(n_estimators=100, random_state=42, class_weight=cw, verbose=-1),
        "CatBoost":      lambda: CatBoostClassifier(iterations=100, random_seed=42, verbose=0),
        "Extra Trees":   lambda: ExtraTreesClassifier(n_estimators=100, random_state=42, class_weight=cw),
        "Decision Tree": lambda: __import__("sklearn.tree", fromlist=["DecisionTreeClassifier"]).DecisionTreeClassifier(random_state=42, class_weight=cw),
        "KNN":           lambda: KNeighborsClassifier(n_neighbors=5),
        "Logistic Regression": lambda: LogisticRegression(max_iter=1000, random_state=42, class_weight=cw),
        "SVM":           lambda: SVC(kernel="rbf", probability=True, class_weight=cw, random_state=42),
        "Naive Bayes":   lambda: GaussianNB(var_smoothing=1e-2),
        "Gradient Boosting": lambda: GradientBoostingClassifier(n_estimators=100, random_state=42),
        "AdaBoost":      lambda: __import__("sklearn.ensemble", fromlist=["AdaBoostClassifier"]).AdaBoostClassifier(n_estimators=100, random_state=42),
    }

    for name, mk_est in _CLF_MAP.items():
        if name not in selected_models:
            continue
        p.update(_pct_steps[_model_idx % 5], f"Testing {name} (5-fold CV)…")
        _model_idx += 1
        try:
            _pl    = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")), ("model", mk_est())])
            _folds = cross_val_score(_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric)
            cv_results.append({"algorithm": name, "score": round(float(_folds.mean()), 4), "fold_scores": [round(float(s), 4) for s in _folds]})
        except Exception as _e:
            print(f"{name} CV failed: {_e}", flush=True)

    if not cv_results:
        raise RuntimeError("All selected models failed CV")

    winner = max(cv_results, key=lambda r: r["score"])["algorithm"]
    automl_result = {
        "winner": winner, "selection_metric": sel_label, "is_imbalanced": is_imbal,
        "n_rows": len(X), "n_input_cols": len(X.columns), "cv_results": cv_results,
        "task": "classification", "gpu": _detect_gpu(),
    }
    estimator = _CLF_MAP.get(winner, lambda: RandomForestClassifier(n_estimators=100, random_state=42, class_weight=cw))()

    if tune:
        p.update(65, f"Winner: {winner}. Tuning with Optuna ({n_trials} trials)…")
        try:
            _best_params, _best_val = _optuna_tune(
                winner, "classification", X_cv, y_cv, transformers, cv_split, n_trials, is_imbal,
                lambda t, s: p.update(65 + int(t / n_trials * 13), f"Optuna trial {t}/{n_trials} — best {sel_label}: {s:.4f}"),
            )
            estimator = _build_tuned_estimator(winner, "classification", _best_params, is_imbal)
            automl_result["optuna_params"]     = _best_params
            automl_result["optuna_best_score"] = round(_best_val, 4)
            automl_result["optuna_n_trials"]   = n_trials
            p.update(78, f"Tuning done. Training {winner} with best params…")
        except Exception as _oe:
            print(f"Optuna tuning failed, using default params: {_oe}", flush=True)
            p.update(78, f"Tuning failed — using default {winner} params…")
    else:
        p.update(65, f"Winner: {winner}. Training on full dataset…")

    return automl_result, estimator, winner


def _single_clf_estimator(algorithm, cw, XGBClassifier, LGBMClassifier, CatBoostClassifier):
    if algorithm == "XGBoost":
        return XGBClassifier(n_estimators=100, random_state=42, eval_metric="logloss", verbosity=0)
    if algorithm == "LightGBM":
        return LGBMClassifier(n_estimators=100, random_state=42, verbose=-1)
    if algorithm == "CatBoost":
        return CatBoostClassifier(iterations=100, random_seed=42, verbose=0)
    if algorithm == "Random Forest":
        return RandomForestClassifier(n_estimators=100, random_state=42)
    return GradientBoostingClassifier(n_estimators=100, random_state=42)
