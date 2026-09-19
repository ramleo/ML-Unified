"""
Testwright (QA Automation) — configuration.

All tunables in one place so a future standalone `qa-api` microservice carries
its settings without hunting through the code. Env-driven where it matters.
"""

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
