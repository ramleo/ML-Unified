"""FeatureEngineeringTransformer — sklearn-compatible transformer for custom FE."""
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import PowerTransformer


class FeatureEngineeringTransformer(BaseEstimator, TransformerMixin):
    """Fit on train data only, transform both train and test."""

    def __init__(self, fe_config=None):
        self.fe_config = fe_config or {}

    def fit(self, X, y=None):
        import numpy as np
        cfg = self.fe_config
        X_df = pd.DataFrame(X) if not isinstance(X, pd.DataFrame) else X.copy()

        self._bin_edges_       = {}
        self._yeo_transformers_= {}
        self._iqr_bounds_      = {}
        self._rank_vals_       = {}
        self._date_mins_       = {}
        self._poly_transformer_= None
        self._poly_cols_       = []

        for col, transforms in cfg.get("numeric", {}).items():
            if col not in X_df.columns or not isinstance(transforms, dict):
                continue
            series = X_df[col].dropna()
            if series.empty:
                continue

            bin_method = transforms.get("bin", "none")
            bin_n      = int(transforms.get("bin_n", 5) or 5)
            if bin_method == "quantile":
                try:
                    _, edges = pd.qcut(series, q=bin_n, retbins=True, duplicates="drop")
                    self._bin_edges_[col] = edges
                except Exception:
                    pass
            elif bin_method == "equal_width":
                try:
                    _, edges = pd.cut(series, bins=bin_n, retbins=True)
                    self._bin_edges_[col] = edges
                except Exception:
                    pass
            elif bin_method == "custom":
                try:
                    raw = str(transforms.get("bin_custom", "") or "")
                    edges = sorted(float(x.strip()) for x in raw.split(",") if x.strip())
                    if len(edges) >= 2:
                        self._bin_edges_[col] = edges
                except Exception:
                    pass

            if transforms.get("yeo_johnson"):
                try:
                    pt = PowerTransformer(method="yeo-johnson")
                    pt.fit(series.values.reshape(-1, 1))
                    self._yeo_transformers_[col] = pt
                except Exception:
                    pass

            if transforms.get("outlier_flag"):
                q1, q3 = float(series.quantile(0.25)), float(series.quantile(0.75))
                iqr    = q3 - q1
                self._iqr_bounds_[col] = (q1 - 1.5 * iqr, q3 + 1.5 * iqr)

            if transforms.get("rank"):
                self._rank_vals_[col] = np.sort(series.values)

        for col, dcfg in cfg.get("dates", {}).items():
            if col not in X_df.columns or not isinstance(dcfg, dict):
                continue
            if dcfg.get("days_since_min"):
                try:
                    self._date_mins_[col] = pd.to_datetime(X_df[col], errors="coerce").min()
                except Exception:
                    pass

        poly_cols = [c for c in cfg.get("poly_cols", []) if c in X_df.columns]
        if len(poly_cols) >= 2:
            try:
                from sklearn.preprocessing import PolynomialFeatures
                pf = PolynomialFeatures(degree=2, interaction_only=True, include_bias=False)
                pf.fit(X_df[poly_cols].fillna(0))
                self._poly_transformer_ = pf
                self._poly_cols_        = poly_cols
            except Exception:
                pass

        return self

    def transform(self, X):
        import numpy as np
        cfg  = self.fe_config
        X_df = pd.DataFrame(X) if not isinstance(X, pd.DataFrame) else X.copy()

        # 1. Missing indicators (before any other transform)
        for col, transforms in cfg.get("numeric", {}).items():
            if col not in X_df.columns or not isinstance(transforms, dict):
                continue
            if transforms.get("missing_flag"):
                X_df[f"{col}_was_missing"] = X_df[col].isna().astype("int8")

        # 2. Numeric transforms
        for col, transforms in cfg.get("numeric", {}).items():
            if col not in X_df.columns or not isinstance(transforms, dict):
                continue
            if transforms.get("log1p"):
                X_df[f"{col}_log"] = np.log1p(X_df[col].clip(lower=0))
            if transforms.get("sqrt"):
                X_df[f"{col}_sqrt"] = np.sqrt(X_df[col].clip(lower=0))
            if transforms.get("yeo_johnson") and col in self._yeo_transformers_:
                try:
                    pt   = self._yeo_transformers_[col]
                    vals = pt.transform(X_df[col].fillna(0).values.reshape(-1, 1)).flatten()
                    X_df[f"{col}_yj"] = vals
                except Exception:
                    pass
            if transforms.get("rank") and col in self._rank_vals_:
                try:
                    train_sorted = self._rank_vals_[col]
                    n            = len(train_sorted)
                    raw          = X_df[col].values
                    ranks        = np.searchsorted(train_sorted, raw, side="left") / max(n, 1)
                    X_df[f"{col}_rank"] = np.where(pd.isna(X_df[col]), np.nan, ranks)
                except Exception:
                    pass

        # 3. Binning (using fitted edges)
        for col, edges in self._bin_edges_.items():
            if col not in X_df.columns:
                continue
            try:
                X_df[f"{col}_bin"] = pd.cut(
                    X_df[col], bins=edges, labels=False, include_lowest=True
                )
            except Exception:
                pass

        # 4. Outlier flags
        for col, (lower, upper) in self._iqr_bounds_.items():
            if col not in X_df.columns:
                continue
            X_df[f"{col}_is_outlier"] = (
                (X_df[col] < lower) | (X_df[col] > upper)
            ).astype("int8")

        # 5. Date extraction
        for col, dcfg in cfg.get("dates", {}).items():
            if col not in X_df.columns or not isinstance(dcfg, dict):
                continue
            try:
                dt = pd.to_datetime(X_df[col], errors="coerce")
                if dcfg.get("year"):
                    X_df[f"{col}_year"] = dt.dt.year
                if dcfg.get("month"):
                    X_df[f"{col}_month"] = dt.dt.month
                if dcfg.get("day"):
                    X_df[f"{col}_day"] = dt.dt.day
                if dcfg.get("dow"):
                    X_df[f"{col}_dow"] = dt.dt.dayofweek
                if dcfg.get("quarter"):
                    X_df[f"{col}_quarter"] = dt.dt.quarter
                if dcfg.get("is_weekend"):
                    X_df[f"{col}_is_weekend"] = (dt.dt.dayofweek >= 5).astype("int8")
                if dcfg.get("days_since_min") and col in self._date_mins_:
                    X_df[f"{col}_days_since_min"] = (dt - self._date_mins_[col]).dt.days
                if dcfg.get("cyclical"):
                    if dcfg.get("month"):
                        m = dt.dt.month
                        X_df[f"{col}_month_sin"] = np.sin(2 * np.pi * m / 12)
                        X_df[f"{col}_month_cos"] = np.cos(2 * np.pi * m / 12)
                    if dcfg.get("dow"):
                        d = dt.dt.dayofweek
                        X_df[f"{col}_dow_sin"] = np.sin(2 * np.pi * d / 7)
                        X_df[f"{col}_dow_cos"] = np.cos(2 * np.pi * d / 7)
                if not dcfg.get("keep_original"):
                    X_df = X_df.drop(columns=[col], errors="ignore")
            except Exception:
                pass

        # 6. Derived features
        for d in cfg.get("derived", []):
            col_a = d.get("col_a")
            col_b = d.get("col_b")
            op = d.get("op")
            if not col_a or not col_b or col_a not in X_df.columns or col_b not in X_df.columns:
                continue
            try:
                if op == "ratio":
                    X_df[f"{col_a}_div_{col_b}"] = X_df[col_a] / (X_df[col_b].replace(0, np.nan) + 1e-9)
                elif op == "diff":
                    X_df[f"{col_a}_minus_{col_b}"] = X_df[col_a] - X_df[col_b]
            except Exception:
                pass

        # 7. Polynomial interactions
        if self._poly_transformer_ is not None:
            try:
                from itertools import combinations as _comb
                avail = [c for c in self._poly_cols_ if c in X_df.columns]
                if len(avail) == len(self._poly_cols_):
                    poly_arr    = X_df[avail].fillna(0).to_numpy()
                    poly_out    = self._poly_transformer_.transform(poly_arr)
                    inter_names = [f"{a} {b}" for a, b in _comb(avail, 2)]
                    n_inter     = len(inter_names)
                    inter_vals  = poly_out[:, -n_inter:]
                    inter_df    = pd.DataFrame(inter_vals, columns=inter_names, index=X_df.index)
                    X_df        = pd.concat([X_df, inter_df], axis=1)
            except Exception as _poly_exc:
                print(f"Polynomial FE transform failed: {_poly_exc}", flush=True)

        return X_df
