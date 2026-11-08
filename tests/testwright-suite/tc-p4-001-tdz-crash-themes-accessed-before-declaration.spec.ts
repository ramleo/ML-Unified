import { test, expect } from '@playwright/test';

const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test.describe('tc-p4-001-tdz-crash-themes-accessed-before-declaration', () => {
  test('should not emit THEMES ReferenceError and load model list', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error' && msg.text().includes('ReferenceError')) {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto(BASE_URL);
    // hard refresh bypassing cache
    await page.evaluate(() => location.reload(true));

    // Wait for at least four model buttons to appear (within 10 s)
    await page.waitForFunction(() => {
      return document.querySelectorAll('#modelList .model-btn').length >= 4;
    }, null, { timeout: 10000 });

    // Verify a model button is visible (web‑first assertion)
    await expect(page.locator('#modelList .model-btn').first()).toBeVisible();

    // Assert no THEMES ReferenceError was logged
    const themError = consoleErrors.find(text => text.includes("Cannot access 'THEMES' before initialization"));
    expect(themError).toBeUndefined();
  });
});