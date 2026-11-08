import { test, expect } from '@playwright/test';

test.describe('tc-p1-051-blue-value-display-span-not-shown-next-to-field-labels', () => {
  test('blue value span not present on model form', async ({ page }) => {
    const BASE_URL = 'https://ml-portfolio-rho.vercel.app';
    await page.goto(BASE_URL);

    // Dismiss possible first‑load overlay if a common dismiss button is present
    const possibleDismiss = page.getByRole('button', { name: /got it|accept all|skip tour|no thanks|dismiss|get started/i });
    if (await possibleDismiss.isVisible().catch(() => false)) {
      await possibleDismiss.click();
    }

    // Assert that no element with class "sv" (blue value display span) exists
    await expect(page.locator('.sv')).toHaveCount(0);
  });
});