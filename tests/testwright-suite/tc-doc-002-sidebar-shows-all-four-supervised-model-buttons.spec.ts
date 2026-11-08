import { test, expect } from '@playwright/test';

const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test.describe('tc-doc-002-sidebar-shows-all-four-supervised-model-buttons', () => {
  test('Sidebar shows all four supervised model buttons', async ({ page }) => {
    await page.goto(BASE_URL);

    // Button for Iris model – identified by its exact accessible name, making the locator resilient.
    const irisBtn = page.getByRole('button', { name: 'Iris Species Classifier Logistic Regression', exact: true });
    await expect(irisBtn).toBeVisible();
    await expect(irisBtn).toHaveCount(1);

    // Button for Titanic model – identified by its exact accessible name.
    const titanicBtn = page.getByRole('button', { name: 'Titanic Random Forest', exact: true });
    await expect(titanicBtn).toBeVisible();
    await expect(titanicBtn).toHaveCount(1);

    // Button for Diabetes model – identified by its exact accessible name.
    const diabetesBtn = page.getByRole('button', { name: 'Diabetes Risk Predictor Random Forest', exact: true });
    await expect(diabetesBtn).toBeVisible();
    await expect(diabetesBtn).toHaveCount(1);

    // Button for Insurance model – identified by its exact accessible name.
    const insuranceBtn = page.getByRole('button', { name: 'Insurance Premium Predictor Random Forest', exact: true });
    await expect(insuranceBtn).toBeVisible();
    await expect(insuranceBtn).toHaveCount(1);
  });
});