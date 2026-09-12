"""
EDA multivariate tests — PCA, scatter-plot matrix, mutual information.
See: ML-Iris/Conversations/EDA_Bug_Log.md for full context on each bug.

Each test is tagged with the bug ID it covers.
"""
import io
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from app import app  # noqa: E402

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def _post_eda(df: pd.DataFrame):
    csv = _csv_bytes(df)
    r = client.post("/eda", files={"file": ("test.csv", csv, "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def mixed_df():
    """A dataset with numeric + categorical cols, missing values, duplicates."""
    rng = np.random.default_rng(42)
    n = 120
    df = pd.DataFrame({
        "id":       range(n),                                    # ID-like (all unique)
        "age":      rng.integers(18, 80, n).astype(float),
        "salary":   rng.normal(50000, 15000, n),
        "score":    rng.uniform(0, 1, n),
        "constant": np.ones(n),                                  # near-zero variance
        "target":   rng.choice([0, 1], n),                      # binary low-cardinality
        "category": rng.choice(["A", "B", "C"], n),
        "name":     [f"person_{i}" for i in range(n)],          # high-cardinality cat
    })
    # Add missing values
    df.loc[rng.choice(n, 10, replace=False), "salary"] = np.nan
    # Add duplicates
    df = pd.concat([df, df.iloc[:3]], ignore_index=True)
    return df


@pytest.fixture(scope="module")
def eda_response(mixed_df):
    return _post_eda(mixed_df)


@pytest.fixture(scope="module")
def clustered_df():
    """Dataset where most numeric cols have very low variance (BUG-002)."""
    rng = np.random.default_rng(0)
    n = 80
    return pd.DataFrame({
        # std/range well below 5% threshold
        "clustered": 5.0 + rng.uniform(-1e-5, 1e-5, n),
        "normal":    rng.normal(50, 10, n),
        "category":  rng.choice(["X", "Y"], n),
    })


# Split out of the original 394-line test_eda.py when the ml-eda service was
# folded into ml-api (2026-09-12). Same tests, same fixtures, no behaviour
# change — the file was over the 350-line threshold at which this project
# modularises before touching a file.

# ── BUG-003 / BUG-004: PCA result structure and color map ─────────────────────

class TestPCA:

    def test_eda_pca_result_structure(self, eda_response):
        """
        BUG-003: PCA result must have coords, explained_variance, cat_color_map.
        Missing cat_color_map caused frontend to pass string arrays to Plotly
        colorscale → silent render failure → blank chart.
        """
        pca = eda_response.get("pca")
        assert pca is not None, "PCA result missing"
        assert "coords" in pca
        assert "explained_variance" in pca
        assert "cat_color_map" in pca
        assert "cat_cols" in pca

    def test_eda_pca_coords_are_3d(self, eda_response):
        """Every PCA coordinate must have exactly 3 components."""
        pca = eda_response["pca"]
        for i, row in enumerate(pca["coords"]):
            assert len(row) == 3, f"Row {i} has {len(row)} dims, expected 3"

    def test_eda_pca_explained_variance_sums_to_reasonable(self, eda_response):
        """Explained variance values must be percentages summing to ≤ 100."""
        ev = eda_response["pca"]["explained_variance"]
        assert len(ev) == 3
        assert all(0 <= v <= 100 for v in ev), f"Bad variance values: {ev}"
        assert sum(ev) <= 100.5  # small float tolerance

    def test_eda_pca_cat_color_map_values_are_strings(self, eda_response):
        """
        BUG-003: cat_color_map values must be string lists so the frontend can
        convert them to integer codes via unique.indexOf(). If they were numeric,
        the old direct-color approach might work; if they are non-string objects,
        indexOf mapping could break.
        """
        pca = eda_response["pca"]
        for col, vals in pca["cat_color_map"].items():
            assert isinstance(vals, list), f"{col}: color vals not a list"
            assert len(vals) == len(pca["coords"]), (
                f"{col}: color vals length {len(vals)} != coords {len(pca['coords'])}"
            )
            assert all(isinstance(v, str) for v in vals), (
                f"{col}: color vals contain non-string entries"
            )

    def test_eda_pca_cat_color_map_all_cols(self, eda_response):
        """
        BUG-004: Every column listed in cat_cols must have an entry in
        cat_color_map. Missing entries meant only the first column's dropdown
        selection actually worked.
        """
        pca = eda_response["pca"]
        for col in pca["cat_cols"]:
            assert col in pca["cat_color_map"], (
                f"cat_col '{col}' missing from cat_color_map"
            )

    def test_eda_pca_includes_low_cardinality_numeric(self, eda_response):
        """
        BUG-004: Low-cardinality numeric cols (like binary target 0/1) must appear
        in cat_cols so they show up in the "Color by" dropdown alongside categoricals.
        """
        pca = eda_response["pca"]
        # 'target' has 2 unique values — must be a color option
        assert "target" in pca["cat_cols"], (
            "binary 'target' column not in PCA color options"
        )


# ── BUG-003 edge case: dataset with no categorical columns ────────────────────

class TestPCANoCatCols:

    def test_eda_pca_no_cat_cols(self):
        """PCA must still return a valid result when no categorical columns exist."""
        rng = np.random.default_rng(7)
        df = pd.DataFrame({
            "a": rng.normal(0, 1, 100),
            "b": rng.normal(5, 2, 100),
            "c": rng.normal(-3, 0.5, 100),
        })
        data = _post_eda(df)
        assert data["pca"] is not None
        assert data["pca"]["cat_color_map"] == {}
        assert data["pca"]["cat_cols"] == []


# ── SPLOM result ───────────────────────────────────────────────────────────────

class TestSPLOM:

    def test_splom_present(self, eda_response):
        assert "splom" in eda_response
        assert eda_response["splom"] is not None

    def test_splom_cols_aligned(self, eda_response):
        """All data arrays in splom must have the same length (aligned rows)."""
        splom = eda_response["splom"]
        lengths = {col: len(vals) for col, vals in splom["data"].items()}
        assert len(set(lengths.values())) == 1, (
            f"SPLOM data arrays have different lengths: {lengths}"
        )

    def test_splom_color_map_aligned(self, eda_response):
        """color_map values must match splom row count (same sample index)."""
        splom = eda_response["splom"]
        n = splom["n"]
        for col, vals in splom["color_map"].items():
            assert len(vals) == n, (
                f"color_map['{col}'] length {len(vals)} != splom n={n}"
            )

    def test_splom_capped_at_8_cols(self):
        """SPLOM must not exceed 8 numeric columns."""
        rng = np.random.default_rng(3)
        n = 60
        df = pd.DataFrame({f"col_{i}": rng.normal(i, 1, n) for i in range(12)})
        data = _post_eda(df)
        assert len(data["splom"]["cols"]) <= 8


# ── Mutual Information ─────────────────────────────────────────────────────────

class TestMutualInformation:

    def test_mi_present(self, eda_response):
        assert "mi" in eda_response
        mi = eda_response["mi"]
        assert mi is not None
        assert "labels" in mi
        assert "matrix" in mi

    def test_mi_matrix_diagonal_is_one(self, eda_response):
        """
        Normalized MI of a column with itself must be 1.0.
        Exception: a constant column has H(X)=0, so MI(X,X)/H(X) is undefined
        and we normalise to 0.0 by convention — skip those diagonals.
        """
        mi = eda_response["mi"]
        mat = mi["matrix"]
        for i, label in enumerate(mi["labels"]):
            if mat[i][i] == 0.0:
                continue  # constant column, MI undefined — see BUG-002 notes
            assert abs(mat[i][i] - 1.0) < 0.01, (
                f"Diagonal [{i}][{i}] (col='{label}') = {mat[i][i]}, expected ~1.0"
            )

    def test_mi_matrix_symmetric(self, eda_response):
        """MI(X, Y) == MI(Y, X) — matrix must be symmetric."""
        mi = eda_response["mi"]
        mat = mi["matrix"]
        n = len(mat)
        for i in range(n):
            for j in range(i + 1, n):
                assert abs(mat[i][j] - mat[j][i]) < 0.01, (
                    f"MI not symmetric at [{i}][{j}]: {mat[i][j]} vs {mat[j][i]}"
                )

    def test_mi_values_normalized_0_to_1(self, eda_response):
        """All MI values must be in [0, 1]."""
        mi = eda_response["mi"]
        for row in mi["matrix"]:
            for v in row:
                assert 0.0 <= v <= 1.01, f"MI value out of range: {v}"


