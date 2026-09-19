---
title: ML QA Runner
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# ml-qa-runner

Isolated Playwright test-execution service for **Testwright** (the QA-automation
platform), Phase 2 — Run. Kept separate from the main ML-Unified Space so a
misbehaving browser can never affect the other tools. This *is* the microservice
the QA design pointed at.

Plan: [`docs/QA_PHASE2_RUN_PLAN.md`](../../docs/QA_PHASE2_RUN_PLAN.md).

## Endpoints

- `GET /health` — liveness + the current own-site allowlist.
- `POST /run` — body `{ code, baseUrl?, testName? }` where `code` is a Playwright
  `@playwright/test` source file. Runs it single-worker under a bounded config
  and returns:
  ```json
  {
    "status": "passed | failed | timeout",
    "passed": true,
    "timedOut": false,
    "summary": { "expected": 1, "unexpected": 0, "flaky": 0, "skipped": 0 },
    "screenshotBase64": "<png, only on failure>",
    "logTail": "<tail of runner output>"
  }
  ```

## Safety

- **Own-site allowlist** on `baseUrl` (`QA_ALLOWED_HOSTS`) — third-party targets
  are rejected (SSRF).
- **Hard wall-clock timeout** (`QA_RUN_TIMEOUT_MS`) kills the whole process tree.
- **Payload cap** rejects oversized source before touching disk.
- **Guaranteed temp-dir cleanup** on every path.

## Local run

```bash
npm install
npx playwright install --with-deps chromium
npm start                      # listens on $PORT (default 7860)

# known-good (expect passed:true)
curl -s localhost:7860/run -H 'content-type: application/json' \
  --data @<(jq -Rs '{code:.}' fixtures/known-good.spec.ts)

# known-bad (expect passed:false + a screenshot)
curl -s localhost:7860/run -H 'content-type: application/json' \
  --data @<(jq -Rs '{code:.}' fixtures/known-bad.spec.ts)
```

Status: **scaffold (Phase 2a).** Not yet deployed to a Space.
