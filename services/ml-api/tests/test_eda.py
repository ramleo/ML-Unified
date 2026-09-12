"""
EDA endpoint tests — derived from user-reported bugs.
See: ML-Iris/Conversations/EDA_Bug_Log.md for full context on each bug.

Profile half: distributions, readiness, narrative and edge cases.
The multivariate half (PCA, SPLOM, mutual information) is in
test_eda_multivariate.py.

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

# ── BUG-001: Distribution charts need raw_vals for frontend capture ────────────

class TestDistributions:

    def test_eda_distributions_present(self, eda_response):
        """Distributions dict exists and has at least one entry."""
        assert "distributions" in eda_response
        assert len(eda_response["distributions"]) > 0

    def test_eda_distributions_numeric_have_bins_and_counts(self, eda_response):
        """Each numeric distribution has both bins and counts."""
        for col, dist in eda_response["distributions"].items():
            if dist["type"] == "histogram":
                assert "bins" in dist,   f"{col}: missing bins"
                assert "counts" in dist, f"{col}: missing counts"
                assert len(dist["bins"]) == len(dist["counts"])

    def test_eda_stats_include_raw_vals(self, eda_response):
        """
        BUG-001 / BUG-002: Frontend uses raw_vals for Plotly native histogram
        (autobinx). If raw_vals is missing, capture falls back to pre-computed
        bins which produce giant bars for clustered data.
        """
        stats = eda_response["stats"]
        assert len(stats) > 0, "No numeric stats returned"
        for col, s in stats.items():
            assert "raw_vals" in s, f"{col}: raw_vals missing from stats"
            assert isinstance(s["raw_vals"], list)
            assert len(s["raw_vals"]) > 0, f"{col}: raw_vals is empty"

    def test_eda_low_variance_cols_returned(self, eda_response):
        """Backend flags near-constant columns for the ⚠ low variance label."""
        assert "low_variance_cols" in eda_response
        assert isinstance(eda_response["low_variance_cols"], list)

    def test_eda_low_variance_detects_constant_col(self, clustered_df):
        """BUG-002: Near-constant column must appear in low_variance_cols."""
        data = _post_eda(clustered_df)
        assert "clustered" in data["low_variance_cols"], (
            "constant column not flagged as low variance"
        )

    def test_eda_normal_col_not_flagged_low_variance(self, clustered_df):
        """Column with real spread must NOT be flagged as low variance."""
        data = _post_eda(clustered_df)
        assert "normal" not in data["low_variance_cols"]


# ── ML Readiness panel ─────────────────────────────────────────────────────────

class TestMLReadiness:

    def test_readiness_present(self, eda_response):
        assert "readiness" in eda_response
        assert len(eda_response["readiness"]) > 0

    def test_readiness_id_col_flagged_fail(self):
        """ID-like column (all unique, > 10 rows) must be verdict=fail."""
        rng = np.random.default_rng(9)
        n = 50
        df = pd.DataFrame({
            "unique_id": range(n),            # all unique — ID-like
            "value":     rng.normal(0, 1, n),
        })
        data = _post_eda(df)
        r = {c["name"]: c for c in data["readiness"]}
        assert r["unique_id"]["verdict"] == "fail", "ID column not flagged as fail"

    def test_readiness_constant_col_flagged_fail(self, eda_response):
        """Near-zero variance column must be verdict=fail."""
        r = {c["name"]: c for c in eda_response["readiness"]}
        assert r["constant"]["verdict"] == "fail"

    def test_readiness_clean_col_passes(self, eda_response):
        """Column with real variance and no issues should be verdict=pass."""
        r = {c["name"]: c for c in eda_response["readiness"]}
        assert r["age"]["verdict"] == "pass"

    def test_readiness_high_missing_flagged(self):
        """Column with >20% missing must be verdict=fail."""
        rng = np.random.default_rng(1)
        n = 100
        df = pd.DataFrame({
            "x": rng.normal(0, 1, n),
            "bad": [None] * 25 + list(rng.normal(0, 1, 75)),  # 25% missing
        })
        data = _post_eda(df)
        r = {c["name"]: c for c in data["readiness"]}
        assert r["bad"]["verdict"] == "fail"

    def test_readiness_moderate_missing_warns(self):
        """Column with 6-20% missing must be verdict=warn."""
        rng = np.random.default_rng(2)
        n = 100
        df = pd.DataFrame({
            "x":   rng.normal(0, 1, n),
            "mid": [None] * 10 + list(rng.normal(0, 1, 90)),  # 10% missing
        })
        data = _post_eda(df)
        r = {c["name"]: c for c in data["readiness"]}
        assert r["mid"]["verdict"] == "warn"


# ── Narrative ──────────────────────────────────────────────────────────────────

class TestNarrative:

    def test_narrative_present(self, eda_response):
        assert "narrative" in eda_response
        assert isinstance(eda_response["narrative"], str)
        assert len(eda_response["narrative"]) > 20

    def test_narrative_mentions_row_count(self, eda_response, mixed_df):
        """Narrative must reference the actual row count (after duplicates concat)."""
        n_rows = len(mixed_df)  # fixture already includes the 3 duplicate rows
        assert str(n_rows) in eda_response["narrative"] or \
               f"{n_rows:,}" in eda_response["narrative"]

    def test_narrative_mentions_quality(self, eda_response):
        assert "quality" in eda_response["narrative"].lower()


# ── Edge cases ─────────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_single_column_csv(self):
        df = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
        data = _post_eda(df)
        assert data["overview"]["cols"] == 1
        assert data["pca"] is None   # need ≥3 numeric cols
        assert data["splom"] is None # need ≥2 numeric cols

    def test_all_missing_column_handled(self):
        """Column with 100% missing values must not crash the endpoint."""
        df = pd.DataFrame({
            "a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "b": [None, None, None, None, None],
        })
        r = client.post("/eda", files={"file": ("t.csv", _csv_bytes(df), "text/csv")})
        assert r.status_code == 200

    def test_empty_csv_rejected(self):
        csv = b"col1,col2\n"  # header only, no rows
        r = client.post("/eda", files={"file": ("empty.csv", csv, "text/csv")})
        assert r.status_code == 400

    def test_non_csv_rejected(self):
        r = client.post("/eda", files={"file": ("img.png", b"\x89PNG", "image/png")})
        assert r.status_code == 400

    def test_quality_score_range(self, eda_response):
        """Quality score must always be 0–100."""
        qs = eda_response["quality_score"]
        assert 0 <= qs <= 100

