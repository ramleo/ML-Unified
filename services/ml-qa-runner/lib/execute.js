"use strict";

const { spawn } = require("child_process");
const fs = require("fs/promises");
const path = require("path");

// The service root — the dir that holds node_modules/@playwright/test. Run dirs
// live UNDER it so Node resolves @playwright/test from an ancestor node_modules
// (a temp dir elsewhere on disk cannot, and npx would fetch a stray copy).
const APP_ROOT = path.resolve(__dirname, "..");
const RUNS_DIR = path.join(APP_ROOT, ".qa-runs");
const PLAYWRIGHT_BIN = path.join(APP_ROOT, "node_modules", ".bin", "playwright");
const {
  ALLOWED_HOSTS,
  RUN_TIMEOUT_MS,
  TEST_TIMEOUT_MS,
  MAX_CODE_BYTES,
  MAX_SCREENSHOT_BYTES,
} = require("./config");

// A bounded Playwright config written into every run's temp dir. Single worker,
// no retries (deterministic for the spike), artifacts only on failure, JSON
// reporter to a file we parse.
function configTs() {
  return `import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  timeout: ${TEST_TIMEOUT_MS},
  workers: 1,
  retries: 0,
  reporter: [['json', { outputFile: 'results.json' }]],
  outputDir: './artifacts',
  use: {
    headless: true,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'on-first-retry',
  },
});
`;
}

function httpError(message, statusCode) {
  const e = new Error(message);
  e.statusCode = statusCode;
  return e;
}

function assertAllowed(baseUrl) {
  if (!baseUrl) return;
  let host;
  try {
    host = new URL(baseUrl).host;
  } catch {
    throw httpError(`Invalid base URL: ${baseUrl}`, 400);
  }
  if (!ALLOWED_HOSTS.includes(host)) {
    throw httpError(
      `Base URL host "${host}" is not on the allowlist. Testwright runs against our own site only.`,
      403
    );
  }
}

// Spawn `npx playwright test` in a detached group so we can kill the whole
// process tree (browser included) on timeout.
function execPlaywright(cwd) {
  return new Promise((resolve) => {
    const child = spawn(PLAYWRIGHT_BIN, ["test"], {
      cwd,
      detached: true,
      env: { ...process.env, CI: "1", FORCE_COLOR: "0" },
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => (stdout += d.toString()));
    child.stderr.on("data", (d) => (stderr += d.toString()));

    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      try {
        process.kill(-child.pid, "SIGKILL");
      } catch {
        /* already gone */
      }
    }, RUN_TIMEOUT_MS);

    child.on("close", (code) => {
      clearTimeout(timer);
      resolve({ code, stdout, stderr, timedOut });
    });
    child.on("error", (err) => {
      clearTimeout(timer);
      resolve({ code: -1, stdout, stderr: stderr + String(err), timedOut });
    });
  });
}

async function readResults(file) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return null;
  }
}

function summarize(results) {
  const stats = results && results.stats;
  if (!stats) return { expected: 0, unexpected: 0, flaky: 0, skipped: 0 };
  return {
    expected: stats.expected || 0,
    unexpected: stats.unexpected || 0,
    flaky: stats.flaky || 0,
    skipped: stats.skipped || 0,
  };
}

// Find the first screenshot Playwright produced (only exists on failure) and
// return it inline as base64, capped in size.
async function firstScreenshot(dir) {
  let found = null;
  async function walk(d) {
    let entries;
    try {
      entries = await fs.readdir(d, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      if (found) return;
      const p = path.join(d, e.name);
      if (e.isDirectory()) await walk(p);
      else if (e.isFile() && e.name.endsWith(".png")) found = p;
    }
  }
  await walk(dir);
  if (!found) return null;
  try {
    const buf = await fs.readFile(found);
    if (buf.length > MAX_SCREENSHOT_BYTES) return null;
    return buf.toString("base64");
  } catch {
    return null;
  }
}

function tail(s, n) {
  if (!s) return "";
  return s.length <= n ? s : s.slice(s.length - n);
}

async function runTest({ code, baseUrl, testName }) {
  if (typeof code !== "string" || !code.trim()) {
    throw httpError("code (Playwright test source) is required", 400);
  }
  if (Buffer.byteLength(code, "utf8") > MAX_CODE_BYTES) {
    throw httpError("Test source too large.", 413);
  }
  assertAllowed(baseUrl);

  await fs.mkdir(RUNS_DIR, { recursive: true });
  const dir = await fs.mkdtemp(path.join(RUNS_DIR, "run-"));
  try {
    await fs.mkdir(path.join(dir, "tests"), { recursive: true });
    await fs.writeFile(path.join(dir, "playwright.config.ts"), configTs());
    await fs.writeFile(path.join(dir, "tests", "generated.spec.ts"), code);

    const { code: exitCode, stdout, stderr, timedOut } = await execPlaywright(dir);
    const results = await readResults(path.join(dir, "results.json"));
    const screenshotBase64 = await firstScreenshot(path.join(dir, "artifacts"));

    const passed = !timedOut && exitCode === 0;
    return {
      status: timedOut ? "timeout" : passed ? "passed" : "failed",
      passed,
      timedOut,
      testName: testName || null,
      summary: summarize(results),
      screenshotBase64,
      logTail: tail(`${stdout}\n${stderr}`, 4000),
    };
  } finally {
    // Guaranteed cleanup so a crash can never leak disk.
    await fs.rm(dir, { recursive: true, force: true }).catch(() => {});
  }
}

module.exports = { runTest };
