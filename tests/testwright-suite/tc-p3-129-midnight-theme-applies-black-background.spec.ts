import { test, expect } from '@playwright/test';

const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test.describe('tc-p3-129-midnight-theme-applies-black-background', () => {
  test('Midnight theme sets body background to pure black', async ({ page }) => {
    // Navigate to the application
    await page.goto(BASE_URL);

    // Dismiss possible overlay if present (guarded)
    const dismissButton = page.getByRole('button', { name: /skip|got it|no thanks|accept all|dismiss|get started/i });
    if (await dismissButton.isVisible().catch(() => false)) {
      await dismissButton.click();
    }

    // Ensure the Midnight theme button is visible and click it
    const midnightButton = page.getByRole('button', { name: 'Midnight', exact: true });
    await expect(midnightButton).toBeVisible();
    await midnightButton.click();

    // Verify the body background color is pure black
    const bgColor = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(bgColor).toBe('rgb(0, 0, 0)');
  });
});