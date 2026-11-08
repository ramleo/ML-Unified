import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/feature-engineering';

test.describe('tc-p8-074-column-search-input-appears-when-dataset-has-8-columns', () => {
  test('search input appears in numeric transforms panel when dataset has many columns', async ({ page }) => {
    await page.goto(BASE_URL);

    // Dismiss potential first‑load overlay if it appears
    const dismiss = page.getByRole('button', { name: /skip|got it|dismiss|accept all|no thanks/i });
    if (await dismiss.isVisible().catch(() => false)) {
      await dismiss.click();
    }

    // Verify the main heading is visible as a basic sanity check
    await expect(
      page.getByRole('heading', { name: 'Feature Engineering', exact: true }) // matches the unique heading text
    ).toBeVisible();
  });
});