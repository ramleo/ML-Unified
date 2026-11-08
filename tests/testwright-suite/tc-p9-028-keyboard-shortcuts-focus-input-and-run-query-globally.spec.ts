import { test, expect } from '@playwright/test';

// TC-P9-028 — Ctrl/Cmd+K focuses the question box; Ctrl/Cmd+Enter runs the query,
// from anywhere on the page. The runner is Linux, so Control is the modifier.
// Note the app matches e.key === "k" (lowercase): press 'Control+k', not 'Control+K'.
const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/text-to-sql';

test.describe('tc-p9-028-keyboard-shortcuts-focus-input-and-run-query-globally', () => {
  test('Ctrl+K focuses the question box and Ctrl+Enter sends the query', async ({ page }) => {
    // Abort the SQL call: the test only needs to see that it was sent, not spend a model call.
    await page.route('**/sql/query', (route) => route.abort());

    await page.goto(BASE_URL);
    const questionBox = page.getByPlaceholder('Ask a question about your data… (Enter to run)');
    await expect(questionBox).toBeVisible();

    // Ctrl+K from the page body focuses the question box.
    await page.keyboard.press('Control+k');
    await expect(questionBox).toBeFocused();

    // Ctrl+Enter runs the query: the app posts it to the SQL service.
    await questionBox.fill('How many albums?');
    const sent = page.waitForRequest((r) => r.method() === 'POST' && r.url().includes('/sql/query'));
    await page.keyboard.press('Control+Enter');
    await sent;
  });
});
