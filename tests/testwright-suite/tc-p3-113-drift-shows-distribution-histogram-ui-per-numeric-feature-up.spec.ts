import { test, expect } from '@playwright/test';

// Grounded on the live ?mode=ml page (2026-11-15). Each numeric feature card
// renders a .drift-hist with 12 .drift-hist-bin bars and a .drift-hist-legend
// ("Expected" / "Actual"). Verified live with a 40-row cereals CSV (4 numeric
// features × 12 bins = 48 bins total).
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

test('Drift upload shows a 12-bin distribution histogram with an Expected/Actual legend', async ({ page }) => {
  test.setTimeout(90000);
  await page.goto(BASE_URL);

  await page.getByRole('button', { name: /80 Cereals/ }).click();
  await page.getByRole('button', { name: 'Drift' }).click();
  await page.getByRole('button', { name: /Upload dataset/ }).click();

  await page.locator('#driftFileInput').setInputFiles({
    name: 'cereals.csv', mimeType: 'text/csv', buffer: Buffer.from(cerealsCSV()),
  });

  await expect(page.locator('#driftBody')).toContainText(/OVERALL DRIFT/i, { timeout: 30000 });

  const hist = page.locator('.drift-hist').first();
  await expect(hist).toBeVisible();
  await expect(hist.locator('.drift-hist-bin')).toHaveCount(12);

  const legend = page.locator('.drift-hist-legend').first();
  await expect(legend).toContainText('Expected');
  await expect(legend).toContainText('Actual');
});
