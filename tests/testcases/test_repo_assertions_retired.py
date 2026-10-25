"""Documented cases whose subject no longer exists here, or that belong to another
lane (a live API, a rendered page). Kept as explicit skips so the registry stays
honest about what is covered and what is dead — never silently dropped.
"""
from __future__ import annotations

import pytest

from conftest import RETIRED


@RETIRED
def test_tc_early_050_run_sh_preflight_docker_check():
    """TC-EARLY-050: run.sh exits with a friendly error when Docker is not running"""


@RETIRED
def test_tc_early_051_pipeline_runs_without_claude_cli():
    """TC-EARLY-051: auto_pipeline.py executes standalone, no `claude` CLI invocation"""


@RETIRED
def test_tc_early_055_feature_ranges_domain_bounds():
    """TC-EARLY-055: feature ranges use domain-informed bounds"""


@RETIRED
def test_tc_early_060_feature_importance_normalized():
    """TC-EARLY-060: feature_importance.json contains normalized values 0-1"""


@RETIRED
def test_tc_p1_039_pydantic_field_alias_in_generated_app():
    """TC-P1-039: generated app.py uses Field(alias) for column names with spaces"""


@RETIRED
def test_tc_p1_074_generated_app_py_compiles():
    """TC-P1-074: generated app.py has no syntax errors"""


@RETIRED
def test_tc_p1_076_target_column_prompt_loops():
    """TC-P1-076: target column prompt re-prompts on empty input"""


@RETIRED
def test_tc_p1_079_pip_install_no_cache_dir():
    """TC-P1-079: pip install uses --no-cache-dir"""


@RETIRED
def test_tc_p1_082_metrics_json_has_target():
    """TC-P1-082: metrics.json includes a `target` field for regression models"""


@RETIRED
def test_tc_p1_083_metrics_json_has_algorithm():
    """TC-P1-083: metrics.json includes an `algorithm` field for regression models"""


@pytest.mark.skip(reason="asserts a live API response — belongs to the backend lane, "
                         "not the repo-assertion lane")
def test_tc_early_009_predict_upload_batch_count():
    """TC-EARLY-009: POST /predict/upload returns a count matching the CSV row count"""


@pytest.mark.skip(reason="needs the rendered page, and the documented figures are a "
                         "point-in-time list — belongs to the browser lane")
def test_tc_p13_024_no_unverifiable_performance_claims():
    """TC-P13-024: unverifiable performance claims removed sitewide"""


@pytest.mark.skip(reason="needs the served HTML and the generated handbook chapters — "
                         "browser lane")
def test_tc_p13_036_corner_radii_use_tokens():
    """TC-P13-036: corner radii all resolve to the token scale (14/10px)"""


@pytest.mark.skip(reason="src/lib/capabilities.ts moved to src/data/capabilities/; the "
                         "documented path no longer identifies the subject")
def test_tc_p13_042_chapter_filenames_key_off_capability_id():
    """TC-P13-042: deep-chapter file names key off capability id, not route"""
