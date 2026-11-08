import { test, expect } from '@playwright/test';

const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test.describe('tc-p3-112-drift-response-includes-ks-test-stat-and-p-value-for-upload', () => {
  test('should display KS stat and p-value after opening Drift view', async ({ page }) => {
    await page.goto(BASE_URL);

    // Dismiss possible overlay if present (guarded)
    const dismissButton = page.getByRole('button', { name: /skip|got it|no thanks|accept all|dismiss|get started/i });
    if (await dismissButton.isVisible().catch(() => false)) {
      await dismissButton.click();
    }

    // Open the Drift tab/view
    await expect(page.getByRole('button', { name: 'Drift' })).toBeVisible();
    await page.getByRole('button', { name: 'Drift' }).click();

    // Locate the KS statistic element and verify it is visible and contains numeric values
    const ksStat = page.locator('[class*="ks-stat"]');
    await expect(ksStat).toBeVisible();
    await expect(ksStat).toContainText(/KS stat:\s*\d+(\.\d+)?\s*·\s*p-value:\s*\d+(\.\d+)?/i);
  });
});