"""Helper functions for /automl/preprocess — imputation, encoding, feature selection."""
import logging

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import LabelEncoder, StandardScaler


def apply_imputation(df_feat, target_series, mv_num, mv_cat, num_cols, cat_cols):
    """Apply missing-value imputation in-place; returns updated (df_feat, target_series, cat_cols)."""

    def _impute_num(cols):
        nonlocal df_feat, target_series
        if not cols:
            return
        if mv_num == "drop":
            mask = df_feat[cols].notna().all(axis=1)
            df_feat = df_feat[mask]
            if target_series is not None:
                target_series = target_series.loc[df_feat.index]
        elif mv_num == "ffill":
            df_feat[cols] = df_feat[cols].ffill()
        elif mv_num == "bfill":
            df_feat[cols] = df_feat[cols].bfill()
        elif mv_num == "constant":
            df_feat[cols] = df_feat[cols].fillna(0)
        elif mv_num == "knn":
            from sklearn.impute import KNNImputer  # noqa: PLC0415
            df_feat[cols] = KNNImputer(n_neighbors=5).fit_transform(df_feat[cols])
        elif mv_num == "mice":
            from sklearn.experimental import enable_iterative_imputer  # noqa: PLC0415, F401
            from sklearn.impute import IterativeImputer  # noqa: PLC0415
            df_feat[cols] = IterativeImputer(max_iter=10, random_state=42).fit_transform(df_feat[cols])
        elif mv_num in ("mean", "median", "mode"):
            strategy = "most_frequent" if mv_num == "mode" else mv_num
            df_feat[cols] = SimpleImputer(strategy=strategy).fit_transform(df_feat[cols])

    def _impute_cat(cols):
        nonlocal df_feat, target_series
        if not cols:
            return
        if mv_cat == "drop":
            mask = df_feat[cols].notna().all(axis=1)
            df_feat = df_feat[mask]
            if target_series is not None:
                target_series = target_series.loc[df_feat.index]
        elif mv_cat == "ffill":
            df_feat[cols] = df_feat[cols].ffill()
        elif mv_cat == "bfill":
            df_feat[cols] = df_feat[cols].bfill()
        elif mv_cat == "constant":
            df_feat[cols] = df_feat[cols].fillna("Unknown")
        elif mv_cat in ("most_frequent", "mode"):
            df_feat[cols] = SimpleImputer(strategy="most_frequent").fit_transform(df_feat[cols])

    if mv_num or mv_cat:
        _impute_num(num_cols)
        cat_cols = df_feat.select_dtypes(exclude="number").columns.tolist()
        _impute_cat(cat_cols)

    return df_feat, target_series, cat_cols


def apply_encoding(df_feat, cat_cols, encode_method, ordinal_cols, target_series, _np):
    """Apply categorical encoding; returns (df_feat, ohe_cols_added)."""
    nominal_cols   = [c for c in cat_cols if c not in ordinal_cols]
    ohe_cols_added = 0

    if encode_method == "onehot" and nominal_cols:
        _cols_before_ohe = len(df_feat.columns)
        df_feat = pd.get_dummies(df_feat, columns=nominal_cols, drop_first=False)
        _bool_ohe = df_feat.select_dtypes(include="bool").columns.tolist()
        if _bool_ohe:
            df_feat[_bool_ohe] = df_feat[_bool_ohe].astype(_np.int8)
        ohe_cols_added = len(df_feat.columns) - _cols_before_ohe

    elif encode_method == "ordinal":
        cols_to_encode = ordinal_cols if ordinal_cols else cat_cols
        for c in cols_to_encode:
            if c in df_feat.columns:
                df_feat[c] = LabelEncoder().fit_transform(df_feat[c].astype(str))

    elif encode_method == "frequency" and cat_cols:
        for c in cat_cols:
            freq_map = df_feat[c].value_counts().to_dict()
            df_feat[c] = df_feat[c].map(freq_map)

    elif encode_method == "target" and cat_cols and target_series is not None:
        _apply_target_encoding(df_feat, cat_cols, target_series)

    return df_feat, ohe_cols_added


