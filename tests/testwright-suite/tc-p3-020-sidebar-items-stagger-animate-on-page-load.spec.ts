import { test, expect } from '@playwright/test';

const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test.describe('tc-p3-020-sidebar-items-stagger-animate-on-page-load', () => {
  test('Sidebar items animate with staggered timing', async ({ page }) => {
    await page.goto(BASE_URL);

    // Dismiss potential first‑load overlay if present
    const dismiss = page.getByRole('button', { name: /skip|got it|no thanks|accept all|dismiss|get started/i });
    if (await dismiss.isVisible().catch(() => false)) {
      await dismiss.click();
    }

    // Locator for sidebar items that have the animation class
    const sidebarItems = page.locator('.sb-anim'); // uses the specific animation class from the page

    // Ensure at least one item is present
    await expect(sidebarItems.first()).toBeVisible();

    const itemCount = await sidebarItems.count();
    const timestamps: number[] = [];

    for (let i = 0; i < itemCount; i++) {
      const item = sidebarItems.nth(i);
      // Wait for the individual item to become visible (staggered animation)
      await expect(item).toBeVisible();

      // Record the high‑resolution timestamp at the moment the item is visible
      const now = await page.evaluate(() => performance.now());
      timestamps.push(now);
    }

    // Verify that each successive item appears at least ~40 ms after the previous one
    for (let i = 1; i < timestamps.length; i++) {
      const diff = timestamps[i] - timestamps[i - 1];
      expect(diff).toBeGreaterThan(40);
    }
  });
});