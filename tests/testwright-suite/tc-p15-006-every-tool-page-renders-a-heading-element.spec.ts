import { test, expect } from '@playwright/test';

test.describe('tc-p15-006-every-tool-page-renders-a-heading-element', () => {
  test('Realtime Analytics page renders a heading element', async ({ page }) => {
    const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/realtime-analytics';
    await page.goto(BASE_URL);

    // Dismiss possible overlay if present
    const dismissButton = page.getByRole('button', { name: /skip|got it|no thanks|accept all|dismiss|get started/i });
    if (await dismissButton.isVisible().catch(() => false)) {
      await dismissButton.click();
    }

    // Assert that a heading is present on the page
    const heading = page.getByRole('heading', { name: 'Real-Time Analytics', exact: true }).first();
    await expect(heading).toBeVisible();
  });
});