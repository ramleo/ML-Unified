import { test, expect } from '@playwright/test';

const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test.describe('tc-early-011-key-factors-bar-chart-displays-feature-labels-without-num', () => {
  test('Key Factors bar labels are clean after prediction', async ({ page }) => {
    // Navigate to the main page
    await page.goto(BASE_URL);

    // Click a predictor button (using exact accessible name for resilience)
    const predictorButton = page.getByRole('button', { name: 'Diabetes Risk Predictor Random Forest', exact: true });
    await expect(predictorButton).toBeVisible();
    await predictorButton.click();

    // Click the Predict button to submit a prediction
    const predictBtn = page.getByRole('button', { name: 'Predict', exact: true });
    await expect(predictBtn).toBeVisible();
    await predictBtn.click();

    // Wait for the key‑factors bar chart to appear (identified by its container)
    const barLabels = page.locator('#fiBars span');
    await expect(barLabels.first()).toBeVisible();

    // Collect all label texts and assert they do not contain the unwanted prefixes
    const labels = await barLabels.allTextContents();
    for (const label of labels) {
      expect(label).not.toMatch(/^(num|cat)[\s_]/i);
    }
  });
});