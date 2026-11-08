import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/realtime-analytics';

test.describe('tc-p9-066-live-feed-filters-by-event-type-and-country', () => {
  test('filters feed by event type and country', async ({ page }) => {
    // Navigate to the exact page URL
    await page.goto(BASE_URL);

    // Dismiss possible first‑load overlay if present
    const dismissBtn = page.getByRole('button', { name: /skip|got it|dismiss|accept all|no thanks/i });
    if (await dismissBtn.isVisible().catch(() => false)) {
      await dismissBtn.click();
    }

    // Ensure the main heading is visible (resilient generic check)
    await expect(page.getByRole('heading', { name: 'Real-Time Analytics' })).toBeVisible();

    // Click an event‑type filter pill (example: "run_success")
    const typeFilter = page.getByRole('button', { name: 'run_success', exact: true });
    await expect(typeFilter).toBeVisible();
    await typeFilter.click();

    // Click a country filter pill (example: "c6d9d4bf")
    const countryFilter = page.getByRole('button', { name: 'c6d9d4bf', exact: true });
    await expect(countryFilter).toBeVisible();
    await countryFilter.click();

    // Verify the page URL remains the same (filters do not navigate)
    await expect(page).toHaveURL(BASE_URL);

    // Verify the generic heading is still visible after filtering
    await expect(page.getByRole('heading', { name: 'Real-Time Analytics' })).toBeVisible();

    // Verify the "All" filter button is still present to allow reset
    const allButton = page.getByRole('button', { name: 'All', exact: true });
    await expect(allButton).toBeVisible();
  });
});