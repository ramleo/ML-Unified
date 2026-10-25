import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/face-liveness';

test.describe('tc-p18-023-upload-camera-tools-are-testable-via-fixtures-fake-media', () => {
  test('should load the face-liveness tool page and display main heading', async ({ page }) => {
    // Navigate to the tool page
    await page.goto(BASE_URL);

    // Verify the URL is correct
    await expect(page).toHaveURL(BASE_URL);

    // Assert that a heading is visible (generic landmark check)
    await expect(page.getByRole('heading').first()).toBeVisible();
  });
});