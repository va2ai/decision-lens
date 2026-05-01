"""Typed contracts for every stage of the analysis pipeline.

Each agent reads its declared input schema and emits its declared output schema.
The orchestrator passes typed artifacts between stages; nothing is a raw dict.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums and primitives
# ---------------------------------------------------------------------------


class DocumentType(str, Enum):
    ADMINISTRATIVE_DENIAL = "administrative_denial"
    LEGAL_LETTER = "legal_letter"
    APPEAL_DECISION = "appeal_decision"
    UNKNOWN = "unknown"


class AuthorityType(str, Enum):
    BINDING_REGULATION = "binding_regulation"
    PRECEDENTIAL_CASE = "precedential_case"
    AGENCY_POLICY = "agency_policy"
    SECONDARY = "secondary"


# ---------------------------------------------------------------------------
# Stage 1: Intake
# ---------------------------------------------------------------------------


class IntakeOutput(BaseModel):
    """Validated, normalized, classified document — the canonical record everything else reads."""

    normalized_text: str
    doc_type: DocumentType
    char_count: int = Field(ge=0)
    language: str = Field(default="en", description="ISO 639-1 language code")
    intake_warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 2: Extraction
# ---------------------------------------------------------------------------


class DocumentIssue(BaseModel):
    """A single decision-bearing issue identified in the document."""

    issue_text: str
    decision: Literal["denied", "approved", "deferred", "unclear"]
    stated_reason: str | None = None
    source_span: tuple[int, int] = Field(
        description="(start, end) char offsets into normalized_text"
    )
    confidence: float = Field(ge=0.0, le=1.0)


class EvidenceItem(BaseModel):
    """A single piece of evidence — present, missing, favorable, or adverse."""

    label: str
    description: str
    source_type: Literal["document", "external_record", "lay_statement", "missing"]
    favorability: Literal["favorable", "adverse", "neutral", "missing"]
    source_span: tuple[int, int] | None = None


class ExtractionOutput(BaseModel):
    issues: list[DocumentIssue]
    evidence: list[EvidenceItem] = Field(default_factory=list)
    parties: dict[str, str] = Field(
        default_factory=dict,
        description="e.g. {'claimant': 'Jane Demo', 'issuing_body': 'Demo Agency'}",
    )
    key_dates: dict[str, date] = Field(default_factory=dict)
    extraction_confidence: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Stage 3: Retrieval
# ---------------------------------------------------------------------------


class RetrievedReference(BaseModel):
    """A reference passage retrieved against an extracted issue."""

    issue_index: int = Field(ge=0)
    source_id: str
    source_title: str
    authority_type: AuthorityType
    passage: str
    url: str | None = None
    relevance_score: float = Field(ge=0.0, le=1.0)


class RetrievalOutput(BaseModel):
    references: list[RetrievedReference]
    retrieval_warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 4: Reasoning
# ---------------------------------------------------------------------------


class ReasoningFinding(BaseModel):
    """A single grounded argument synthesized from issues + retrieved references."""

    issue_index: int = Field(ge=0)
    finding_text: str
    supporting_source_ids: list[str] = Field(
        min_length=1,
        description="Every finding must cite at least one retrieved source",
    )
    confidence: float = Field(ge=0.0, le=1.0)


class ReasoningOutput(BaseModel):
    findings: list[ReasoningFinding]
    identified_weaknesses: list[str] = Field(default_factory=list)
    reasoning_trace: str = Field(
        default="",
        description="Chain-of-thought scratchpad — internal, not shown to end users",
    )


# ---------------------------------------------------------------------------
# Stage 5: Critic
# ---------------------------------------------------------------------------


class CriticFinding(BaseModel):
    """A single flag raised by the adversarial critic."""

    target_index: int = Field(ge=0, description="Index into ReasoningOutput.findings")
    flag_type: Literal["hallucination", "weak_citation", "overreach", "unsupported_date"]
    explanation: str
    severity: Literal["block", "warn"]


class CriticOutput(BaseModel):
    approved_finding_indices: list[int] = Field(default_factory=list)
    flags: list[CriticFinding] = Field(default_factory=list)
    overall_faithfulness_score: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Stage 6: Report (assembly only)
# ---------------------------------------------------------------------------


class Citation(BaseModel):
    """A reference as it appears in the final report."""

    source_id: str
    title: str
    authority_type: AuthorityType
    passage: str
    url: str | None = None
    validated: bool = False


class StrategyRecommendation(BaseModel):
    issue_index: int = Field(ge=0)
    recommended_action: str
    rationale: str
    priority: Literal["critical", "important", "optional"]
    supporting_source_ids: list[str] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    """Final structured output — only critic-approved findings appear here."""

    report_id: UUID = Field(default_factory=uuid4)
    doc_type: DocumentType
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    overall_confidence: float = Field(ge=0.0, le=1.0)
    faithfulness_score: float = Field(ge=0.0, le=1.0)

    issues: list[DocumentIssue]
    evidence: list[EvidenceItem]
    findings: list[ReasoningFinding]
    strategy: list[StrategyRecommendation]
    citations: list[Citation]
    critic_flags: list[CriticFinding]

    pipeline_warnings: list[str] = Field(default_factory=list)
    prompt_version: str = Field(
        description="e.g. 'intake:v1,extract:v1,retrieve:v1,reason:v1,critic:v1,report:v1'",
    )


# ---------------------------------------------------------------------------
# Pipeline context — accumulates as agents run
# ---------------------------------------------------------------------------


class PipelineContext(BaseModel):
    """Shared state passed between agents. The orchestrator owns this."""

    run_id: UUID = Field(default_factory=uuid4)
    raw_text: str
    intake: IntakeOutput | None = None
    extraction: ExtractionOutput | None = None
    retrieval: RetrievalOutput | None = None
    reasoning: ReasoningOutput | None = None
    critic: CriticOutput | None = None
    poisoned: bool = False
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------


class TraceEvent(BaseModel):
    """One span in the agent execution trace."""

    run_id: UUID
    span_id: UUID = Field(default_factory=uuid4)
    parent_span_id: UUID | None = None
    agent: str
    status: Literal["start", "success", "validation_error", "retry", "failure"]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    error_type: str | None = None
    metadata: dict = Field(default_factory=dict)
