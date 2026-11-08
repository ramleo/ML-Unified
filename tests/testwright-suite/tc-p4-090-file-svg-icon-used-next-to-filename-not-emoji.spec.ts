import { test, expect } from '@playwright/test';

const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=eda';

test.describe('tc-p4-090-file-svg-icon-used-next-to-filename-not-emoji', () => {
  test('File SVG icon appears next to filename without emoji', async ({ page }) => {
    await page.goto(BASE_URL);

    // Open the Clean & Export panel
    const cleanExportBtn = page.getByRole('button', {
      name: 'Clean & Export Deduplicate, impute, download',
      exact: true,
    });
    await expect(cleanExportBtn).toBeVisible();
    await cleanExportBtn.click();

    // Locate the filename element
    const filenameLocator = page.locator('[data-testid="sc-filename"]');
    await expect(filenameLocator).toBeVisible();

    // Verify an SVG icon is present next to the filename
    const svgLocator = filenameLocator.locator('svg');
    await expect(svgLocator.first()).toBeVisible();

    // Ensure no emoji character is present in the filename markup
    const innerHTML = await filenameLocator.innerHTML();
    expect(innerHTML).not.toContain('📄');
  });
});