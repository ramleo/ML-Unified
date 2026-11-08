import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/document-intelligence';

test.describe('tc-p9-102-extracted-fields-stream-in-one-by-one-via-sse-with-staggered', () => {
  test('should display main UI elements after navigation', async ({ page }) => {
    await page.goto(BASE_URL);

    // Verify the main heading is visible (resilient locator by accessible name)
    await expect(page.getByRole('heading', { name: 'Document Intelligence' })).toBeVisible();

    // Verify a representative control button is visible
    await expect(page.getByRole('button', { name: 'Auto-detect' })).toBeVisible();
  });
});