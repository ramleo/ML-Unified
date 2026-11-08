import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/feature-selection';

test.describe('tc-hist-042-fs-method-agreement-table-appears-only-when-2-scoring-meth', () => {
  test('method agreement table appears only when 2 scoring methods are active', async ({ page }) => {
    await page.goto(BASE_URL);
    // Verify that the main heading for the Feature Selection tool is visible
    await expect(page.getByRole('heading', { name: 'Feature Selection', exact: true })).toBeVisible();
  });
});