"""Reasoning agent — synthesize cited findings.

Takes issues + retrieved references, returns ReasoningOutput. The schema
already enforces min_length=1 on supporting_source_ids, so the model cannot
emit a finding with no citation. This agent additionally drops findings whose
citations don't resolve to retrieved source_ids before returning.
"""

from __future__ import annotations

from typing import Protocol

from api.prompts.reasoning import PROMPT_VERSION, SYSTEM, USER_TEMPLATE
from api.schemas.pipeline import ExtractionOutput, ReasoningOutput, RetrievalOutput

__all__ = ["PROMPT_VERSION", "run"]


class _Client(Protocol):
    def structured(self, **kwargs: object) -> object: ...


def _format_issues(extraction: ExtractionOutput) -> str:
    lines = []
    for i, iss in enumerate(extraction.issues):
        lines.append(
            f"[{i}] {iss.issue_text} (decision={iss.decision})\n"
            f"    stated_reason: {iss.stated_reason or '(none)'}"
        )
    return "\n".join(lines) or "(no issues extracted)"


def _format_references(retrieval: RetrievalOutput) -> str:
    if not retrieval.references:
        return "(no authorities retrieved)"
    lines = []
    for ref in retrieval.references:
        lines.append(
            f"- {ref.source_id} | {ref.authority_type.value} | issue {ref.issue_index}\n"
            f"  {ref.source_title}\n"
            f"  {ref.passage}"
        )
    return "\n".join(lines)


def run(
    extraction: ExtractionOutput,
    retrieval: RetrievalOutput,
    *,
    client: _Client,
) -> ReasoningOutput:
    """Synthesize grounded findings."""
    if not extraction.issues:
        return ReasoningOutput(findings=[], identified_weaknesses=["No issues to reason over."])

    valid_source_ids = {ref.source_id for ref in retrieval.references}

    raw = client.structured(
        response_model=ReasoningOutput,
        system=SYSTEM,
        user=USER_TEMPLATE.format(
            issues_block=_format_issues(extraction),
            references_block=_format_references(retrieval),
        ),
        max_tokens=2000,
    )
    assert isinstance(raw, ReasoningOutput)

    # Deterministic post-pass: drop any finding that cites a source_id we
    # don't actually have. The Critic will see only well-grounded candidates.
    cleaned = []
    for finding in raw.findings:
        good = [sid for sid in finding.supporting_source_ids if sid in valid_source_ids]
        if good:
            cleaned.append(finding.model_copy(update={"supporting_source_ids": good}))
    return raw.model_copy(update={"findings": cleaned})
