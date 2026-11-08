import { test, expect } from '@playwright/test';

// TC-P12-066 — every Security & Trust tool has a User Guide and the AI Assistant.
// The route list is the 26 tools mapped to "security-trust" in ml-portfolio/src/lib/toolNav.ts
// (the case said 10; the category has since grown to 26).
const BASE_URL = 'https://ml-portfolio-rho.vercel.app';
const TOOLS = [
  'adversarial-robustness-lab',
  'ai-code-detector',
  'anomaly-detection',
  'attack-surface-scanner',
  'captcha-hardening-lab',
  'dns-tunneling-detector',
  'email-auth-checker',
  'exploit-payload-detector',
  'extension-permission-analyzer',
  'face-cloak',
  'face-deanonymization-demo',
  'intrusion-detection',
  'jwt-analyzer',
  'keystroke-biometric-auth-risk',
  'malicious-package-scanner',
  'malware-image-triage',
  'password-audit',
  'phishing-email-classifier',
  'prompt-injection-playground',
  'qr-phishing-detector',
  'secret-scanner',
  'siem-alert-triage',
  'style-cloak',
  'tls-security-headers-scanner',
  'video-keystroke-inference',
  'yara-file-scanner',
];

test.describe('tc-p12-066-all-security-trust-tools-have-user-guide-toolsaichat', () => {
  for (const id of TOOLS) {
    test(`${id} has a User Guide and an AI Assistant`, async ({ page }) => {
      await page.goto(`${BASE_URL}/tools/${id}`);

      // The User Guide opens a panel headed "<tool> — User Guide".
      await page.getByRole('button', { name: 'User Guide', exact: true }).click();
      await expect(page.getByRole('heading', { name: /User Guide/ }).first()).toBeVisible();

      // The AI Assistant opens a box scoped to this tool: "Ask about <tool> or this website…".
      await page.getByRole('button', { name: 'AI Assistant', exact: true }).click();
      await expect(page.getByPlaceholder(/^Ask about .* or this website/)).toBeVisible();
    });
  }
});
