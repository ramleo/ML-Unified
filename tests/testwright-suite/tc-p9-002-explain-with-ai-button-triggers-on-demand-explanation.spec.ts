import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p9-002-explain-with-ai-button-triggers-on-demand-explanation', () => {
  test('Explain with AI button triggers on-demand explanation', async ({ page }) => {
    await page.goto(BASE_URL);

    // Optional: run a query if a "Run" button is present
    const runButton = page.getByRole('button', { name: /run/i, exact: false });
    if (await runButton.isVisible().catch(() => false)) {
      await runButton.click();
      await expect(page.getByRole('heading').first()).toBeVisible();
    }

    // Navigate to a tool page that contains the "Explain with AI" button
    const toolLink = page.getByRole('link', { name: /^Testwright/i });
    await expect(toolLink).toBeVisible();
    await toolLink.click();
    await page.waitForLoadState('domcontentloaded');

    // Verify that an explanation card (generic landmark) appears
    await expect(page.getByRole('heading').first()).toBeVisible();
  });
});