"""Reasoning agent tests — citation grounding (drops findings that cite unknown source_ids)."""

from __future__ import annotations

from typing import Any

from api.agents.reasoning import run
from api.schemas.pipeline import (
    AuthorityType,
    DocumentIssue,
    ExtractionOutput,
    ReasoningFinding,
    ReasoningOutput,
    RetrievalOutput,
    RetrievedReference,
)


class StubClient:
    def __init__(self, payload: ReasoningOutput) -> None:
        self.payload = payload

    def structured(self, **_: Any) -> Any:
        return self.payload


def _make_extraction() -> ExtractionOutput:
    return ExtractionOutput(
        issues=[
            DocumentIssue(
                issue_text="Service connection denied for back condition",
                decision="denied",
                stated_reason="No nexus.",
                source_span=(0, 30),
                confidence=0.8,
            ),
        ],
        extraction_confidence=0.8,
    )


def _make_retrieval(*ids: str) -> RetrievalOutput:
    return RetrievalOutput(
        references=[
            RetrievedReference(
                issue_index=0,
                source_id=sid,
                source_title=f"{sid} title",
                authority_type=AuthorityType.BINDING_REGULATION,
                passage="passage",
                relevance_score=0.9,
            )
            for sid in ids
        ]
    )


def test_drops_findings_with_unknown_source_ids() -> None:
    payload = ReasoningOutput(
        findings=[
            ReasoningFinding(
                issue_index=0,
                finding_text="Real finding [REG-3.303].",
                supporting_source_ids=["REG-3.303"],
                confidence=0.85,
            ),
            ReasoningFinding(
                issue_index=0,
                finding_text="Phantom finding [REG-FAKE].",
                supporting_source_ids=["REG-FAKE"],
                confidence=0.6,
            ),
        ]
    )
    out = run(_make_extraction(), _make_retrieval("REG-3.303"), client=StubClient(payload))
    assert len(out.findings) == 1
    assert out.findings[0].finding_text.startswith("Real finding")


def test_keeps_partial_overlap_drops_dangling_ids() -> None:
    payload = ReasoningOutput(
        findings=[
            ReasoningFinding(
                issue_index=0,
                finding_text="Mixed finding citing two sources.",
                supporting_source_ids=["REG-3.303", "REG-FAKE"],
                confidence=0.75,
            )
        ]
    )
    out = run(_make_extraction(), _make_retrieval("REG-3.303"), client=StubClient(payload))
    assert len(out.findings) == 1
    assert out.findings[0].supporting_source_ids == ["REG-3.303"]


def test_returns_empty_when_no_issues() -> None:
    out = run(
        ExtractionOutput(issues=[], extraction_confidence=0.0),
        _make_retrieval(),
        client=StubClient(ReasoningOutput(findings=[])),
    )
    assert out.findings == []
