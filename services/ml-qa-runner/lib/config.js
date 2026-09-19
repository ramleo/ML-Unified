"use strict";

// Own-site allowlist. Testwright runs against our own site only — an arbitrary
// third-party target is an SSRF / abuse risk. Overridable via env for local
// testing, comma-separated hostnames (no scheme).
const ALLOWED_HOSTS = (
  process.env.QA_ALLOWED_HOSTS || "ml-portfolio-rho.vercel.app"
)
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

module.exports = {
  PORT: Number(process.env.PORT) || 7860,
  ALLOWED_HOSTS,
  // Hard wall-clock cap for a single run; the browser process tree is killed
  // when this fires.
  RUN_TIMEOUT_MS: Number(process.env.QA_RUN_TIMEOUT_MS) || 90_000,
  // Per-test timeout inside Playwright (must be < RUN_TIMEOUT_MS).
  TEST_TIMEOUT_MS: Number(process.env.QA_TEST_TIMEOUT_MS) || 30_000,
  // Reject oversized payloads before we ever touch disk.
  MAX_CODE_BYTES: Number(process.env.QA_MAX_CODE_BYTES) || 200_000,
  // Cap the screenshot we return inline so a response stays small.
  MAX_SCREENSHOT_BYTES: Number(process.env.QA_MAX_SCREENSHOT_BYTES) || 3_000_000,
};
