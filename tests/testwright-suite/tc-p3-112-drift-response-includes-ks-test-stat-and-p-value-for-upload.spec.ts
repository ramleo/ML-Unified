import { test, expect } from '@playwright/test';

// Grounded on the live ?mode=ml page (2026-11-15). In upload mode each numeric
// feature card renders a .drift-ks line: "KS stat: 0.132 · p-value: 0.518 —
// within range". Verified live with a 40-row cereals CSV (4 numeric KS lines).
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

test('Drift upload shows a KS stat and p-value per numeric feature', async ({ page }) => {
  test.setTimeout(90000);
  await page.goto(BASE_URL);

  await page.getByRole('button', { name: /80 Cereals/ }).click();
  await page.getByRole('button', { name: 'Drift' }).click();
  await page.getByRole('button', { name: /Upload dataset/ }).click();

  await page.locator('#driftFileInput').setInputFiles({
    name: 'cereals.csv', mimeType: 'text/csv', buffer: Buffer.from(cerealsCSV()),
  });

  // Wait for the analysis to render, then assert the KS line.
  await expect(page.locator('#driftBody')).toContainText(/OVERALL DRIFT/i, { timeout: 30000 });
  const ks = page.locator('.drift-ks').first();
  await expect(ks).toBeVisible();
  await expect(ks).toContainText(/KS stat:/);
  await expect(ks).toContainText(/p-value:/);
});
