import { test, expect } from '@playwright/test';

const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test.describe('tc-p3-020-sidebar-items-stagger-animate-on-page-load', () => {
  test('Sidebar items stagger-animate on page load', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('load');

    // Ensure there are sidebar elements with the expected animation class.
    const sbCount = await page.evaluate(() => document.querySelectorAll('.sb-anim').length);
    expect(sbCount).toBeGreaterThan(0);

    // Record the timestamps when each .sb-anim element becomes visible.
    const timestamps = await page.evaluate(() => {
      const elements = Array.from(document.querySelectorAll('.sb-anim'));
      const times: number[] = [];

      return new Promise<number[]>((resolve) => {
        let pending = elements.length;

        elements.forEach((el) => {
          const checkVisibility = () => {
            const style = getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            const visible =
              style.visibility !== 'hidden' &&
              parseFloat(style.opacity) > 0 &&
              rect.width > 0 &&
              rect.height > 0;

            if (visible) {
              times.push(performance.now());
              pending--;
              if (pending === 0) {
                resolve(times);
              }
            } else {
              requestAnimationFrame(checkVisibility);
            }
          };
          requestAnimationFrame(checkVisibility);
        });
      });
    });

    // Verify that each stagger interval exceeds 40 ms.
    for (let i = 1; i < timestamps.length; i++) {
      const interval = timestamps[i] - timestamps[i - 1];
      expect(interval).toBeGreaterThan(40);
    }
  });
});