"""Testwright (QA Automation) — request/response schemas."""

from pydantic import BaseModel, Field

from routers.qa import config


class GenerateRequest(BaseModel):
    instructions: str = Field(..., min_length=1, max_length=config.MAX_INSTRUCTIONS)
    base_url: str = Field("", max_length=config.MAX_BASE_URL)
    test_name: str = Field("", max_length=config.MAX_NAME)


class GenerateResponse(BaseModel):
    code: str
    provider: str | None = None


class AssertRequest(BaseModel):
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


class HealRequest(BaseModel):
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


class RunStatus(BaseModel):
    # pending (not materialised yet) | queued | in_progress | completed | error
    status: str
    passed: bool | None = None
    conclusion: str | None = None
    summary: dict | None = None
    screenshot_base64: str | None = None
    steps: list[RunStep] = []
    has_video: bool = False
    has_trace: bool = False
    correlation_id: str | None = None
    run_url: str | None = None
    detail: str | None = None
    # Flakiness fields — populated when the test ran more than once. `flaky` is
    # true when the repeats disagreed (some passed, some failed).
    runs: int | None = None
    passed_runs: int | None = None
    failed_runs: int | None = None
    pass_rate: float | None = None
    flaky: bool | None = None
