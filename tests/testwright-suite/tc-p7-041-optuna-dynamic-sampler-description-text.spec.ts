import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/optuna';

test.describe('tc-p7-041-optuna-dynamic-sampler-description-text', () => {
  test('loads Optuna Tuning page and shows key UI elements', async ({ page }) => {
    await page.goto(BASE_URL);
    await expect(page.getByRole('heading', { name: 'Optuna Tuning', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'User Guide', exact: true })).toBeVisible();
  });
});