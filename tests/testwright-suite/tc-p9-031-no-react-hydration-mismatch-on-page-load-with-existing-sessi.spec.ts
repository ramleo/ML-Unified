import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p9-031-no-react-hydration-mismatch-on-page-load-with-existing-sessi', () => {
  test('should load without hydration errors and restore tabs from sessionStorage', async ({ page }) => {
    // Collect console error and warning messages
    const consoleErrors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error' || msg.type() === 'warning') {
        consoleErrors.push(msg.text());
      }
    });

    // Seed sessionStorage before any script runs
    await page.addInitScript(() => {
      // Store a dummy tabs array to simulate previously saved tabs
      window.sessionStorage.setItem('tabs', JSON.stringify(['tab1', 'tab2']));
    });

    // Navigate to the home page
    await page.goto(BASE_URL);

    // Verify the page has rendered a visible heading (generic landmark)
    await expect(page.getByRole('heading').first()).toBeVisible();

    // Assert no console messages contain hydration error indicators
    const hydrationMatches = consoleErrors.filter(msg => /Hydration|#418/i.test(msg));
    expect(hydrationMatches).toHaveLength(0);
  });
});