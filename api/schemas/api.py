"""HTTP request/response models — kept separate from internal pipeline schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from api.schemas.pipeline import AnalysisReport


class AnalysisRequest(BaseModel):
    """POST /analyze body."""

    raw_text: str = Field(min_length=50, description="The document text to analyze")
    filename: Optional[str] = None
    config: dict = Field(default_factory=dict, description="Optional per-run overrides")


class AnalysisResponse(BaseModel):
    """POST /analyze response."""

    run_id: str
    report: AnalysisReport


class SpanView(BaseModel):
    name: str
    started_at: float
    ended_at: float | None
    duration_ms: float | None
    status: str
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceView(BaseModel):
    """GET /traces/{run_id} response."""

    run_id: str
    started_at: float
    ended_at: float | None
    duration_ms: float | None
    spans: list[SpanView]


class ErrorResponse(BaseModel):
    error: str
    stage: str | None = None
    detail: str | None = None
