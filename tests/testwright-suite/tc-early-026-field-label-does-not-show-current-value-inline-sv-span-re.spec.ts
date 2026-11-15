import { test, expect } from '@playwright/test';

// Grounded on the live ?mode=ml page (2026-11-15). Field labels render as
// <label class="field-label">name</label> above each input, and the old inline
// value span (class "sv") has been removed — querySelectorAll('.sv') is 0.
// Typing into a field must not append the value to its label.
const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test('Field label shows only the field name, with no inline value and no .sv span', async ({ page }) => {
  await page.goto(BASE_URL);

  // The default 80-cereals model has a numeric "sodium" field.
  const group = page.locator('.field-group').filter({
    has: page.locator('.field-label', { hasText: /^sodium$/ }),
  });
  await expect(group).toHaveCount(1);

  await group.locator('input').fill('42');

  // The label text must stay the bare field name — never "sodium 42".
  await expect(group.locator('.field-label')).toHaveText('sodium');

  // The removed inline-value span must not exist anywhere on the page.
  await expect(page.locator('.sv')).toHaveCount(0);
});
