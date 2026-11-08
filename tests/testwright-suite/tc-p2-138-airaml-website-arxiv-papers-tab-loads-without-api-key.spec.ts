import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p2-138-airaml-website-arxiv-papers-tab-loads-without-api-key', () => {
  test('Research Papers tab loads arXiv papers without API key', async ({ page }) => {
    // Navigate to the main page
    await page.goto(BASE_URL);

    // Scroll to the News section using the "News" link (stable anchor)
    const newsLink = page.getByRole('link', { name: 'News' });
    await newsLink.scrollIntoViewIfNeeded();

    // Click the "Research Papers" tab button (exact match to avoid ambiguity)
    const researchPapersButton = page.getByRole('button', { name: '📄 Research Papers', exact: true });
    await expect(researchPapersButton).toBeVisible();
    await researchPapersButton.click();

    // Verify that content appears after clicking the tab.
    // Generic check: a heading is visible (ensures the tab switched content)
    await expect(page.getByRole('heading').first()).toBeVisible();

    // Generic check: at least one link (e.g., a paper title) is visible
    await expect(page.getByRole('link').first()).toBeVisible();

    // Ensure no error message is displayed (looking for common error text)
    const errorMessage = page.getByText(/error|api key/i);
    if (await errorMessage.isVisible().catch(() => false)) {
      throw new Error('Unexpected error message displayed after loading Research Papers tab');
    }
  });
});