"""Testwright (QA Automation) — request/response schemas."""

from pydantic import BaseModel, Field

from routers.qa import config


class ModelChoice(BaseModel):
    """Optional model selection, mixed into the LLM request models. Default (all
    None) = the free server cascade. `user_key` set = BYOK (caller's own key).
    `owner_token` valid = unlock the server's paid provider (e.g. Gemini)."""
    provider: str | None = Field(None, max_length=40)
    model: str | None = Field(None, max_length=80)
    user_key: str | None = Field(None, max_length=400)
    owner_token: str | None = Field(None, max_length=200)


class GenerateRequest(ModelChoice):
    instructions: str = Field(..., min_length=1, max_length=config.MAX_INSTRUCTIONS)
    base_url: str = Field("", max_length=config.MAX_BASE_URL)
    test_name: str = Field("", max_length=config.MAX_NAME)
    # Optional real page context (ARIA snapshot + link map) from Discover, so the
    # generated locators and URLs are grounded in the actual page, not guessed.
    page_context: str = Field("", max_length=config.MAX_PAGE_CONTEXT)


class GenerateResponse(BaseModel):
    code: str
    provider: str | None = None


class AssertRequest(ModelChoice):
    code: str = Field(..., min_length=1, max_length=config.MAX_RUN_CODE)


class AssertSuggestion(BaseModel):
    title: str
    code: str
    why: str


class AssertResponse(BaseModel):
    suggestions: list[AssertSuggestion] = []
    provider: str | None = None


class RunRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=config.MAX_RUN_CODE)
    base_url: str = Field("", max_length=config.MAX_BASE_URL)
    test_name: str = Field("", max_length=config.MAX_NAME)
    # >1 repeats the test back-to-back in one run to detect flakiness.
    runs: int = Field(1, ge=1, le=config.MAX_RUN_REPEATS)
    # Caller confirms ownership/authorization for a third-party target host.
    authorized: bool = False


class RunAccepted(BaseModel):
    correlation_id: str
    status: str  # always "queued"


class CancelResponse(BaseModel):
    # cancelling (GitHub accepted the cancel) | already_done | not_found
    status: str
    detail: str | None = None


class HealRequest(ModelChoice):
    correlation_id: str = Field(..., min_length=1, max_length=64)
    code: str = Field(..., min_length=1, max_length=config.MAX_RUN_CODE)


class HealResponse(BaseModel):
    healed_code: str
    provider: str | None = None
    detail: str | None = None


class DiscoverStart(BaseModel):
    url: str = Field(..., min_length=1, max_length=config.MAX_BASE_URL)
    # Caller confirms ownership/authorization for a third-party target host.
    authorized: bool = False
    # Default ON: also visit same-origin links one hop from the page, so generation
    # SEES the destination pages a test navigates to and asserts their real content
    # instead of guessing (one dispatch, no extra CI runs). Uncheck for a faster,
    # single-page scan.
    deep: bool = True


class Proposal(BaseModel):
    title: str
    steps: str


class DiscoverStatus(BaseModel):
    # pending | queued | in_progress | completed | error
    status: str
    correlation_id: str | None = None
    proposals: list[Proposal] = []
    run_url: str | None = None
    detail: str | None = None
    # Real page context (ARIA snapshot + link map) to ground code generation.
    page_context: str | None = None


class HealGroupRequest(BaseModel):
    correlation_ids: list[str] = Field(default_factory=list)


class HealGroup(BaseModel):
    signature: str
    cause: str
    correlation_ids: list[str] = []


class HealGroupResponse(BaseModel):
    groups: list[HealGroup] = []


class RunStep(BaseModel):
    title: str
    category: str | None = None
    duration: float | int | None = None
    ok: bool = True


class RunTest(BaseModel):
    """One test CASE in the run (a merged suite has many). Lets the UI show which
    tests passed/failed and each failure's own error, not just a count."""
    title: str
    status: str  # passed | failed | timedOut | interrupted | skipped
    duration: float | int | None = None
    error: str | None = None


class RunStatus(BaseModel):
    # pending (not materialised yet) | queued | in_progress | completed | error
    status: str
    passed: bool | None = None
    conclusion: str | None = None
    summary: dict | None = None
    screenshot_base64: str | None = None
    steps: list[RunStep] = []
    # Per-test-case outcomes so a run shows WHICH tests failed, not just a count.
    tests: list[RunTest] = []
    has_video: bool = False
    has_trace: bool = False
    correlation_id: str | None = None
    run_url: str | None = None
    detail: str | None = None
    # The failure reason (Playwright error of the first failing test), shown in
    # the UI so a failed run explains itself. Only set when the test failed.
    error_message: str | None = None
    # Flakiness fields — populated when the test ran more than once. `flaky` is
    # true when the repeats disagreed (some passed, some failed).
    runs: int | None = None
    passed_runs: int | None = None
    failed_runs: int | None = None
    pass_rate: float | None = None
    flaky: bool | None = None
