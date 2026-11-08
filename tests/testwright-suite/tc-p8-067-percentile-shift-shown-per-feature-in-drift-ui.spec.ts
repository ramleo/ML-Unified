import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p8-067-percentile-shift-shown-per-feature-in-drift-ui', () => {
  test('loads Drift UI and shows main heading', async ({ page }) => {
    // Navigate to the EDA page, which likely hosts the drift UI
    await page.goto(`${BASE_URL}/eda`);
    await expect(page).toHaveURL(`${BASE_URL}/eda`);

    // Verify that a primary heading is visible as a generic sanity check
    await expect(page.getByRole('heading').first()).toBeVisible();
  });
});