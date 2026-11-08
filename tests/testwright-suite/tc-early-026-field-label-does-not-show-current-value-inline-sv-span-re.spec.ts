import { test, expect } from '@playwright/test';

const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test.describe('tc-early-026-field-label-does-not-show-current-value-inline-sv-span-re', () => {
  test('label should not include current value after typing', async ({ page }) => {
    // Navigate to the main page
    await page.goto(BASE_URL);

    // Open a predictor (Iris Species Classifier Logistic Regression)
    const predictorButton = page.getByRole('button', { name: 'Iris Species Classifier Logistic Regression', exact: true });
    await expect(predictorButton).toBeVisible();
    await predictorButton.click();

    // Wait for the specific input to appear
    const sepalInput = page.locator('input[name="SepalLengthCm"]');
    await expect(sepalInput).toBeVisible();

    // Fill the input with a number
    await sepalInput.fill('5');

    // Locate the label element above the field and verify it does not contain digits
    const label = page.locator('.inp-lbl').first();
    await expect(label).toBeVisible();
    const labelText = await label.textContent();
    expect(labelText?.trim()).not.toMatch(/\d/);
  });
});