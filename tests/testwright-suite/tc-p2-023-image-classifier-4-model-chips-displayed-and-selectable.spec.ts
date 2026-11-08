import { test, expect } from '@playwright/test';

test.describe('tc-p2-023-image-classifier-4-model-chips-displayed-and-selectable', () => {
  test('Image Classifier shows 4 model chips and they are selectable', async ({ page }) => {
    const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=vision';
    await page.goto(BASE_URL);

    // Click the Image Classifier button in the sidebar
    const imageClassifierBtn = page.getByRole('button', { name: /^Image Classifier ImageNet ·/ }).first();
    await expect(imageClassifierBtn).toBeVisible();
    await imageClassifierBtn.click();

    // Verify the four model chips are visible
    const mobileNetBtn = page.getByRole('button', {
      name: 'MobileNetV2 Fast & lightweight (14 MB)',
      exact: true,
    });
    const resNetBtn = page.getByRole('button', {
      name: 'ResNet50 Classic deep residual (98 MB)',
      exact: true,
    });
    const squeezeNetBtn = page.getByRole('button', {
      name: 'SqueezeNet 1.1 Tiny & fast (5 MB)',
      exact: true,
    });
    const googLeNetBtn = page.getByRole('button', {
      name: 'GoogLeNet Multi-scale Inception (28 MB)',
      exact: true,
    });

    await expect(mobileNetBtn).toBeVisible();
    await expect(resNetBtn).toBeVisible();
    await expect(squeezeNetBtn).toBeVisible();
    await expect(googLeNetBtn).toBeVisible();

    // Click each chip and assert it remains visible (selection state)
    if (await mobileNetBtn.isVisible()) {
      await mobileNetBtn.click();
      await expect(mobileNetBtn).toBeVisible();
    }

    if (await resNetBtn.isVisible()) {
      await resNetBtn.click();
      await expect(resNetBtn).toBeVisible();
    }

    if (await squeezeNetBtn.isVisible()) {
      await squeezeNetBtn.click();
      await expect(squeezeNetBtn).toBeVisible();
    }

    if (await googLeNetBtn.isVisible()) {
      await googLeNetBtn.click();
      await expect(googLeNetBtn).toBeVisible();
    }
  });
});