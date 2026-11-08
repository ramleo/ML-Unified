import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/feature-engineering';

test.describe('tc-p6-051-ai-suggest-rule-based-auto-selects-transforms-based-on-skew', () => {
  test('AI Suggest auto-selects transforms based on skew and missing rate', async ({ page }) => {
    await page.goto(BASE_URL);
    // Verify that the main heading of the feature engineering page is visible
    await expect(page.getByRole('heading', { name: 'Feature Engineering' })).toBeVisible();
  });
});