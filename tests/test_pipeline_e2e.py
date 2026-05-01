"""End-to-end pipeline test — all six nodes wired, LLM stubbed.

This test runs the full LangGraph DAG against case_001 with stubbed clients
to verify that artifact handoffs, soft-fail semantics, and the final report
assembly all work together.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from api.agents import graph as graph_mod
from api.agents.intake import IntakeClassification
from api.schemas.pipeline import (
    AuthorityType,
    CriticOutput,
    DocumentIssue,
    EvidenceItem,
    ExtractionOutput,
    ReasoningFinding,
    ReasoningOutput,
    RetrievedReference,
)


SAMPLE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "sample_cases"
    / "case_001_administrative_denial.txt"
)


class MultiStageStubClient:
    """Returns canned responses keyed by response_model type."""

    def __init__(self, **by_model: Any) -> None:
        self._by_model = by_model

    def structured(self, *, response_model: type, **_: Any) -> Any:
        key = response_model.__name__
        if key not in self._by_model:
            raise AssertionError(f"No stub for {key}")
        return self._by_model[key]


class StubStore:
    """Deterministic retrieval store: returns the same fixed references every time."""

    def __init__(self, references: list[RetrievedReference]) -> None:
        self._refs = references

    def ensure_loaded(self) -> None:  # noqa: D401
        return None

    def query(self, *, query_text: str, top_k: int = 3) -> list[dict]:  # noqa: ARG002
        return [
            {
                "source_id": r.source_id,
                "meta": {
                    "title": r.source_title,
                    "authority_type": r.authority_type.value,
                    "passage": r.passage,
                    "url": r.url or "",
                },
                "distance": (1.0 / r.relevance_score) - 1.0,
            }
            for r in self._refs[:top_k]
        ]

    def to_reference(self, *, issue_index: int, hit: dict) -> RetrievedReference:
        meta = hit["meta"]
        return RetrievedReference(
            issue_index=issue_index,
            source_id=hit["source_id"],
            source_title=meta["title"],
            authority_type=AuthorityType(meta["authority_type"]),
            passage=meta["passage"],
            url=meta["url"] or None,
            relevance_score=round(1.0 / (1.0 + max(0.0, hit["distance"])), 4),
        )


@pytest.fixture
def stub_client(monkeypatch: pytest.MonkeyPatch) -> MultiStageStubClient:
    text = SAMPLE.read_text(encoding="utf-8")
    n = len(text)

    client = MultiStageStubClient(
        IntakeClassification=IntakeClassification(
            doc_type="administrative_denial",
            language="en",
            intake_warnings=[],
        ),
        ExtractionOutput=ExtractionOutput(
            issues=[
                DocumentIssue(
                    issue_text="Service connection for chronic respiratory condition denied",
                    decision="denied",
                    stated_reason="Examiner opined less likely than not; long latency.",
                    source_span=(0, min(200, n)),
                    confidence=0.9,
                ),
            ],
            evidence=[
                EvidenceItem(
                    label="missing private nexus opinion",
                    description="No private medical opinion linking exposure to current condition.",
                    source_type="missing",
                    favorability="missing",
                ),
            ],
            parties={"claimant": "Jane Demo", "issuing_body": "Demo Review Board"},
            extraction_confidence=0.9,
        ),
        ReasoningOutput=ReasoningOutput(
            findings=[
                ReasoningFinding(
                    issue_index=0,
                    finding_text=(
                        "The agency examination is inadequate under [REG-3.159] because "
                        "it failed to address a credibly raised secondary-causation theory."
                    ),
                    supporting_source_ids=["REG-3.159", "CASE-DEMO-001"],
                    confidence=0.82,
                ),
            ],
            identified_weaknesses=[
                "Examiner did not address secondary-causation theory raised by the record."
            ],
        ),
        CriticOutput=CriticOutput(
            approved_finding_indices=[0],
            flags=[],
            overall_faithfulness_score=0.92,
        ),
    )
    refs = [
        RetrievedReference(
            issue_index=0,
            source_id="REG-3.159",
            source_title="Demo § 3.159(c)(4) — Duty to provide adequate examination",
            authority_type=AuthorityType.BINDING_REGULATION,
            passage="When the agency provides a medical examination, it must be adequate.",
            relevance_score=0.92,
        ),
        RetrievedReference(
            issue_index=0,
            source_id="CASE-DEMO-001",
            source_title="Demo v. Secretary, No. 00-0001",
            authority_type=AuthorityType.PRECEDENTIAL_CASE,
            passage="An inadequate examination requires remand.",
            relevance_score=0.85,
        ),
    ]
    monkeypatch.setattr(graph_mod, "get_client", lambda: client)
    monkeypatch.setattr(graph_mod, "get_store", lambda: StubStore(refs))
    return client


def test_full_pipeline_produces_grounded_report(stub_client: MultiStageStubClient) -> None:
    text = SAMPLE.read_text(encoding="utf-8")
    report = graph_mod.run_analysis(text)

    # Intake classification reached the report
    assert report.doc_type.value == "administrative_denial"

    # Extraction kept its issue
    assert len(report.issues) >= 1

    # Retrieval ran against the real ChromaDB store; references should resolve
    assert len(report.citations) > 0

    # Reasoning finding survived the critic
    assert len(report.findings) == 1
    assert "REG-3.159" in report.findings[0].supporting_source_ids

    # Strategy was derived from the approved finding
    assert len(report.strategy) == 1

    # Confidence reflects the approved finding's confidence
    assert report.overall_confidence == pytest.approx(0.82, rel=1e-3)
    assert report.faithfulness_score == pytest.approx(0.92, rel=1e-3)

    # Prompt version is well-formed
    assert "intake:v1" in report.prompt_version
    assert "report:v1" in report.prompt_version

    # No critic flags on a clean case
    assert report.critic_flags == []
