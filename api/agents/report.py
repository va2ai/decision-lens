"""Report agent — assembly only, no generation.

Emits an AnalysisReport from the upstream artifacts. Only critic-approved
findings appear; deterministic strategy recommendations are derived from those
findings; pipeline_warnings propagate from every stage with no silent drops.
"""

from __future__ import annotations

from statistics import mean

from api.schemas.pipeline import (
    AnalysisReport,
    Citation,
    PipelineContext,
    StrategyRecommendation,
)

__all__ = ["PROMPT_VERSION", "run"]

PROMPT_VERSION = "report:v1"  # No prompt — but versioned for traceability.


def _strategy_from_findings(reasoning, critic) -> list[StrategyRecommendation]:
    """Promote each approved finding into a strategy recommendation."""
    recs: list[StrategyRecommendation] = []
    for idx in critic.approved_finding_indices:
        f = reasoning.findings[idx]
        priority = (
            "critical" if f.confidence >= 0.8 else "important" if f.confidence >= 0.5 else "optional"
        )
        recs.append(
            StrategyRecommendation(
                issue_index=f.issue_index,
                recommended_action=f.finding_text,
                rationale=f"Supported by {', '.join(f.supporting_source_ids)}.",
                priority=priority,
                supporting_source_ids=f.supporting_source_ids,
            )
        )
    return recs


def _citations_from_retrieval(retrieval) -> list[Citation]:
    return [
        Citation(
            source_id=ref.source_id,
            title=ref.source_title,
            authority_type=ref.authority_type,
            passage=ref.passage,
            url=ref.url,
            validated=False,  # Phase 5 wires the validator
        )
        for ref in retrieval.references
    ]


def _prompt_version_string() -> str:
    from api.prompts import critic as critic_prompt
    from api.prompts import extraction as extraction_prompt
    from api.prompts import intake as intake_prompt
    from api.prompts import reasoning as reasoning_prompt

    return ",".join(
        [
            intake_prompt.PROMPT_VERSION,
            extraction_prompt.PROMPT_VERSION,
            "retrieval:v1",
            reasoning_prompt.PROMPT_VERSION,
            critic_prompt.PROMPT_VERSION,
            PROMPT_VERSION,
        ]
    )


def run(ctx: PipelineContext) -> AnalysisReport:
    assert ctx.intake is not None, "Report stage requires Intake to have run"

    extraction = ctx.extraction
    retrieval = ctx.retrieval
    reasoning = ctx.reasoning
    critic = ctx.critic

    issues = list(extraction.issues) if extraction else []
    evidence = list(extraction.evidence) if extraction else []

    approved_findings = []
    if reasoning and critic:
        approved_findings = [reasoning.findings[i] for i in critic.approved_finding_indices]

    if approved_findings:
        overall_conf = round(mean(f.confidence for f in approved_findings), 4)
    elif issues:
        overall_conf = round(mean(i.confidence for i in issues) / 2, 4)  # halved when no findings
    else:
        overall_conf = 0.0

    faithfulness = critic.overall_faithfulness_score if critic else 0.0

    pipeline_warnings: list[str] = []
    pipeline_warnings.extend(ctx.intake.intake_warnings)
    if extraction is None:
        pipeline_warnings.append("Extraction stage produced no output.")
    if retrieval is not None:
        pipeline_warnings.extend(retrieval.retrieval_warnings)
    if reasoning is None:
        pipeline_warnings.append("Reasoning stage produced no output.")
    if ctx.poisoned:
        pipeline_warnings.append("Pipeline marked poisoned — degraded report.")
    pipeline_warnings.extend(ctx.warnings)

    return AnalysisReport(
        doc_type=ctx.intake.doc_type,
        overall_confidence=overall_conf,
        faithfulness_score=faithfulness,
        issues=issues,
        evidence=evidence,
        findings=approved_findings,
        strategy=_strategy_from_findings(reasoning, critic) if reasoning and critic else [],
        citations=_citations_from_retrieval(retrieval) if retrieval else [],
        critic_flags=critic.flags if critic else [],
        pipeline_warnings=pipeline_warnings,
        prompt_version=_prompt_version_string(),
    )
