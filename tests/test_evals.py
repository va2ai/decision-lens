"""Eval scoring tests — exercise the deterministic metrics without running the pipeline."""

from __future__ import annotations

from datetime import datetime, timezone

from api.evals.runner import _score_case
from api.schemas.pipeline import (
    AnalysisReport,
    AuthorityType,
    Citation,
    CriticFinding,
    DocumentIssue,
    DocumentType,
    EvidenceItem,
    ReasoningFinding,
)


def _make_report(
    *,
    issues: list[DocumentIssue],
    citations: list[Citation],
    findings: list[ReasoningFinding],
    flags: list[CriticFinding] | None = None,
) -> AnalysisReport:
    return AnalysisReport(
        doc_type=DocumentType.ADMINISTRATIVE_DENIAL,
        issues=issues,
        evidence=[],
        findings=findings,
        citations=citations,
        strategy=[],
        critic_flags=flags or [],
        pipeline_warnings=[],
        overall_confidence=0.8,
        faithfulness_score=0.9,
        prompt_version="intake:v1|extraction:v1|retrieval:v1|reasoning:v1|critic:v1|report:v1",
        generated_at=datetime.now(tz=timezone.utc),
    )


def _issue(text: str, decision: str = "denied") -> DocumentIssue:
    return DocumentIssue(
        issue_text=text,
        decision=decision,  # type: ignore[arg-type]
        stated_reason=None,
        source_span=(0, 50),
        confidence=0.8,
    )


def _cite(sid: str) -> Citation:
    return Citation(
        source_id=sid,
        title=sid,
        authority_type=AuthorityType.BINDING_REGULATION,
        passage="p",
        validated=False,
    )


def _finding(*ids: str) -> ReasoningFinding:
    return ReasoningFinding(
        issue_index=0,
        finding_text=f"finding citing {','.join(ids)}",
        supporting_source_ids=list(ids),
        confidence=0.8,
    )


def test_clean_case_passes() -> None:
    case = {
        "id": "x",
        "expected_issue_keywords": ["respiratory", "service connection"],
        "expected_decision": "denied",
        "required_source_ids": ["REG-3.159"],
    }
    report = _make_report(
        issues=[_issue("Respiratory service connection denied")],
        citations=[_cite("REG-3.159")],
        findings=[_finding("REG-3.159")],
    )
    res = _score_case(case, report)
    assert res.passed
    assert res.issue_recall == 1.0
    assert res.decision_match
    assert res.citation_grounding == 1.0
    assert res.required_source_recall == 1.0
    assert res.faithfulness == 1.0


def test_dangling_finding_id_lowers_grounding() -> None:
    case = {"id": "x", "expected_issue_keywords": [], "expected_decision": None,
            "required_source_ids": []}
    report = _make_report(
        issues=[_issue("y")],
        citations=[_cite("REG-A")],
        findings=[_finding("REG-A", "REG-PHANTOM")],
    )
    res = _score_case(case, report)
    assert res.citation_grounding == 0.5


def test_missing_required_source_fails() -> None:
    case = {
        "id": "x",
        "expected_issue_keywords": ["foo"],
        "expected_decision": "denied",
        "required_source_ids": ["REG-3.159", "REG-3.310"],
    }
    report = _make_report(
        issues=[_issue("foo case")],
        citations=[_cite("REG-3.159")],  # only one of two required
        findings=[_finding("REG-3.159")],
    )
    res = _score_case(case, report)
    assert res.required_source_recall == 0.5
    assert res.passed  # 0.5 is the boundary


def test_block_flag_kills_pass() -> None:
    case = {"id": "x", "expected_issue_keywords": [], "expected_decision": "denied",
            "required_source_ids": []}
    flag = CriticFinding(
        target_index=0, flag_type="hallucination", explanation="bad", severity="block"
    )
    report = _make_report(
        issues=[_issue("y")],
        citations=[_cite("REG-A")],
        findings=[_finding("REG-A")],
        flags=[flag],
    )
    res = _score_case(case, report)
    assert res.had_block_flag
    assert not res.passed
    assert res.faithfulness == 0.0


def test_keyword_partial_recall() -> None:
    case = {
        "id": "x",
        "expected_issue_keywords": ["alpha", "beta", "gamma"],
        "expected_decision": "denied",
        "required_source_ids": [],
    }
    report = _make_report(
        issues=[_issue("alpha and beta but not the third")],
        citations=[],
        findings=[],
    )
    res = _score_case(case, report)
    assert res.issue_recall == round(2 / 3, 3)
