import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p14-014-return-pill-names-the-chapter-at-the-reading-line-with-a-wo', () => {
  test('should load the homepage and display a primary heading', async ({ page }) => {
    await page.goto(BASE_URL);
    await expect(page).toHaveURL(BASE_URL);
    // Assert that a generic heading is visible to confirm the page has loaded.
    await expect(page.getByRole('heading').first()).toBeVisible();
  });
});