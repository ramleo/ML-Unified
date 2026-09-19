"use strict";

const express = require("express");
const { runTest } = require("./lib/execute");
const { PORT, ALLOWED_HOSTS } = require("./lib/config");

const app = express();
app.use(express.json({ limit: "256kb" }));

app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "ml-qa-runner", allowedHosts: ALLOWED_HOSTS });
});

// Execute one Playwright test file and return pass/fail + a failure screenshot.
app.post("/run", async (req, res) => {
  const { code, baseUrl, testName } = req.body || {};
  try {
    const result = await runTest({ code, baseUrl, testName });
    res.json(result);
  } catch (err) {
    const status = err.statusCode || 500;
    res.status(status).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`ml-qa-runner listening on ${PORT}; allowlist: ${ALLOWED_HOSTS.join(", ")}`);
});
