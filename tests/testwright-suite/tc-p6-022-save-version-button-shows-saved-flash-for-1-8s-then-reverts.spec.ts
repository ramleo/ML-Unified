import { test, expect } from '@playwright/test';

// TC-P6-022 — Save Version flashes "Saved!" for 1.8s, disabled, then reverts.
// The button only exists after a finished AutoML run, so the test runs one on a
// small generated CSV (no fixture file: the runner has no access to local files).
const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/automl';

// 150 rows, two noisy classes, deterministic (no Math.random).
function toyCsv(): string {
  const rows = ['x1,x2,x3,label'];
  for (let i = 0; i < 150; i++) {
    const c = i % 2;
    const wob = (k: number) => Math.sin(i * k) * 1.2;
    rows.push(`${(c * 2 + wob(1.7)).toFixed(3)},${(-c + wob(2.3)).toFixed(3)},${wob(3.1).toFixed(3)},${c ? 'yes' : 'no'}`);
  }
  return rows.join('\n');
}

test.describe('tc-p6-022-save-version-button-shows-saved-flash-for-1-8s-then-reverts', () => {
  test('Save Version button flashes "Saved!" then reverts', async ({ page }) => {
    test.setTimeout(120_000);
    await page.goto(BASE_URL);

    // Upload -> Config -> run the competition.
    await page.locator('input[type=file]').setInputFiles({
      name: 'toy.csv', mimeType: 'text/csv', buffer: Buffer.from(toyCsv()),
    });
    await page.locator('select').first().selectOption('label');
    await page.getByRole('button', { name: 'Run AutoML Competition' }).click();

    // Results step: training takes ~20s.
    const save = page.getByRole('button', { name: 'Save Version', exact: true });
    await expect(save).toBeVisible({ timeout: 90_000 });

    // Click: text becomes "Saved!" immediately and the button is disabled.
    await save.click();
    const flash = page.getByRole('button', { name: 'Saved!', exact: true });
    await expect(flash).toBeVisible();
    await expect(flash).toBeDisabled();

    // After ~1.8s it reverts to "Save Version" and re-enables.
    await expect(save).toBeVisible({ timeout: 4000 });
    await expect(save).toBeEnabled();
  });
});
