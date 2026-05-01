"""Extraction agent tests — span grounding + invalid-span rejection."""

from __future__ import annotations

from typing import Any

from api.agents.extraction import run, validate_spans
from api.schemas.pipeline import (
    DocumentIssue,
    DocumentType,
    EvidenceItem,
    ExtractionOutput,
    IntakeOutput,
)


class StubClient:
    def __init__(self, payload: ExtractionOutput) -> None:
        self.payload = payload

    def structured(self, **_: Any) -> Any:
        return self.payload


def _intake(text: str) -> IntakeOutput:
    return IntakeOutput(
        normalized_text=text,
        doc_type=DocumentType.ADMINISTRATIVE_DENIAL,
        char_count=len(text),
    )


def test_validate_spans_keeps_valid_drops_invalid() -> None:
    text = "A short denial document with claim language."
    raw = ExtractionOutput(
        issues=[
            DocumentIssue(
                issue_text="Valid", decision="denied", source_span=(0, 7), confidence=0.9
            ),
            DocumentIssue(
                issue_text="OOR", decision="denied", source_span=(0, 9999), confidence=0.5
            ),
        ],
        evidence=[
            EvidenceItem(
                label="ok", description="x", source_type="document",
                favorability="favorable", source_span=(0, 5),
            ),
            EvidenceItem(
                label="bad", description="x", source_type="document",
                favorability="favorable", source_span=(100, 9999),
            ),
        ],
        extraction_confidence=0.7,
    )
    cleaned, warnings = validate_spans(raw, text)
    assert len(cleaned.issues) == 1
    assert cleaned.issues[0].issue_text == "Valid"
    assert len(cleaned.evidence) == 1
    assert any("Issue 1" in w for w in warnings)
    assert any("bad" in w for w in warnings)


def test_run_drops_invalid_spans_via_validation() -> None:
    text = "Demo denial document. " * 10
    payload = ExtractionOutput(
        issues=[
            DocumentIssue(
                issue_text="Real issue", decision="denied",
                source_span=(0, 20), confidence=0.85,
            ),
            DocumentIssue(
                issue_text="Phantom issue", decision="denied",
                source_span=(99999, 100000), confidence=0.7,
            ),
        ],
        extraction_confidence=0.8,
    )
    out = run(_intake(text), client=StubClient(payload))
    assert len(out.issues) == 1
    assert out.issues[0].issue_text == "Real issue"


def test_run_passes_extraction_through_when_all_spans_valid() -> None:
    text = "Demo denial document. " * 20
    payload = ExtractionOutput(
        issues=[
            DocumentIssue(
                issue_text="i", decision="approved",
                source_span=(0, 10), confidence=0.95,
            )
        ],
        parties={"claimant": "Jane Demo"},
        extraction_confidence=0.9,
    )
    out = run(_intake(text), client=StubClient(payload))
    assert len(out.issues) == 1
    assert out.parties["claimant"] == "Jane Demo"
    assert out.extraction_confidence == 0.9
