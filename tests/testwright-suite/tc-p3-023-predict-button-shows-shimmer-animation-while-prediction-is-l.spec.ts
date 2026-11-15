import { test, expect } from '@playwright/test';

// Grounded on the live ?mode=ml page + frontend source (2026-11-15). runPredict()
// adds the .btn-shimmer class to #predictBtn before the /predict fetch and
// removes it in finally. To observe it reliably we delay the response so the
// loading state stays on screen long enough to assert.
const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test('Predict button carries .btn-shimmer while the prediction request is in flight', async ({ page }) => {
  test.setTimeout(60000);

  // Hold the predict response so the loading state is observable.
  await page.route('**/predict/**', async route => {
    await new Promise(r => setTimeout(r, 1500));
    await route.continue();
  });

  await page.goto(BASE_URL);
  await page.getByRole('button', { name: 'Fill Sample' }).click();

  const btn = page.locator('#predictBtn');
  await btn.click();

  // While the (delayed) request runs, the button has the shimmer class.
  await expect(btn).toHaveClass(/btn-shimmer/, { timeout: 1200 });
});
