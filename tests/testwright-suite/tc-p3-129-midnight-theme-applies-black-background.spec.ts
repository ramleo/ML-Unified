import { test, expect } from '@playwright/test';

// Grounded on the live ?mode=ml page (2026-11-15). The theme options live in a
// dropdown that is HIDDEN until the picker is opened — the old spec clicked the
// Midnight button while it was hidden, which the action-gate rejected. Open the
// picker first (#themePickerLabel sits inside the toggle button), then pick
// Midnight. setThemeChoice('midnight') sets data-theme and --bg:#000000.
const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test('Midnight theme sets data-theme and a pure-black body background', async ({ page }) => {
  await page.goto(BASE_URL);

  // Open the theme picker (the options are hidden until it opens).
  await page.locator('button:has(#themePickerLabel)').click();

  const midnight = page.locator('.theme-option[data-theme-opt="midnight"]');
  await expect(midnight).toBeVisible();
  await midnight.click();

  await expect(page.locator('html')).toHaveAttribute('data-theme', 'midnight');

  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(bg).toBe('rgb(0, 0, 0)');
});
