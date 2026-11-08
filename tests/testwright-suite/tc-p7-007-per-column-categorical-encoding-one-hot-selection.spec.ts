import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p7-007-per-column-categorical-encoding-one-hot-selection', () => {
  test('loads the home page and shows a heading', async ({ page }) => {
    await page.goto(BASE_URL);
    // Generic landmark assertion: ensure at least one heading is visible
    await expect(page.getByRole('heading').first()).toBeVisible();
  });
});