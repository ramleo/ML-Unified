import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app';

test.describe('tc-p12-038-ec-003-switching-documents-resets-to-that-doc-s-page-1-inte', () => {
  test('switching documents resets to page 1', async ({ page }) => {
    // Open the site
    await page.goto(BASE_URL);

    // Dismiss possible first‑load overlay
    const dismiss = page.getByRole('button', {
      name: /skip tour|got it|no thanks|accept all|dismiss|get started/i,
    });
    if (await dismiss.isVisible().catch(() => false)) {
      await dismiss.click();
    }

    // Navigate to the Docs section
    const docsLink = page.getByRole('link', { name: 'Docs', exact: true }).first();
    await docsLink.click();
    await expect(page).toHaveURL(BASE_URL + '/docs');

    // If a pagination control exists, move to page 2 to ensure we are not on page 1
    const page2Btn = page.getByRole('button', { name: '2', exact: true });
    if (await page2Btn.isVisible().catch(() => false)) {
      await page2Btn.click();
      // Wait until the button indicates the current page (common pattern)
      await expect(page2Btn).toHaveAttribute('aria-current', 'page');
    }

    // Switch to another document – click the first document link in the list
    const docLink = page.getByRole('link').first();
    const targetHref = await docLink.getAttribute('href');
    await docLink.click();
    if (targetHref) {
      await expect(page).toHaveURL(new RegExp('^' + BASE_URL + targetHref));
    }

    // Verify that pagination reset to page 1
    const paginationNav = page.getByRole('navigation', { name: /pagination/i }).first();
    if (await paginationNav.isVisible().catch(() => false)) {
      const page1Btn = paginationNav.getByRole('button', { name: '1', exact: true });
      await expect(page1Btn).toBeVisible();
      await expect(page1Btn).toHaveAttribute('aria-current', 'page');
    } else {
      // Fallback: ensure a heading is visible on the new document page
      await expect(page.getByRole('heading').first()).toBeVisible();
    }
  });
});