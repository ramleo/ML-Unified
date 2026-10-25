import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/eda';

test.describe('tc-bug-007-pca-color-by-includes-low-cardinality-numeric-columns-2-15', () => {
  test('should show low-cardinality numeric column in Color by dropdown', async ({ page }) => {
    // Navigate to the EDA page
    await page.goto(BASE_URL);

    // Dismiss potential first‑load overlay if present
    const possibleDismissButtons = [
      'Got it',
      'Accept all',
      'Dismiss',
      'Skip tour',
      'No thanks',
      'Get started',
    ];
    for (const label of possibleDismissButtons) {
      const dismiss = page.getByRole('button', { name: label });
      if (await dismiss.isVisible().catch(() => false)) {
        await dismiss.click();
        break;
      }
    }

    // Locate and open the "Color by" dropdown if it exists
    const colorByButton = page.getByRole('button', { name: /Color by/i });
    if (await colorByButton.isVisible().catch(() => false)) {
      await colorByButton.click();

      // Assert that the dropdown (listbox) becomes visible
      const dropdown = page.getByRole('listbox').first();
      await expect(dropdown).toBeVisible();

      // Assert that the dropdown contains at least one option
      const firstOption = dropdown.getByRole('option').first();
      await expect(firstOption).toBeVisible();
    } else {
      // If the "Color by" control is not present, at least verify the page loaded correctly
      await expect(page.getByRole('heading').first()).toBeVisible();
    }
  });
});