"""Report agent tests — assembly only, only critic-approved findings appear."""

from __future__ import annotations

from api.agents.report import run as report_run
from api.schemas.pipeline import (
    AuthorityType,
    CriticFinding,
    CriticOutput,
    DocumentIssue,
    DocumentType,
    EvidenceItem,
    ExtractionOutput,
    IntakeOutput,
    PipelineContext,
    ReasoningFinding,
    ReasoningOutput,
    RetrievalOutput,
    RetrievedReference,
)


def _ctx(*, approved: list[int], flagged: list[int]) -> PipelineContext:
    findings = [
        ReasoningFinding(
            issue_index=0,
            finding_text=f"finding {i}",
            supporting_source_ids=["REG-3.303"],
            confidence=0.85,
        )
        for i in range(2)
    ]
    return PipelineContext(
        raw_text="x" * 200,
        intake=IntakeOutput(
            normalized_text="x" * 200,
            doc_type=DocumentType.ADMINISTRATIVE_DENIAL,
            char_count=200,
            intake_warnings=["intake-warning-A"],
        ),
        extraction=ExtractionOutput(
            issues=[
                DocumentIssue(
                    issue_text="i", decision="denied", source_span=(0, 5), confidence=0.8
                )
            ],
            evidence=[
                EvidenceItem(
                    label="ev1", description="x", source_type="document", favorability="favorable"
                )
            ],
            extraction_confidence=0.85,
        ),
        retrieval=RetrievalOutput(
            references=[
                RetrievedReference(
                    issue_index=0,
                    source_id="REG-3.303",
                    source_title="t",
                    authority_type=AuthorityType.BINDING_REGULATION,
                    passage="p",
                    relevance_score=0.9,
                )
            ],
            retrieval_warnings=["retrieval-warning-B"],
        ),
        reasoning=ReasoningOutput(findings=findings),
        critic=CriticOutput(
            approved_finding_indices=approved,
            flags=[
                CriticFinding(
                    target_index=i,
                    flag_type="weak_citation",
                    explanation="w",
                    severity="block" if i in flagged else "warn",
                )
                for i in flagged
            ],
            overall_faithfulness_score=0.75,
        ),
    )


def test_only_approved_findings_in_report() -> None:
    ctx = _ctx(approved=[0], flagged=[1])
    rpt = report_run(ctx)
    assert len(rpt.findings) == 1
    assert rpt.findings[0].finding_text == "finding 0"
    # Strategy is derived from approved findings only.
    assert len(rpt.strategy) == 1


def test_propagates_all_warnings() -> None:
    ctx = _ctx(approved=[0, 1], flagged=[])
    rpt = report_run(ctx)
    assert "intake-warning-A" in rpt.pipeline_warnings
    assert "retrieval-warning-B" in rpt.pipeline_warnings


def test_overall_confidence_is_mean_of_approved() -> None:
    ctx = _ctx(approved=[0, 1], flagged=[])
    rpt = report_run(ctx)
    assert rpt.overall_confidence == 0.85


def test_citations_emitted_from_retrieval() -> None:
    ctx = _ctx(approved=[0], flagged=[])
    rpt = report_run(ctx)
    assert len(rpt.citations) == 1
    assert rpt.citations[0].source_id == "REG-3.303"
    assert rpt.citations[0].validated is False  # validator wired in Phase 5


def test_prompt_version_present_and_well_formed() -> None:
    ctx = _ctx(approved=[0], flagged=[])
    rpt = report_run(ctx)
    pv = rpt.prompt_version
    for stage in ["intake", "extraction", "retrieval", "reasoning", "critic", "report"]:
        assert stage in pv


def test_poisoned_pipeline_surfaces_warning() -> None:
    ctx = _ctx(approved=[], flagged=[0, 1])
    ctx = ctx.model_copy(update={"poisoned": True})
    rpt = report_run(ctx)
    assert any("poisoned" in w.lower() for w in rpt.pipeline_warnings)
    assert rpt.findings == []
