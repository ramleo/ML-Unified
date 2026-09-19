import { test, expect } from '@playwright/test';

// A HEALABLE failure: the element exists, but the accessible name is wrong — the
// real level-1 heading is "AIRaML", not "AIRaML Platform". Self-healing should
// read the page snapshot and correct the name; the original must fail first.
test.describe('heal-me', () => {
  test('the main heading is visible', async ({ page }) => {
    await page.goto('https://ml-portfolio-rho.vercel.app', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'AIRaML Platform', level: 1 })
    ).toBeVisible({ timeout: 4000 });
  });
});
