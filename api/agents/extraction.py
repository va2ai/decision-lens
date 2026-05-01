"""Extraction agent — span-grounded structured extraction."""

from __future__ import annotations

from typing import Protocol

from api.prompts.extraction import PROMPT_VERSION, SYSTEM, USER_TEMPLATE
from api.schemas.pipeline import (
    DocumentIssue,
    EvidenceItem,
    ExtractionOutput,
    IntakeOutput,
)

__all__ = ["PROMPT_VERSION", "run", "validate_spans"]


class _Client(Protocol):
    def structured(self, **kwargs: object) -> object: ...


def validate_spans(out: ExtractionOutput, normalized_text: str) -> tuple[ExtractionOutput, list[str]]:
    """Drop issues whose source_span is out of range. Return cleaned output + warnings.

    The model is asked to produce valid spans; this layer enforces the contract.
    """
    n = len(normalized_text)
    warnings: list[str] = []

    kept_issues: list[DocumentIssue] = []
    for i, iss in enumerate(out.issues):
        start, end = iss.source_span
        if 0 <= start <= end <= n:
            kept_issues.append(iss)
        else:
            warnings.append(
                f"Issue {i} dropped: span ({start},{end}) out of range for {n}-char doc."
            )

    kept_evidence: list[EvidenceItem] = []
    for j, ev in enumerate(out.evidence):
        if ev.source_span is None:
            kept_evidence.append(ev)
            continue
        s, e = ev.source_span
        if 0 <= s <= e <= n:
            kept_evidence.append(ev)
        else:
            warnings.append(
                f"Evidence {j} '{ev.label}' dropped: span ({s},{e}) out of range."
            )

    cleaned = out.model_copy(update={"issues": kept_issues, "evidence": kept_evidence})
    return cleaned, warnings


def run(intake: IntakeOutput, *, client: _Client) -> ExtractionOutput:
    """Extract structured fields from the normalized document."""
    raw = client.structured(
        response_model=ExtractionOutput,
        system=SYSTEM,
        user=USER_TEMPLATE.format(
            char_count=intake.char_count,
            text=intake.normalized_text[:12000],
        ),
        max_tokens=2000,
    )
    assert isinstance(raw, ExtractionOutput)
    cleaned, _warnings = validate_spans(raw, intake.normalized_text)
    return cleaned