def _apply_target_encoding(df_feat, cat_cols, target_series):
    import numpy as _np_inner  # noqa: PLC0415
    from sklearn.model_selection import KFold as _KF  # noqa: PLC0415
    tgt = target_series.reindex(df_feat.index)
    if not pd.api.types.is_numeric_dtype(tgt):
        tgt = tgt.map({v: i for i, v in enumerate(tgt.unique())}).astype(float)
    else:
        tgt = tgt.astype(float)
    global_mean = float(tgt.mean())
    k_smooth    = 10
    for c in cat_cols:
        if c not in df_feat.columns:
            continue
        encoded = _np_inner.zeros(len(df_feat), dtype=float)
        idx_arr = df_feat.index.to_numpy()
        kf = _KF(n_splits=5, shuffle=True, random_state=42)
        pos_arr = _np_inner.arange(len(df_feat))
        for train_pos, val_pos in kf.split(pos_arr):
            train_idx = idx_arr[train_pos]
            val_idx   = idx_arr[val_pos]
            fold_tgt  = tgt.loc[train_idx]
            fold_col  = df_feat[c].loc[train_idx]
            stats = fold_col.groupby(fold_col).apply(
                lambda g: (len(g), float(fold_tgt.loc[g.index].mean()))
            )
            for val_i in val_idx:
                cat_val = df_feat[c].loc[val_i]
                if cat_val in stats.index:
                    cnt, mean_ = stats[cat_val]
                    smoothed = (cnt * mean_ + k_smooth * global_mean) / (cnt + k_smooth)
                else:
                    smoothed = global_mean
                pos = int(_np_inner.where(idx_arr == val_i)[0][0])
                encoded[pos] = smoothed
        df_feat[c] = encoded


def apply_feature_selection(df_feat, target_series, fs_method, top_k):
    """Run feature selection; returns df_feat with columns pruned."""
    import numpy as _np  # noqa: PLC0415
    try:
        leftover_non_num = df_feat.select_dtypes(exclude="number").columns.tolist()
        if leftover_non_num:
            df_feat = df_feat.drop(columns=leftover_non_num)
        num_X = df_feat.select_dtypes(include="number").fillna(0)
        k = min(top_k, len(num_X.columns))
        y_fs = target_series.reindex(df_feat.index) if target_series is not None else None

        if fs_method == "variance" and len(num_X.columns) > k:
            keep = num_X.var().nlargest(k).index.tolist()
            df_feat = df_feat[keep]

        elif fs_method == "correlation" and len(num_X.columns) > 1:
            corr  = num_X.corr().abs()
            upper = corr.where(_np.triu(_np.ones(corr.shape), k=1).astype(bool))
            to_drop = [c for c in upper.columns if any(upper[c] > 0.90)]
            df_feat = df_feat.drop(columns=to_drop, errors="ignore")
            remaining_num = df_feat.select_dtypes(include="number")
            if len(remaining_num.columns) > k:
                keep = remaining_num.var().nlargest(k).index.tolist()
                df_feat = df_feat[keep]

        elif fs_method == "rfe" and y_fs is not None and len(num_X.columns) >= k:
            from sklearn.feature_selection import RFE  # noqa: PLC0415
            from sklearn.ensemble import RandomForestClassifier as _RFC, RandomForestRegressor as _RFR  # noqa: PLC0415
            is_clf = y_fs.dtype == object or y_fs.nunique() < 20
            estimator = _RFC(n_estimators=50, random_state=42) if is_clf else _RFR(n_estimators=50, random_state=42)
            y_fit = LabelEncoder().fit_transform(y_fs.astype(str)) if is_clf else pd.to_numeric(y_fs, errors="coerce").fillna(0)
            rfe = RFE(estimator, n_features_to_select=k)
            rfe.fit(num_X, y_fit)
            keep = num_X.columns[rfe.support_].tolist()
            df_feat = df_feat[keep]

        elif fs_method == "kbest" and y_fs is not None and len(num_X.columns) >= k:
            from sklearn.feature_selection import SelectKBest, mutual_info_classif, mutual_info_regression  # noqa: PLC0415
            is_clf = y_fs.dtype == object or y_fs.nunique() < 20
            score_fn = mutual_info_classif if is_clf else mutual_info_regression
            y_fit = LabelEncoder().fit_transform(y_fs.astype(str)) if is_clf else pd.to_numeric(y_fs, errors="coerce").fillna(0)
            sel = SelectKBest(score_fn, k=k)
            sel.fit(num_X, y_fit)
            keep = num_X.columns[sel.get_support()].tolist()
            df_feat = df_feat[keep]

    except Exception as _fs_err:
        logging.warning("Feature selection failed: %s", _fs_err)

    return df_feat
