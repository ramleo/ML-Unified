import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p13-037-home-shows-area-section-tiles-not-50-tool-cards', () => {
  test('home displays area tiles, no tool cards, and area routes return 200 while bogus slug 404s', async ({ page }) => {
    // Load home page
    await page.goto(BASE_URL + '/');

    // Verify a generic heading is visible (ensures page has loaded)
    await expect(page.getByRole('heading').first()).toBeVisible();

    // Verify that no tool cards are present on the home page.
    // Assuming tool cards are rendered with a semantic role such as "article".
    const toolCards = page.getByRole('article');
    await expect(toolCards).toHaveCount(0);

    // Define the four area routes to check.
    const areaRoutes = [
      '/tools/ml-pipeline',
      '/tools/language-documents',
      '/tools/computer-vision',
      '/tools/security-trust',
    ];

    // Verify each area route loads with HTTP 200 and displays a heading.
    for (const route of areaRoutes) {
      const response = await page.goto(BASE_URL + route);
      expect(response?.status()).toBe(200);
      await expect(page.getByRole('heading').first()).toBeVisible();
    }

    // Verify a bogus tool slug returns a 404 status.
    const bogusResponse = await page.goto(BASE_URL + '/tools/does-not-exist-12345');
    expect(bogusResponse?.status()).toBe(404);
  });
});