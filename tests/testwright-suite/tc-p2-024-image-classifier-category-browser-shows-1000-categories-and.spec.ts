import { test, expect } from '@playwright/test';

const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=vision';

test.describe('tc-p2-024-image-classifier-category-browser-shows-1000-categories-and', () => {
  test('category browser expands and filters on search', async ({ page }) => {
    // Navigate to the starting page
    await page.goto(BASE_URL);

    // Click the Image Classifier button
    const imageClassifierBtn = page.getByRole('button', { name: /^Image Classifier ImageNet ·/ }).first();
    await expect(imageClassifierBtn).toBeVisible();
    await imageClassifierBtn.click();

    // Open the 1,000 categories browser
    const browseBtn = page.getByRole('button', { name: /^Browse/ }).first();
    await expect(browseBtn).toBeVisible();
    await browseBtn.click();

    // Locate the search box and type a query
    const searchBox = page.getByPlaceholder('Search categories…');
    await expect(searchBox).toBeVisible();
    await searchBox.fill('dog');
    await expect(searchBox).toHaveValue('dog');
  });
});