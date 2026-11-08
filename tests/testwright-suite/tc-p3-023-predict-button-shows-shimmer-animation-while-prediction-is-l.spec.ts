import { test, expect } from '@playwright/test';

test.describe('tc-p3-023-predict-button-shows-shimmer-animation-while-prediction-is-l', () => {
  test('Predict button shows shimmer animation while loading', async ({ page }) => {
    const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';
    await page.goto(BASE_URL);

    // Dismiss possible first‑load overlay if it appears
    const dismiss = page.getByRole('button', { name: /skip|got it|no thanks|accept all|dismiss|get started/i });
    if (await dismiss.isVisible().catch(() => false)) {
      await dismiss.click();
    }

    // Ensure the Predict button is visible and enabled before interaction
    const predictBtn = page.getByRole('button', { name: 'Predict' });
    await expect(predictBtn).toBeVisible();
    await expect(predictBtn).toBeEnabled();

    // Click Predict and verify the shimmer animation appears during the API call
    await predictBtn.click();
    const shimmer = page.locator('.btn-shimmer');
    await expect(shimmer).toBeVisible();

    // After the prediction completes the shimmer should disappear
    await expect(shimmer).toBeHidden();
  });
});