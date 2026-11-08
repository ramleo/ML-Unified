import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p12-012-ordinary-typing-does-not-trigger-an-unwanted-scroll-jump', () => {
  test('typing does not cause scroll jump', async ({ page }) => {
    // Navigate to the exact page URL
    await page.goto(BASE_URL);

    // Ensure the main search box is visible (stable locator by role and exact name)
    const searchBox = page.getByRole('searchbox', { name: /^Search all/ }).first();
    await expect(searchBox).toBeVisible();

    // Scroll to a comfortable position (e.g., 500px down) and record the scrollY
    await page.evaluate(() => window.scrollTo(0, 500));
    const initialScroll = await page.evaluate(() => window.scrollY);

    // Focus the search box and type "p" then "i"
    await searchBox.focus();
    await page.keyboard.type('p');
    await page.keyboard.type('i');

    // Verify the typed value is present
    await expect(searchBox).toHaveValue('pi');

    // Capture scrollY after typing and assert it has not changed
    const finalScroll = await page.evaluate(() => window.scrollY);
    expect(finalScroll).toBe(initialScroll);
  });
});