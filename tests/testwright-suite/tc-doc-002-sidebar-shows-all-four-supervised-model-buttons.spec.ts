import { test, expect } from '@playwright/test';

const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test.describe('tc-doc-002-sidebar-shows-all-four-supervised-model-buttons', () => {
  test('Sidebar shows all four supervised model buttons', async ({ page }) => {
    await page.goto(BASE_URL);
    // Assert each supervised model button exists exactly once.
    await expect(page.locator('#btn-iris')).toHaveCount(1);
    await expect(page.locator('#btn-titanic')).toHaveCount(1);
    await expect(page.locator('#btn-diabetes')).toHaveCount(1);
    await expect(page.locator('#btn-insurance')).toHaveCount(1);
  });
});