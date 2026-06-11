"""
Home page — page loads, sidebar is populated with model buttons.
"""


def test_page_title(page):
    assert "ML" in page.title()


def test_sidebar_has_supervised_models(page):
    """All four supervised model buttons must be present."""
    for model_id in ("iris", "titanic", "diabetes", "insurance"):
        btn = page.locator(f"#btn-{model_id}")
        assert btn.count() == 1, f"Missing sidebar button for model '{model_id}'"


def test_sidebar_has_unsupervised_tools(page):
    page.wait_for_selector("#ubtn-kmeans", timeout=5000)
    page.wait_for_selector("#ubtn-dbscan", timeout=5000)


def test_sidebar_has_data_tools(page, ml_api_server):
    """EDA/Clean buttons only appear in ?mode=eda — verify they render there."""
    page.goto(f"{ml_api_server}/?mode=eda", wait_until="networkidle")
    page.wait_for_selector("#ebtn-eda",   timeout=8000)
    page.wait_for_selector("#ebtn-clean", timeout=5000)


def test_empty_state_shown_on_load(page):
    """Before any model is selected the empty-state prompt is visible."""
    empty = page.locator("#emptyState")
    assert empty.count() == 1
    assert empty.is_visible()
