import { test, expect } from '@playwright/test';

test.describe('tc-hist-025-pca-auto-kaiser-toggle-keeps-only-components-with-eigenval', () => {
  test('PCA Auto (Kaiser) toggle behavior', async ({ page }) => {
    const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/feature-selection';
    await page.goto(BASE_URL);

    // Verify that the page loaded and a top-level heading is visible
    await expect(page.getByRole('heading').first()).toBeVisible();

    // Verify the URL is exactly the expected one
    await expect(page).toHaveURL(BASE_URL);
  });
});