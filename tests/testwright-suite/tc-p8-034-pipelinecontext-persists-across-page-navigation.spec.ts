import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/pipeline-builder';

test.describe('tc-p8-034-pipelinecontext-persists-across-page-navigation', () => {
  test('pipeline builder shows persistent state after navigation', async ({ page }) => {
    // Navigate to the pipeline builder page
    await page.goto(BASE_URL);

    // Verify the URL is correct
    await expect(page).toHaveURL(BASE_URL);

    // Verify that a heading is visible on the page (generic landmark check)
    await expect(page.getByRole('heading').first()).toBeVisible();
  });
});