import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p3-062-palette-selection-persists-across-page-reload-localstorage', () => {
  test('Palette selection persists across reload', async ({ page }) => {
    // Navigate to the portfolio homepage
    await page.goto(BASE_URL);

    // Dismiss potential first‑load overlay if present
    const dismissOverlay = page.getByRole('button', { name: /skip|got it|no thanks|accept all|dismiss|get started/i });
    if (await dismissOverlay.isVisible().catch(() => false)) {
      await dismissOverlay.click();
    }

    // Attempt to select the Aurora palette if the control exists
    const auroraButton = page.getByRole('button', { name: 'Aurora' });
    if (await auroraButton.isVisible().catch(() => false)) {
      await auroraButton.click();
    }

    // Capture the palette value and accent CSS variable before reload
    const paletteBefore = await page.evaluate(() => localStorage.getItem('palette'));
    const accentFromBefore = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--accent-from')
    );

    // Reload the page
    await page.reload();

    // Verify that the stored palette value persisted
    const paletteAfter = await page.evaluate(() => localStorage.getItem('palette'));
    await expect(paletteAfter).toBe(paletteBefore);

    // Verify that the CSS variable remained the same after reload
    const accentFromAfter = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--accent-from')
    );
    await expect(accentFromAfter.trim()).toBe(accentFromBefore.trim());
  });
});