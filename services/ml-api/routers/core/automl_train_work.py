"""Orchestrates the /train SSE stream — delegates to clf/reg/clustering helpers."""
import json
import os

import pandas as pd
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline

from routers.core.automl_clf import run_classification
from routers.core.automl_reg import run_regression
from routers.core.shared import _upload_model_to_hf, MODELS, SCHEMA_DIR, MODEL_DIR
import joblib


def build_work_fn(
    X, y, task, algorithm, accent, model_id, model_name, target_col,
    fe_transformer, pre_fe_cols, pre_fe_sample, n_clusters,
    tune, n_trials, selected_models, num_cols, cat_cols, transformers,
):
    """Return the _work(p) closure to pass to StreamingTask.stream()."""

    _task        = task
    _algorithm   = algorithm
    _accent      = accent
    _model_id    = model_id
    _model_name  = model_name
    _target_col  = target_col
    _fe_tfm      = fe_transformer
    _pre_fe_cols_  = pre_fe_cols
    _pre_fe_sample_= pre_fe_sample
    _n_clusters  = n_clusters
    _tune        = tune
    _n_trials    = n_trials
    _selected_models = selected_models
    _y           = y

    def _work(p):  # noqa: C901
        from xgboost import XGBClassifier, XGBRegressor          # noqa: PLC0415
        from lightgbm import LGBMClassifier, LGBMRegressor        # noqa: PLC0415
        from catboost import CatBoostClassifier, CatBoostRegressor  # noqa: PLC0415

        le            = None
        plot_data     = None
        extra_metrics = []
        automl_result = None
        _actuals_data = None

        p.update(5, "Preparing feature matrix…")

        if _task == "clustering":
            from sklearn.compose import ColumnTransformer as _CT  # noqa: PLC0415
            preprocessor = _CT(transformers, remainder="drop")
            _cluster_result = _run_clustering(p, X, preprocessor, _algorithm, _n_clusters)
            metric       = _cluster_result["metric"]
            metric_label = _cluster_result["metric_label"]
            plot_data    = _cluster_result["plot_data"]
            pipeline     = _cluster_result["pipeline"]
            _effective_algorithm = _algorithm

        elif _task == "classification":
            _clf_result = run_classification(
                p, X, _y, _algorithm, _selected_models, _tune, _n_trials,
                transformers, num_cols, cat_cols,
                XGBClassifier, LGBMClassifier, CatBoostClassifier,
            )
            le               = _clf_result["le"]
            pipeline         = _clf_result["pipeline"]
            metric           = _clf_result["metric"]
            metric_label     = _clf_result["metric_label"]
            extra_metrics    = _clf_result["extra_metrics"]
            automl_result    = _clf_result["automl_result"]
            _actuals_data    = None
            _effective_algorithm = _clf_result["effective_algorithm"]

        else:  # regression
            _reg_result = run_regression(
                p, X, _y, _algorithm, _selected_models, _tune, _n_trials,
                transformers, num_cols, cat_cols,
                XGBRegressor, LGBMRegressor, CatBoostRegressor,
            )
            le               = None
            pipeline         = _reg_result["pipeline"]
            metric           = _reg_result["metric"]
            metric_label     = _reg_result["metric_label"]
            extra_metrics    = _reg_result["extra_metrics"]
            automl_result    = _reg_result["automl_result"]
            _actuals_data    = _reg_result["actuals_data"]
            _effective_algorithm = _reg_result["effective_algorithm"]

        p.update(88, "Building schema…")
        feature_cols = [c for c in _pre_fe_cols_ if c in X.columns]
        fields: list = []
        sample: dict = {}
        for col in feature_cols:
            is_cat = not pd.api.types.is_numeric_dtype(X[col]) or X[col].nunique() <= 15
            if is_cat:
                opts     = [{"value": str(v), "label": str(v)} for v in sorted(X[col].dropna().unique())]
                col_vals = X[col].dropna()
                n_col    = len(col_vals)
                cat_freq = {str(v): round(int((col_vals == v).sum()) / n_col, 6) for v in col_vals.unique()} if n_col else {}
                fields.append({"name": col, "label": col, "type": "select", "options": opts, "cat_freq": cat_freq})
                mode = X[col].mode()
                sample[col] = str(mode[0]) if not mode.empty else ""
            else:
                cmin = round(float(X[col].min()), 4)
                cmax = round(float(X[col].max()), 4)
                rng  = cmax - cmin
                step = max(round(rng / 100, 4) if rng > 0 else 1.0, 0.0001)
                fields.append({"name": col, "label": col, "type": "number",
                               "min": cmin, "max": cmax, "step": step})
                sample[col] = round(float(X[col].median()), 4)

        output_meta: dict = {"type": _task}
        if _task == "clustering":
            output_meta["n_clusters"] = _n_clusters
        else:
            output_meta["target_col"] = _target_col
        if _task == "classification" and le is not None:
            output_meta["class_names"] = [str(c) for c in le.classes_]

        schema = {
            "id":          _model_id,
            "title":       _model_name,
            "description": f"Auto-trained {_task} model using {_effective_algorithm}.",
            "task":        _task,
            "accent":      _accent,
            "model":       _effective_algorithm,
            "metric":      metric,
            "metricLabel": metric_label,
            "id_cols":      [],
            "ensure_cols":  [],
            "pre_fe_cols":   _pre_fe_cols_,
            "pre_fe_sample": _pre_fe_sample_,
            "fields":        fields,
            "sample":        sample,
            "output":      output_meta,
        }

        p.update(93, "Saving model to disk…")
        with open(os.path.join(SCHEMA_DIR, f"{_model_id}.json"), "w") as f:
            json.dump(schema, f, indent=2)
        joblib.dump(pipeline, os.path.join(MODEL_DIR, f"{_model_id}_pipeline.pkl"))
        joblib.dump(_fe_tfm, os.path.join(MODEL_DIR, f"{_model_id}_fe.pkl"))
        if le is not None:
            joblib.dump(le, os.path.join(MODEL_DIR, f"{_model_id}_labels.pkl"))
        if _actuals_data is not None:
            _act_path = os.path.join(MODEL_DIR, f"{_model_id}_actuals.json")
            with open(_act_path, "w") as _af:
                json.dump(_actuals_data, _af)
            print(f"ACTUALS: saved {_act_path} ({len(_actuals_data.get('actual', []))} pts)", flush=True)
        else:
            print(f"ACTUALS: _actuals_data is None for {_model_id} (task={_task})", flush=True)

        MODELS[_model_id] = {
            "pipeline": pipeline,
            "le":       le,
            "classes":  le.classes_.tolist() if le is not None else None,
            "schema":   schema,
            "fe":       _fe_tfm,
            "actuals":  _actuals_data,
        }

        resp = {
            "id":           _model_id,
            "title":        _model_name,
            "metric":       metric,
            "metricLabel":  metric_label,
            "extraMetrics": extra_metrics,
            "accent":       _accent,
        }
        if plot_data is not None:
            resp["plot_data"]  = plot_data
            resp["n_clusters"] = _n_clusters
        if automl_result is not None:
            resp["automl"] = automl_result

        p.finish(result=resp)
        import threading as _threading  # noqa: PLC0415
        _threading.Thread(target=_upload_model_to_hf, args=(_model_id,), daemon=True).start()

    return _work


