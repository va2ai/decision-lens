"""Schema contract tests — these guard the typed boundaries between agents."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.schemas.pipeline import (
    AnalysisReport,
    AuthorityType,
    Citation,
    DocumentIssue,
    DocumentType,
    EvidenceItem,
    ExtractionOutput,
    IntakeOutput,
    ReasoningFinding,
    ReasoningOutput,
    RetrievedReference,
)


def test_intake_output_minimal_valid() -> None:
    out = IntakeOutput(
        normalized_text="A short administrative denial.",
        doc_type=DocumentType.ADMINISTRATIVE_DENIAL,
        char_count=30,
    )
    assert out.language == "en"
    assert out.intake_warnings == []


def test_document_issue_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        DocumentIssue(
            issue_text="x",
            decision="denied",
            source_span=(0, 1),
            confidence=1.5,  # invalid
        )


def test_schema_rejects_finding_without_any_citation() -> None:
    """Hard contract: a ReasoningFinding without at least one source_id never
    constructs. Every other layer downstream (Critic deterministic guard,
    Reasoning post-filter, eval `citation_grounding` metric) builds on top of
    this — it is the foundation of the project's no-ungrounded-claims policy.
    """
    with pytest.raises(ValidationError):
        ReasoningFinding(
            issue_index=0,
            finding_text="An unsupported claim.",
            supporting_source_ids=[],  # invalid: min_length=1
            confidence=0.8,
        )


def test_extraction_output_round_trips() -> None:
    out = ExtractionOutput(
        issues=[
            DocumentIssue(
                issue_text="Claim denied for insufficient evidence.",
                decision="denied",
                stated_reason="No supporting documentation submitted.",
                source_span=(0, 39),
                confidence=0.9,
            )
        ],
        evidence=[
            EvidenceItem(
                label="medical record",
                description="Referenced but not in record.",
                source_type="missing",
                favorability="missing",
            )
        ],
        extraction_confidence=0.85,
    )
    parsed = ExtractionOutput.model_validate_json(out.model_dump_json())
    assert parsed.issues[0].decision == "denied"
    assert parsed.evidence[0].favorability == "missing"


def test_analysis_report_has_required_prompt_version() -> None:
    with pytest.raises(ValidationError):
        AnalysisReport(  # type: ignore[call-arg]
            doc_type=DocumentType.UNKNOWN,
            overall_confidence=0.0,
            faithfulness_score=0.0,
            issues=[],
            evidence=[],
            findings=[],
            strategy=[],
            citations=[],
            critic_flags=[],
            # prompt_version omitted — should fail
        )


def test_analysis_report_serializes_cleanly() -> None:
    report = AnalysisReport(
        doc_type=DocumentType.ADMINISTRATIVE_DENIAL,
        overall_confidence=0.7,
        faithfulness_score=0.85,
        issues=[],
        evidence=[],
        findings=[],
        strategy=[],
        citations=[
            Citation(
                source_id="REG-001",
                title="Demo regulation",
                authority_type=AuthorityType.BINDING_REGULATION,
                passage="Sample passage.",
            )
        ],
        critic_flags=[],
        prompt_version="stub:v0",
    )
    payload = report.model_dump_json()
    parsed = AnalysisReport.model_validate_json(payload)
    assert parsed.faithfulness_score == 0.85
    assert parsed.citations[0].authority_type is AuthorityType.BINDING_REGULATION


def test_retrieved_reference_score_bounds() -> None:
    with pytest.raises(ValidationError):
        RetrievedReference(
            issue_index=0,
            source_id="X",
            source_title="X",
            authority_type=AuthorityType.SECONDARY,
            passage="x",
            relevance_score=1.5,  # invalid
        )


def test_reasoning_output_default_fields() -> None:
    out = ReasoningOutput(findings=[])
    assert out.identified_weaknesses == []
    assert out.reasoning_trace == ""
