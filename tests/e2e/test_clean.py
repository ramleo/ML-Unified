"""
Clean & Export panel — upload a CSV, verify the options panel renders.

These tests require ml-eda to be running and configured via ML_EDA_URL.
They are automatically skipped when ml-eda is unavailable.
"""
import os

import pytest
import requests


def _eda_available() -> bool:
    eda_url = os.environ.get("ML_EDA_URL", "").rstrip("/")
    if not eda_url:
        return False
    try:
        r = requests.get(f"{eda_url}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


skip_no_eda = pytest.mark.skipif(
    not _eda_available(),
    reason="ML_EDA_URL not set or ml-eda not reachable — skipping Clean & Export tests",
)


def _open_clean_panel(page):
    page.locator("#ebtn-clean").click()
    page.wait_for_selector("#cleanOptions", timeout=8000)


@skip_no_eda
def test_clean_panel_opens(page):
    _open_clean_panel(page)
    assert page.locator("#cleanOptions").is_visible()


@skip_no_eda
def test_clean_upload_renders_options(page, iris_csv):
    _open_clean_panel(page)

    with page.expect_file_chooser() as fc_info:
        page.locator("#cleanOptions").click()
    fc_info.value.set_files(iris_csv)

    # Progress bar runs then options panel renders
    page.wait_for_selector("#cleanOptions .shap-header", timeout=30000)
    assert page.locator("#cleanOptions .shap-title").inner_text() == "🧹 Clean & Export"


@skip_no_eda
def test_clean_upload_shows_sections(page, iris_csv):
    _open_clean_panel(page)

    with page.expect_file_chooser() as fc_info:
        page.locator("#cleanOptions").click()
    fc_info.value.set_files(iris_csv)

    page.wait_for_selector("#cleanOptions .shap-header", timeout=30000)

    # All five section titles should appear
    text = page.locator("#cleanOptions").inner_text()
    for section in ("Duplicate rows", "Columns to drop", "Missing value", "Outlier", "Power transform"):
        assert section in text, f"Section '{section}' missing from Clean & Export panel"


@skip_no_eda
def test_clean_submit_downloads_csv(page, iris_csv):
    _open_clean_panel(page)

    with page.expect_file_chooser() as fc_info:
        page.locator("#cleanOptions").click()
    fc_info.value.set_files(iris_csv)

    page.wait_for_selector("#cleanOptions .shap-header", timeout=30000)

    # Trigger download and check a file is produced
    with page.expect_download() as dl_info:
        page.locator("#sc-submit").click()
    download = dl_info.value
    assert download.suggested_filename.endswith(".csv")
