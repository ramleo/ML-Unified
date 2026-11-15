import { test, expect } from '@playwright/test';

// Grounded on the live ?mode=ml page (2026-11-15). After a prediction the
// Feature Impact (SHAP) panel renders per-feature rows; each feature name is a
// .shap-feat-name inside .shap-panel. The labels must be clean feature names —
// never the raw ColumnTransformer prefixes num__ / cat__.
const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test('Feature Impact bar labels are clean — no num__ / cat__ prefix', async ({ page }) => {
  test.setTimeout(60000);
  await page.goto(BASE_URL);

  await page.getByRole('button', { name: 'Fill Sample' }).click();
  await page.locator('#predictBtn').click();

  // SHAP is fetched asynchronously after the prediction resolves.
  const names = page.locator('.shap-panel .shap-feat-name');
  await expect(names.first()).toBeVisible({ timeout: 40000 });

  const labels = await names.allTextContents();
  expect(labels.length).toBeGreaterThan(0);
  for (const label of labels) {
    expect(label).not.toMatch(/\b(num__|cat__)/);
  }
});
