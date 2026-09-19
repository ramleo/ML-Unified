"""
Testwright (QA Automation) — configuration.

All tunables in one place so a future standalone `qa-api` microservice carries
its settings without hunting through the code. Env-driven where it matters.
"""

import os

# Free-provider cascade, tried in order. Cohere leads (free + reliable),
# mistral is the second opinion. Gemini is deliberately absent — it is the only
# paid key and these endpoints are public.
GEN_CANDIDATES = [
    ("cohere", "command-a-03-2025"),
    ("mistral", "mistral-small-latest"),
]

# Input bounds.
MAX_INSTRUCTIONS = 4000
MAX_BASE_URL = 300
MAX_NAME = 120

# Budget / rate accounting. Kept identical to the pre-refactor names so the
# daily-cap history and env var carry over unchanged.
FEATURE = "qa-test-author"
BUDGET_POOL = "qa_test_author"
DAILY_CAP_ENV = "QA_TEST_AUTHOR_DAILY_CAP"

# --- Run stage: GitHub Actions execution backend ---
# Tests execute in the isolated public `ramleo/ml-qa-runner` repo, never in this
# Space. The token is read from the RUN_TOKEN_ENV secret at call time.
RUN_OWNER = "ramleo"
RUN_REPO = "ml-qa-runner"
RUN_WORKFLOW_FILE = "qa-run.yml"
RUN_REF = "main"
RUN_TOKEN_ENV = "GH_QA_TOKEN"

# Target URLs are validated in urlcheck.py (any public http(s) URL; private /
# internal addresses blocked). Abuse is bounded by the per-stage budget caps.

# workflow_dispatch inputs are capped (~64KB total) — stay well under.
MAX_RUN_CODE = 60000
# Cap the inline screenshot returned to the UI.
MAX_SCREENSHOT_BYTES = 3_000_000

# Separate budget pool so runs (GitHub-minutes) are capped independently of
# authoring. Defaults to 20/day when the env is unset.
RUN_FEATURE = "qa-run"
RUN_BUDGET_POOL = "qa_run"
RUN_DAILY_CAP_ENV = "QA_RUN_DAILY_CAP"

# --- Heal stage: LLM re-resolves a failed locator from the page snapshot ---
HEAL_FEATURE = "qa-heal"
HEAL_BUDGET_POOL = "qa_heal"
HEAL_DAILY_CAP_ENV = "QA_HEAL_DAILY_CAP"
# Cap the ARIA snapshot sent to the LLM (keeps the prompt within context limits).
MAX_SNAPSHOT_CHARS = 12000
# Cap the error message included in the heal prompt.
MAX_ERROR_CHARS = 2000

# --- Discover stage: crawl a URL, propose test cases from the page snapshot ---
DISCOVER_FEATURE = "qa-discover"
DISCOVER_BUDGET_POOL = "qa_discover"
DISCOVER_DAILY_CAP_ENV = "QA_DISCOVER_DAILY_CAP"
MAX_PROPOSALS = 6
