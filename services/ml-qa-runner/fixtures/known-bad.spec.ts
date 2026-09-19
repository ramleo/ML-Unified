import { test, expect } from '@playwright/test';

// A test that SHOULD fail — proves the runner reports failure (not just green)
// and captures a failure screenshot. If this ever "passes", the runner is lying.
const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('known-bad', () => {
  test('an element that does not exist is asserted visible', async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('button', { name: 'this-button-does-not-exist-xyz-42' })
    ).toBeVisible({ timeout: 3000 });
  });
});
