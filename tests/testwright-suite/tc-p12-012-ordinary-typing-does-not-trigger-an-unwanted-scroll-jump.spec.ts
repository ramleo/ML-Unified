import { test, expect } from '@playwright/test';

// TC-P12-012 — typing in the tools search box must not scroll the page.
// Start with the box ON SCREEN: that is how a user types into it. (An earlier version
// focused the box while it was off-screen, which makes the browser scroll to it — a
// test artifact, not an app bug.)
const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p12-012-ordinary-typing-does-not-trigger-an-unwanted-scroll-jump', () => {
  test('typing "p" then "pi" leaves the scroll position unchanged', async ({ page }) => {
    await page.goto(BASE_URL);
    const search = page.getByRole('searchbox', { name: /^Search all/ });
    await expect(search).toBeVisible();

    // Bring the box on screen and focus it; let any scroll from clicking settle.
    await search.scrollIntoViewIfNeeded();
    await search.click();
    await page.waitForTimeout(800);
    const before = await page.evaluate(() => window.scrollY);

    await page.keyboard.type('p');
    await page.waitForTimeout(400);
    await page.keyboard.type('i');
    await page.waitForTimeout(400);

    await expect(search).toHaveValue('pi');
    expect(await page.evaluate(() => window.scrollY)).toBe(before);
  });
});
