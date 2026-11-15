import { test, expect } from '@playwright/test';

const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test.describe('tc-p4-001-tdz-crash-themes-accessed-before-declaration', () => {
  test('should not have THEMES ReferenceError and load models', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto(BASE_URL);

    // Wait for a known model button to become visible, indicating the model list has loaded.
    await expect(page.getByRole('button', { name: '80 Cereals Gradient Boosting', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'K-Means Clustering', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'DBSCAN Density Clustering', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 't-SNE Visualization', exact: true })).toBeVisible();

    // Assert that no ReferenceError about THEMES appears in the console.
    const hasThemesReferenceError = consoleErrors.some(text =>
      text.includes("Cannot access 'THEMES' before initialization")
    );
    expect(hasThemesReferenceError).toBeFalsy();
  });
});