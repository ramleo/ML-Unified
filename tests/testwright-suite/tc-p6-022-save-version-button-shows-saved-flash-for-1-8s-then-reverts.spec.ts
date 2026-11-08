import { test, expect } from '@playwright/test';

test.describe('tc-p6-022-save-version-button-shows-saved-flash-for-1-8s-then-reverts', () => {
  test('Save Version button flash behavior', async ({ page }) => {
    const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/automl';
    await page.goto(BASE_URL);

    // Locate the "Saved" button (initial state before flash)
    const saveButton = page.getByRole('button', { name: 'Saved', exact: true });
    await expect(saveButton).toBeVisible();

    // Click the button to trigger the flash
    await saveButton.click();

    // Expect the button text to change to "Saved!" and become disabled
    await expect(saveButton).toHaveText('Saved!');
    await expect(saveButton).toBeDisabled();

    // After the flash, expect the text to revert to "Saved" and become enabled again
    await expect(saveButton).toHaveText('Saved', { timeout: 3000 });
    await expect(saveButton).toBeEnabled();
  });
});