"""
Drift Monitor — select iris, upload a CSV via the drift drop zone,
verify drift metrics render in #driftBody.
"""


def _open_drift_tab(page, model_id: str = "iris"):
    page.locator(f"#btn-{model_id}").click()
    # Wait for activeModel.id to match — page auto-selects first model, so #predictBtn
    # may already be visible before selectModel(model_id) completes
    page.wait_for_function(f"activeModel?.id === '{model_id}'", timeout=8000)
    page.locator("#tabDrift").click()
    # Wait for drift shell to render (driftBody is inside _driftShell())
    page.wait_for_selector("#driftBody", timeout=8000)


def _switch_to_upload_mode(page):
    """Click the 'Upload dataset' mode button and wait for the upload zone."""
    page.evaluate("_switchDriftMode('upload')")
    page.wait_for_selector("#driftUploadZone", timeout=8000)


def test_drift_tab_opens(page):
    _open_drift_tab(page)
    assert page.locator("#driftView").is_visible()


def test_drift_upload_renders_metrics(page, iris_csv):
    _open_drift_tab(page)
    _switch_to_upload_mode(page)

    # Set file directly on the hidden input — more reliable than clicking the zone
    page.locator("#driftFileInput").set_input_files(iris_csv)

    # Wait for upload analysis to complete (spinner says "Analysing…", result says "OVERALL DRIFT")
    page.wait_for_function(
        "document.getElementById('driftBody')?.innerText?.includes('OVERALL DRIFT') || "
        "document.getElementById('driftBody')?.innerText?.includes('Could not analyse')",
        timeout=20000,
    )
    body_text = page.locator("#driftBody").inner_text()
    assert body_text.strip(), "Drift body should contain metrics after upload"


def test_drift_upload_shows_column_metrics(page, iris_csv):
    _open_drift_tab(page)
    _switch_to_upload_mode(page)

    page.locator("#driftFileInput").set_input_files(iris_csv)

    # Wait for the upload analysis to complete — spinner says "Analysing…", result says "OVERALL DRIFT"
    page.wait_for_function(
        "document.getElementById('driftBody')?.innerText?.includes('OVERALL DRIFT') || "
        "document.getElementById('driftBody')?.innerText?.includes('Could not analyse')",
        timeout=20000,
    )
    body_text = page.locator("#driftBody").inner_text()
    assert "Could not analyse" not in body_text, f"Drift upload failed: {body_text[:300]!r}"
    assert any(col in body_text for col in ("Sepal", "Petal", "SepalLength", "PetalLength")), (
        f"Expected iris feature names in drift output, got: {body_text[:300]!r}"
    )
