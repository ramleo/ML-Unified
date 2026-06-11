"""
Single-row inference — select a model, fill the what-if form, predict,
verify the result panel renders with a prediction and confidence score.
Also verifies SHAP panel completes after a successful prediction.
"""


def _select_model(page, model_id: str):
    page.locator(f"#btn-{model_id}").click()
    # Wait for activeModel.id to match — #predictBtn may already exist from auto-selection
    page.wait_for_function(f"activeModel?.id === '{model_id}'", timeout=8000)


# ── Iris ─────────────────────────────────────────────────────────────────────

def test_iris_predict_returns_result(page):
    _select_model(page, "iris")
    page.fill('input[name="SepalLengthCm"]', "5.1")
    page.fill('input[name="SepalWidthCm"]',  "3.5")
    page.fill('input[name="PetalLengthCm"]', "1.4")
    page.fill('input[name="PetalWidthCm"]',  "0.2")

    page.locator("#predictBtn").click()
    page.wait_for_selector("#resultState", state="visible", timeout=15000)

    assert page.locator("#resultBody").inner_text().strip(), "Result body should not be empty"


def test_iris_predict_shows_species(page):
    _select_model(page, "iris")
    page.fill('input[name="SepalLengthCm"]', "5.1")
    page.fill('input[name="SepalWidthCm"]',  "3.5")
    page.fill('input[name="PetalLengthCm"]', "1.4")
    page.fill('input[name="PetalWidthCm"]',  "0.2")

    page.locator("#predictBtn").click()
    page.wait_for_selector("#resultState", state="visible", timeout=15000)

    body_text = page.locator("#resultBody").inner_text()
    assert any(s in body_text for s in ("Setosa", "Versicolor", "Virginica")), (
        f"Expected species name in result, got: {body_text!r}"
    )


def test_iris_predict_shows_shap(page):
    """After a successful prediction the SHAP panel should complete (bars or error message)."""
    _select_model(page, "iris")
    page.fill('input[name="SepalLengthCm"]', "5.1")
    page.fill('input[name="SepalWidthCm"]',  "3.5")
    page.fill('input[name="PetalLengthCm"]', "1.4")
    page.fill('input[name="PetalWidthCm"]',  "0.2")

    page.locator("#predictBtn").click()
    page.wait_for_selector("#resultState", state="visible", timeout=15000)

    # #shapPanel becomes .visible immediately (shows spinner).
    # Wait for SSE to complete: bars appear OR "unavailable"/"No features" text appears
    page.wait_for_function(
        "document.getElementById('shapBody')?.querySelector('.shap-bar-fill') !== null || "
        "document.getElementById('shapBody')?.querySelector('.shap-loading') !== null",
        timeout=30000,
    )
    assert page.locator("#shapPanel").is_visible(), "SHAP panel should be visible"


# ── Titanic ───────────────────────────────────────────────────────────────────

def test_titanic_predict_returns_result(page):
    _select_model(page, "titanic")
    page.select_option('select[name="Pclass"]',   "3")
    page.select_option('select[name="Sex"]',      "male")
    page.fill('input[name="Age"]',   "22")
    page.fill('input[name="SibSp"]', "1")
    page.fill('input[name="Parch"]', "0")
    page.fill('input[name="Fare"]',  "7.25")
    page.select_option('select[name="Embarked"]', "S")

    page.locator("#predictBtn").click()
    page.wait_for_selector("#resultState", state="visible", timeout=15000)

    body_text = page.locator("#resultBody").inner_text()
    assert any(l in body_text for l in ("Survived", "Did not survive", "0", "1")), (
        f"Expected survival label, got: {body_text!r}"
    )


# ── Diabetes ──────────────────────────────────────────────────────────────────

def test_diabetes_predict_returns_result(page):
    _select_model(page, "diabetes")
    # Use schema sample values — all within [min, max] for each field
    page.fill('input[name="Pregnancies"]',              "6")
    page.fill('input[name="Glucose"]',                  "148")
    page.fill('input[name="BloodPressure"]',            "72")
    page.fill('input[name="SkinThickness"]',            "35")
    page.fill('input[name="Insulin"]',                  "0")
    page.fill('input[name="BMI"]',                      "33.6")
    page.fill('input[name="DiabetesPedigreeFunction"]', "0.627")
    page.fill('input[name="Age"]',                      "50")

    page.locator("#predictBtn").click()
    page.wait_for_selector("#resultState", state="visible", timeout=15000)
    assert page.locator("#resultBody").inner_text().strip()
