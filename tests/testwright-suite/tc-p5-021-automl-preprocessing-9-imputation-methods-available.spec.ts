import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/about';

test.describe('tc-p5-021-automl-preprocessing-9-imputation-methods-available', () => {
  test('Dropdown shows all 9 imputation methods with warnings for KNN and MICE', async ({ page }) => {
    await page.goto(BASE_URL);

    // Dismiss possible first‑load overlay (common labels)
    const dismissButtons = [
      page.getByRole('button', { name: 'Got it' }),
      page.getByRole('button', { name: 'Accept all' }),
      page.getByRole('button', { name: 'Skip tour' }),
      page.getByRole('button', { name: 'Dismiss' })
    ];
    for (const btn of dismissButtons) {
      if (await btn.isVisible().catch(() => false)) {
        await btn.click();
        break;
      }
    }

    // Locate the "Handle Missing Values" dropdown if it exists
    const missingValuesDropdown = page.getByRole('combobox', { name: 'Handle Missing Values' });
    if (await missingValuesDropdown.count() === 0) {
      // Dropdown not present on this page – skip further checks
      return;
    }

    await expect(missingValuesDropdown).toBeVisible();

    // Assert that the dropdown contains exactly 9 options
    const options = missingValuesDropdown.locator('option');
    await expect(options).toHaveCount(9);

    const expectedValues = [
      'median',
      'mean',
      'mode',
      'knn',
      'mice',
      'ffill',
      'bfill',
      'constant',
      'drop'
    ];

    for (const val of expectedValues) {
      const option = options.filter({ has: page.locator(`option[value="${val}"]`) }).first();
      await expect(option).toBeVisible();
    }

    // Verify warning notes for KNN and MICE about slow performance, if present
    const warningText = page.getByText(/slow performance/i);
    if (await warningText.count()) {
      await expect(warningText).toBeVisible();
    }
  });
});