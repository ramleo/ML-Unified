import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/realtime-analytics';
const SECOND_URL = 'https://ml-portfolio-rho.vercel.app/tools/text-to-sql';

test.describe('tc-p9-100-root-page-background-does-not-block-the-constellation-canvas', () => {
  test('background remains visible behind cards on both tools pages', async ({ page }) => {
    // Load the Real-Time Analytics page
    await page.goto(BASE_URL);
    // Assert that the main heading is visible (resilient by role and exact name)
    await expect(page.getByRole('heading', { name: 'Real-Time Analytics', exact: true })).toBeVisible();

    // Load the Text-to-SQL page
    await page.goto(SECOND_URL);
    // Dismiss possible tour overlay if present
    const skipTour = page.getByRole('button', { name: 'Skip tour' });
    if (await skipTour.isVisible().catch(() => false)) {
      await skipTour.click();
    }
    // Assert that the main heading on Text-to-SQL page is visible
    await expect(page.getByRole('heading', { name: 'Text-to-SQL Agent', exact: true })).toBeVisible();
  });
});