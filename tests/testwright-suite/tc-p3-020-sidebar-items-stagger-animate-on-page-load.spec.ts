import { test, expect } from '@playwright/test';

// TC-P3-020 — sidebar items fade in one after another, ~55 ms apart.
// App (common.js animateSidebarIn): each sidebar item gets `sb-anim`, then `sb-visible`
// is added via setTimeout(i*55+30).
//
// Two earlier versions failed for test reasons, not app reasons:
//  1. waited for every `.sb-anim` to be *visible* — items in collapsed groups never are.
//  2. measured wall-clock gaps between the class additions — on a busy runner the page's
//     timers fire back-to-back (median gap 0.1 ms) even though the app scheduled them
//     55 ms apart. So this version reads the delays the page ASKED for, which do not
//     depend on how loaded the machine is, and separately checks every item ended up shown.
const BASE_URL = 'https://wram1708-ml-unified.hf.space/?mode=ml';

test.describe('tc-p3-020-sidebar-items-stagger-animate-on-page-load', () => {
  test('sidebar items are scheduled ~55 ms apart and all become visible', async ({ page }) => {
    // Record the delay of every timer whose callback adds `sb-visible`.
    await page.addInitScript(() => {
      const w = window as unknown as { __delays: number[] };
      w.__delays = [];
      const orig = window.setTimeout.bind(window);
      (window as unknown as { setTimeout: unknown }).setTimeout = (fn: unknown, ms?: number, ...rest: unknown[]) => {
        if (typeof fn === 'function' && String(fn).includes('sb-visible')) w.__delays.push(Number(ms));
        return orig(fn as TimerHandler, ms, ...rest);
      };
    });

    await page.goto(BASE_URL);
    await page.waitForFunction(
      () => (window as unknown as { __delays: number[] }).__delays.length >= 5, null, { timeout: 15000 });
    // Let the longest delay (~12 items x 55 ms) elapse, however slow the machine is.
    await page.waitForFunction(() => {
      const a = document.querySelectorAll('.sb-anim').length;
      return a >= 5 && document.querySelectorAll('.sb-anim:not(.sb-visible)').length === 0;
    }, null, { timeout: 20000 });

    const delays = await page.evaluate(() => (window as unknown as { __delays: number[] }).__delays);
    expect(delays.length).toBeGreaterThanOrEqual(5);

    // Sequential, not simultaneous: each item is scheduled ~55 ms after the one before it.
    for (let i = 1; i < delays.length; i++) {
      expect(delays[i] - delays[i - 1]).toBe(55);
    }
  });
});
