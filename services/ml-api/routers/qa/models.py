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
