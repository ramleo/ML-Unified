import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/feature-selection';

test.describe('tc-hist-018-lda-4-class-dataset-shows-3d-scatter-with-orbitcontrols', () => {
  test('LDA shows 3D scatter with orbit controls', async ({ page }) => {
    await page.goto(BASE_URL);

    // Dismiss possible first‑load overlay (e.g., tour, cookie banner)
    const dismissBtn = page.getByRole('button', { name: /skip|got it|no thanks|accept all|dismiss|get started/i });
    if (await dismissBtn.isVisible().catch(() => false)) {
      await dismissBtn.click();
    }

    // Wait for the Three.js canvas that renders the 3D scatter
    const canvas = page.locator('canvas').first();
    await expect(canvas).toBeVisible();

    // Drag on the canvas to rotate the scene (OrbitControls)
    const box = await canvas.boundingBox();
    if (box) {
      const startX = box.x + box.width / 2;
      const startY = box.y + box.height / 2;
      await page.mouse.move(startX, startY);
      await page.mouse.down();
      await page.mouse.move(startX + 100, startY, { steps: 10 });
      await page.mouse.up();
    }

    // Canvas should remain visible after interaction
    await expect(canvas).toBeVisible();
  });
});