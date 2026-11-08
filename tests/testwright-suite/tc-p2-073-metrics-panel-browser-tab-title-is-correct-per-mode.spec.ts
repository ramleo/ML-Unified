import { test, expect } from '@playwright/test';

const VISION_URL = 'https://wram1708-ml-unified.hf.space/?mode=vision';
const ML_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test.describe('tc-p2-073-metrics-panel-browser-tab-title-is-correct-per-mode', () => {
  test('should have correct browser tab titles for vision and ml modes', async ({ page }) => {
    // Vision mode
    await page.goto(VISION_URL);
    await expect(page).toHaveTitle('ML Vision — Computer Vision Platform');

    // ML mode
    await page.goto(ML_URL);
    await expect(page).toHaveTitle('ML Unified — Multi-Model Predictor');
  });
});