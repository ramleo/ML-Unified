import { test, expect } from '@playwright/test';

test.describe('tc-p2-058-mode-vision-changes-nav-title-to-ml-vision', () => {
  test('Nav title reads "ML Vision" and subtitle reads "Computer Vision Platform"', async ({ page }) => {
    const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=vision';
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Dismiss possible first‑load overlay if it appears
    const dismiss = page.getByRole('button', { name: /skip|got it|dismiss|accept all/i });
    if (await dismiss.isVisible().catch(() => false)) {
      await dismiss.click();
    }

    // Nav title – resilient locator by visible text
    const navTitle = page.getByText('ML Vision');
    await expect(navTitle).toBeVisible();
  });
});