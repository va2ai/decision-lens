"""Critic agent — adversarial faithfulness audit.

Two-layer guard:
  1. Deterministic: every finding's supporting_source_ids must resolve to
     retrieved references. Any dangling id auto-flags the finding as
     'hallucination' / severity=block.
  2. LLM adversarial pass: subtler issues — overreach, weak citation,
     unsupported dates.

approved_finding_indices = the set of indices with NO block-severity flag.
The Report agent uses only these.
"""

from __future__ import annotations

from typing import Protocol

from api.prompts.critic import PROMPT_VERSION, SYSTEM, USER_TEMPLATE
from api.schemas.pipeline import (
    CriticFinding,
    CriticOutput,
    ReasoningOutput,
    RetrievalOutput,
)

__all__ = ["PROMPT_VERSION", "run"]


class _Client(Protocol):
    def structured(self, **kwargs: object) -> object: ...


def _format_findings(reasoning: ReasoningOutput) -> str:
    lines = []
    for i, f in enumerate(reasoning.findings):
        lines.append(
            f"[{i}] (issue={f.issue_index}, conf={f.confidence:.2f}) {f.finding_text}\n"
            f"    cites: {', '.join(f.supporting_source_ids)}"
        )
    return "\n".join(lines) or "(no findings)"


def _format_references(retrieval: RetrievalOutput) -> str:
    if not retrieval.references:
        return "(none)"
    return "\n".join(
        f"- {ref.source_id}: {ref.passage[:200]}..." for ref in retrieval.references
    )


def _deterministic_dangling_check(
    reasoning: ReasoningOutput, retrieval: RetrievalOutput
) -> list[CriticFinding]:
    """Layer 1: catch dangling source_ids without an LLM call."""
    valid = {ref.source_id for ref in retrieval.references}
    flags: list[CriticFinding] = []
    for i, f in enumerate(reasoning.findings):
        bad = [sid for sid in f.supporting_source_ids if sid not in valid]
        if bad:
            flags.append(
                CriticFinding(
                    target_index=i,
                    flag_type="hallucination",
                    explanation=f"Cited source_ids not in retrieval: {bad}",
                    severity="block",
                )
            )
    return flags


def run(
    reasoning: ReasoningOutput,
    retrieval: RetrievalOutput,
    *,
    client: _Client | None = None,
    poisoned: bool = False,
) -> CriticOutput:
    """Audit findings. If `poisoned`, every finding is auto-blocked."""
    if poisoned:
        flags = [
            CriticFinding(
                target_index=i,
                flag_type="hallucination",
                explanation="Upstream pipeline degraded; finding cannot be trusted.",
                severity="block",
            )
            for i, _ in enumerate(reasoning.findings)
        ]
        return CriticOutput(approved_finding_indices=[], flags=flags, overall_faithfulness_score=0.0)

    deterministic_flags = _deterministic_dangling_check(reasoning, retrieval)

    llm_flags: list[CriticFinding] = []
    llm_score = 1.0
    if client is not None and reasoning.findings:
        raw = client.structured(
            response_model=CriticOutput,
            system=SYSTEM,
            user=USER_TEMPLATE.format(
                findings_block=_format_findings(reasoning),
                references_block=_format_references(retrieval),
            ),
            max_tokens=1500,
        )
        assert isinstance(raw, CriticOutput)
        # Drop any LLM flag pointing at an out-of-range index — model hallucinated.
        for fl in raw.flags:
            if 0 <= fl.target_index < len(reasoning.findings):
                llm_flags.append(fl)
        llm_score = raw.overall_faithfulness_score

    all_flags = [*deterministic_flags, *llm_flags]
    blocked = {fl.target_index for fl in all_flags if fl.severity == "block"}
    approved = [i for i in range(len(reasoning.findings)) if i not in blocked]

    if not reasoning.findings:
        score = 0.0
    else:
        det_block_share = len({fl.target_index for fl in deterministic_flags}) / max(
            1, len(reasoning.findings)
        )
        # Combine: LLM score discounted by deterministic block rate.
        score = max(0.0, min(1.0, llm_score * (1.0 - det_block_share)))

    return CriticOutput(
        approved_finding_indices=approved,
        flags=all_flags,
        overall_faithfulness_score=round(score, 4),
    )
