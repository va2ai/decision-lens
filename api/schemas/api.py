"""HTTP request/response models — kept separate from internal pipeline schemas."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from api.schemas.pipeline import AnalysisReport


class AnalysisRequest(BaseModel):
    """POST /analyze body."""

    raw_text: str = Field(min_length=50, description="The document text to analyze")
    filename: Optional[str] = None
    config: dict = Field(default_factory=dict, description="Optional per-run overrides")


class AnalysisResponse(BaseModel):
    """POST /analyze response."""

    run_id: UUID
    report: AnalysisReport


class ErrorResponse(BaseModel):
    error: str
    stage: str | None = None
    detail: str | None = None
