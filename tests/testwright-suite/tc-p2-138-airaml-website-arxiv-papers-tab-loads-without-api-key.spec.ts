import { test, expect } from '@playwright/test';

// Grounded on the live homepage (2026-11-15). The "News" section (<section id="news">)
// has a "📄 Research Papers" tab that fetches arXiv papers client-side with NO API
// key, rendering each as an <a href*="arxiv.org"> card. A successful load shows those
// links and no error/alert element; a failure would show a gate/error state instead
// of papers.
const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p2-138-airaml-website-arxiv-papers-tab-loads-without-api-key', () => {
  test('Research Papers tab loads arXiv papers without API key', async ({ page }) => {
    await page.goto(BASE_URL);

    // Scroll the News section into view and open the Research Papers tab.
    await page.getByRole('link', { name: 'News' }).scrollIntoViewIfNeeded();
    const tab = page.getByRole('button', { name: '📄 Research Papers', exact: true });
    await expect(tab).toBeVisible();
    await tab.click();

    // Success contract: the tab renders arXiv papers with no API key. Rendered arXiv
    // links are the proof — if a key were required or the fetch errored, there would
    // be no papers, only a gate/error state.
    const papers = page.locator('#news a[href*="arxiv.org"]');
    await expect(papers.first()).toBeVisible({ timeout: 15000 });
    expect(await papers.count()).toBeGreaterThan(0);

    // NOTE: the earlier whole-page getByText(/error|api key/i) guard was removed. It
    // scanned the ENTIRE page and false-failed on live arXiv ABSTRACTS containing the
    // word "error" (ubiquitous in ML papers) — the "guard matches the wrong element"
    // anti-pattern. Papers-present is the correct, non-flaky signal that the tab
    // loaded without a key or error.
  });
});
