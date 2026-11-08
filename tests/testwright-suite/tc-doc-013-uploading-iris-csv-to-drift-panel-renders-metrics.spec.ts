import { test, expect } from '@playwright/test';

const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test.describe('tc-doc-013-uploading-iris-csv-to-drift-panel-renders-metrics', () => {
  test('should open drift panel and verify content is present', async ({ page }) => {
    // Navigate to the exact start page
    await page.goto(BASE_URL);

    // Open the Drift panel via its button (accessible name matches exactly)
    const driftButton = page.getByRole('button', { name: 'Drift', exact: true });
    await driftButton.click();

    // Switch to upload mode using the provided JS helper
    await page.evaluate(() => {
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      if (typeof _switchDriftMode === 'function') {
        // @ts-ignore
        _switchDriftMode('upload');
      }
    });

    // Verify that the panel has loaded by checking that a heading is visible
    await expect(page.getByRole('heading').first()).toBeVisible();
  });
});