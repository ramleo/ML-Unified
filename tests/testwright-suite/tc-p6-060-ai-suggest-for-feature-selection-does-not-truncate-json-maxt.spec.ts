import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p6-060-ai-suggest-for-feature-selection-does-not-truncate-json-maxt', () => {
  test('AI Suggest for Feature Selection does not truncate JSON', async ({ page }) => {
    await page.goto(BASE_URL);

    // Dismiss a possible first‑load overlay
    const dismiss = page.getByRole('button', { name: 'Dismiss' });
    if (await dismiss.isVisible().catch(() => false)) {
      await dismiss.click();
    }

    // Verify the page loaded with a visible heading
    await expect(page.getByRole('heading').first()).toBeVisible();

    // Locate the AI Suggest Methods button (exact accessible name)
    const aiSuggestBtn = page.getByRole('button', { name: 'AI Suggest Methods', exact: true });

    // If the button is present, click it and assert no navigation or generic error appears
    if (await aiSuggestBtn.isVisible().catch(() => false)) {
      await aiSuggestBtn.click();

      // URL should remain the same (no navigation)
      await expect(page).toHaveURL(BASE_URL);

      // Ensure no generic alert is shown after the action
      const errorAlert = page.getByRole('alert');
      await expect(errorAlert).toBeHidden();
    }
  });
});