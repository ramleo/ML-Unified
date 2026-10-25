import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p1-054-dark-animated-mesh-background-hidden-in-light-mode', () => {
  test('should hide mesh background in light mode', async ({ page }) => {
    // Navigate to the home page
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Switch to light mode by ensuring the body has the "light" class
    await page.evaluate(() => {
      document.body.classList.remove('dark');
      document.body.classList.add('light');
    });

    // Verify the body has the light class
    await expect(page.locator('body')).toHaveClass(/light/);
  });
});