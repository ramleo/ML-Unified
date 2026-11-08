import { test, expect } from '@playwright/test';

const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test.describe('tc-p3-113-drift-shows-distribution-histogram-ui-per-numeric-feature-up', () => {
  test('Drift shows distribution histogram UI per numeric feature (upload mode)', async ({ page }) => {
    await page.goto(BASE_URL);

    // Dismiss possible first‑load overlay if it appears
    const dismissOverlay = page.getByRole('button', { name: /skip|got it|no thanks|accept all|dismiss|get started/i });
    if (await dismissOverlay.isVisible().catch(() => false)) {
      await dismissOverlay.click();
    }

    // Open the Drift tab
    const driftTab = page.getByRole('button', { name: 'Drift' });
    await expect(driftTab).toBeVisible();
    await driftTab.click();

    // Verify the histogram container is present
    const histogram = page.locator('[class*="drift-hist"]').first();
    await expect(histogram).toBeVisible();

    // Verify that the histogram contains bar elements (generic check for any child elements)
    const barElements = histogram.locator('[class*="bar"]');
    await expect(barElements.first()).toBeVisible();
  });
});