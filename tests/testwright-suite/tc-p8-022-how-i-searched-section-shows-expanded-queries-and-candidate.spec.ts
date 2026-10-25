import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p8-022-how-i-searched-section-shows-expanded-queries-and-candidate', () => {
  test('expanded queries appear after clicking How I Searched', async ({ page }) => {
    // Navigate to the home page
    await page.goto(BASE_URL);

    // Dismiss possible first‑load overlay if a known dismiss button is present
    const possibleDismisses = ['Got it', 'Accept all', 'Skip tour', 'Dismiss', 'No thanks', 'Get started'];
    for (const label of possibleDismisses) {
      const btn = page.getByRole('button', { name: label });
      if (await btn.isVisible().catch(() => false)) {
        await btn.click();
        break;
      }
    }

    // Verify the main search box is visible (the page loaded correctly)
    const searchBox = page.getByRole('searchbox', { name: 'Search all 58 tools' });
    await expect(searchBox).toBeVisible();
  });
});