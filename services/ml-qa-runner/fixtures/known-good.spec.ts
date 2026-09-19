import { test, expect } from '@playwright/test';

// A test that SHOULD pass — proves the runner reports success correctly.
const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('known-good', () => {
  test('homepage loads and the body is visible', async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
    await expect(page).toHaveTitle(/.+/);
    await expect(page.locator('body')).toBeVisible();
  });
});
