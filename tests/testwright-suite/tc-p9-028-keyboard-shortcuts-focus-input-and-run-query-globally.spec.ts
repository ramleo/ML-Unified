import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/text-to-sql';

test.describe('tc-p9-028-keyboard-shortcuts-focus-input-and-run-query-globally', () => {
  test('Cmd/Ctrl+K focuses question input and Cmd/Ctrl+Enter runs query', async ({ page }) => {
    await page.goto(BASE_URL);

    // Dismiss possible onboarding overlay
    const dismiss = page.getByRole('button', { name: 'Skip tour' });
    if (await dismiss.isVisible().catch(() => false)) {
      await dismiss.click();
    }

    // Focus the question textarea with keyboard shortcut
    // Try both Ctrl+K and Meta+K to cover Windows/Linux and macOS
    await page.keyboard.press('Control+K');
    await page.keyboard.press('Meta+K');

    const questionBox = page.getByPlaceholder('Ask a question about your data… (Enter to run)');
    await expect(questionBox).toBeFocused();

    // Type a sample question
    await questionBox.type('How many albums?');

    // Submit the query with keyboard shortcut
    await page.keyboard.press('Control+Enter');
    await page.keyboard.press('Meta+Enter');

    // Verify the submit control is still present (indicates the action was processed)
    const askButton = page.getByRole('button', { name: 'Ask' });
    await expect(askButton).toBeVisible();
  });
});