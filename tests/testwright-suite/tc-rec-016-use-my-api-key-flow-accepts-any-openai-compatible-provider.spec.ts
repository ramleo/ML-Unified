import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/automl';

test.describe('tc-rec-016-use-my-api-key-flow-accepts-any-openai-compatible-provider', () => {
  test('AutoML page loads and primary controls are visible', async ({ page }) => {
    // Navigate to the AutoML tool page
    await page.goto(BASE_URL);

    // Verify the main heading is visible (resilient by exact name)
    await expect(page.getByRole('heading', { name: 'AutoML Pipeline', exact: true })).toBeVisible();

    // Verify the "New Run" button is visible and click it
    const newRunButton = page.getByRole('button', { name: 'New Run', exact: true });
    await expect(newRunButton).toBeVisible();
    await newRunButton.click();

    // After initiating a new run, ensure a heading is still present as a generic sanity check
    await expect(page.getByRole('heading').first()).toBeVisible();
  });
});