def _run_clustering(p, X, preprocessor, algorithm, n_clusters):
    p.update(10, "Fitting preprocessing…")
    preprocessor.fit(X)
    X_prep = preprocessor.transform(X)
    n_comp = min(2, X_prep.shape[1])

    if algorithm == "t-SNE":
        p.update(20, "Running t-SNE (this may take a while)…")
        reducer = TSNE(n_components=n_comp, random_state=42,
                       perplexity=min(30, max(5, len(X) // 10)))
        coords  = reducer.fit_transform(X_prep)
        labels  = [-1] * len(X)
        metric, metric_label = "N/A", "Visualization"
        pipeline = Pipeline([("prep", preprocessor)])
    elif algorithm == "PCA":
        p.update(20, "Running PCA…")
        reducer = PCA(n_components=n_comp)
        coords  = reducer.fit_transform(X_prep)
        labels  = [-1] * len(X)
        ev      = reducer.explained_variance_ratio_
        metric, metric_label = f"{sum(ev)*100:.1f}%", "Variance Explained"
        pipeline = Pipeline([("prep", preprocessor)])
    elif algorithm == "DBSCAN":
        p.update(20, "Running DBSCAN…")
        db      = DBSCAN(eps=0.5, min_samples=5)
        labels  = db.fit_predict(X_prep).tolist()
        n_found = len(set(lbl for lbl in labels if lbl >= 0))
        sil     = silhouette_score(X_prep, labels) if n_found > 1 and len(set(labels)) > 1 else 0.0
        metric, metric_label = f"{sil:.2f}", "Silhouette"
        pca_viz = PCA(n_components=n_comp)
        coords  = pca_viz.fit_transform(X_prep)
        pipeline = Pipeline([("prep", preprocessor)])
    else:  # K-Means
        p.update(20, f"Running K-Means (k={n_clusters})…")
        km       = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        pipeline = Pipeline([("prep", preprocessor), ("model", km)])
        pipeline.fit(X)
        labels   = pipeline.predict(X).tolist()
        sil      = silhouette_score(X_prep, labels) if n_clusters > 1 and len(set(labels)) > 1 else 0.0
        metric, metric_label = f"{sil:.2f}", "Silhouette"
        pca_viz  = PCA(n_components=n_comp)
        coords   = pca_viz.fit_transform(X_prep)

    p.update(80, "Building cluster plot…")
    if n_comp == 1:
        plot_data = [{"x": round(float(coords[i, 0]), 4), "y": 0.0, "cluster": int(labels[i])} for i in range(len(coords))]
    else:
        plot_data = [{"x": round(float(coords[i, 0]), 4), "y": round(float(coords[i, 1]), 4), "cluster": int(labels[i])} for i in range(len(coords))]

    return {"metric": metric, "metric_label": metric_label, "plot_data": plot_data, "pipeline": pipeline}
