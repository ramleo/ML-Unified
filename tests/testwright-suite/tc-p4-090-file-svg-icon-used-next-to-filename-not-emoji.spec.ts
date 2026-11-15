import { test, expect } from '@playwright/test';

// Grounded on the live ?mode=eda Clean & Export panel + eda.html (2026-11-15).
// After a CSV is uploaded via #cleanFileInput, the options render the filename
// inside <span title="<filename>"> with an inline <svg> document icon and no
// emoji. (The only 📄 in the app is a different panel — the Unsupervised upload
// in ml mode — which this case does not target.) Verified live.
const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=eda';

test('Clean & Export shows an inline SVG file icon next to the filename, no emoji', async ({ page }) => {
  test.setTimeout(60000);
  await page.goto(BASE_URL);

  await page.getByRole('button', { name: /Clean & Export/ }).click();

  await page.locator('#cleanFileInput').setInputFiles({
    name: 'data.csv', mimeType: 'text/csv',
    buffer: Buffer.from('a,b,c\n1,2,3\n4,5,6\n7,8,9\n'),
  });

  // The filename renders in its own titled span, with an inline svg icon.
  const titled = page.locator('span[title="data.csv"]');
  await expect(titled).toBeVisible({ timeout: 20000 });
  await expect(titled.locator('svg')).toHaveCount(1);

  // No 📄 emoji anywhere on the page.
  await expect(page.locator('body')).not.toContainText('📄');
});
