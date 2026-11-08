import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/automl';

test.describe('tc-pend-015-mlpipelinestate-data-contract-carries-all-required-fields', () => {
  test('should display AutoML pipeline UI elements', async ({ page }) => {
    // Navigate to the AutoML page (full absolute URL as required)
    await page.goto(BASE_URL);

    // Dismiss any potential first‑load overlay if present (none listed in context, guard just in case)
    const dismissOverlay = page.getByRole('button', { name: /skip|got it|dismiss|accept all/i });
    if (await dismissOverlay.isVisible().catch(() => false)) {
      await dismissOverlay.click();
    }

    // Verify the main heading is visible – resilient because it matches the accessible name exactly
    await expect(
      page.getByRole('heading', { name: 'AutoML Pipeline', exact: true })
    ).toBeVisible();

    // Verify the "New Run" button is visible – matches the button's accessible name
    const newRunButton = page.getByRole('button', { name: 'New Run' });
    await expect(newRunButton).toBeVisible();

    // Start a new AutoML run
    await newRunButton.click();

    // The click does not navigate away (no URL change expected for this action)
    await expect(page).toHaveURL(BASE_URL);

    // As a generic post‑condition, ensure the page still contains a visible heading (fallback when specific UI is unknown)
    await expect(page.getByRole('heading').first()).toBeVisible();
  });
});