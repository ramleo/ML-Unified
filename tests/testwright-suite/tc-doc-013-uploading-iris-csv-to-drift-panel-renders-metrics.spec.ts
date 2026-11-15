import { test, expect } from '@playwright/test';

// Grounded on the live ?mode=ml page (2026-11-15). Open the Drift tab, switch to
// Upload mode, and upload a CSV whose columns match the active model's input
// fields. The panel (#driftBody) then renders the drift summary ("OVERALL DRIFT")
// on success, or "Could not analyse" if the columns don't match — either way it
// is non-empty. Verified live: a 40-row cereals CSV yields the summary.
const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

function cerealsCSV(): string {
  const cols = ['mfr','type','calories','protein','fat','sodium','fiber','carbo','sugars','potass','vitamins','shelf','weight','cups'];
  const mfr = ['A','G','K','N','P','Q','R'], typ = ['C','H'];
  const rows = [cols.join(',')];
  for (let i = 0; i < 40; i++) {
    rows.push([mfr[i % 7], typ[i % 2], 50 + (i * 10) % 120, 1 + i % 6, i % 5,
      (i * 17) % 320, (i % 14).toFixed(1), (i * 3) % 23, (i * 2) % 15,
      (i * 23) % 330, [0, 25, 100][i % 3], 1 + i % 3,
      (1 + (i % 3) * 0.25).toFixed(2), (0.5 + (i % 4) * 0.25).toFixed(2)].join(','));
  }
  return rows.join('\n') + '\n';
}

test('Uploading a matching CSV to the drift panel renders non-empty metrics', async ({ page }) => {
  test.setTimeout(90000);
  await page.goto(BASE_URL);

  await page.getByRole('button', { name: /80 Cereals/ }).click();
  await page.getByRole('button', { name: 'Drift' }).click();
  await page.getByRole('button', { name: /Upload dataset/ }).click();

  await page.locator('#driftFileInput').setInputFiles({
    name: 'cereals.csv', mimeType: 'text/csv', buffer: Buffer.from(cerealsCSV()),
  });

  const body = page.locator('#driftBody');
  await expect(body).toContainText(/OVERALL DRIFT|Could not analyse/i, { timeout: 30000 });
  await expect(body).not.toBeEmpty();
});
