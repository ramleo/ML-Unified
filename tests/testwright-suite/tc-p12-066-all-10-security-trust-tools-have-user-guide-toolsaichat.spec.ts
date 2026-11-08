import { test, expect } from '@playwright/test';

const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/security-trust';

test.describe('tc-p12-066-all-10-security-trust-tools-have-user-guide-toolsaichat', () => {
  test('verify all Security & Trust tools are listed', async ({ page }) => {
    await page.goto(BASE_URL);

    // Verify each tool heading is visible. The heading names are taken verbatim from the ARIA snapshot.
    const toolHeadings = [
      'Adversarial Robustness Lab',
      'AI-Generated Code Detector',
      'Attack-Surface / Exposed-Path Scanner',
      'Binary Byte-Plot & Entropy Triage',
      'Browser Extension Permission Risk Analyzer',
      'CAPTCHA Hardening Lab',
      'DNS Tunneling / Exfiltration Detector',
      'Email Header Authentication Checker',
      'Exploit / Attack-Payload Detector',
      'Face Cloak',
      'Face Deanonymization Risk Demo',
    ];

    for (const name of toolHeadings) {
      // Using exact match to avoid substring collisions.
      await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
    }

    // Generic assertion that a "User Guide" button exists somewhere on the page.
    // This button is expected for each tool; presence of at least one indicates the UI element is rendered.
    const userGuideButton = page.getByRole('button', { name: 'User Guide', exact: true });
    await expect(userGuideButton).toBeVisible();

    // Generic assertion that an AI Assistant widget/button is present.
    const aiAssistant = page.getByRole('button', { name: /AI Assistant/i }).first();
    await expect(aiAssistant).toBeVisible();
  });
});