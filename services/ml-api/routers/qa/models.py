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


class RunRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=config.MAX_RUN_CODE)
    base_url: str = Field("", max_length=config.MAX_BASE_URL)
    test_name: str = Field("", max_length=config.MAX_NAME)


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
