import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p18-002-scheduled-monitoring-re-runs-a-saved-test-and-records-it', () => {
  test('loads the home page and verifies a heading is visible', async ({ page }) => {
    await page.goto(BASE_URL);

    // Dismiss possible overlay if present
    const dismiss = page.getByRole('button', { name: 'Dismiss' });
    if (await dismiss.isVisible().catch(() => false)) {
      await dismiss.click();
    }

    // Verify the page URL is correct
    await expect(page).toHaveURL(BASE_URL);

    // Verify that at least one heading is visible on the page
    await expect(page.getByRole('heading').first()).toBeVisible();
  });
});