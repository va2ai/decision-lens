"""Full pipeline graph — Intake → Extraction → Retrieval → Reasoning → Critic → Report.

Failure semantics:
  - Intake: hard abort (LangGraph re-raises).
  - Extraction / Retrieval / Reasoning: soft-fail. The node catches its own
    exception, marks ctx.poisoned=True, appends a warning, and the graph
    continues to Critic.
  - Critic: hard abort if it itself errors. Respects ctx.poisoned by blocking
    every finding.
  - Report: always runs, propagates all warnings.
"""

from __future__ import annotations

from typing import Protocol

from langgraph.graph import END, StateGraph

from api.agents import critic as critic_agent
from api.agents import extraction as extraction_agent
from api.agents import intake as intake_agent
from api.agents import reasoning as reasoning_agent
from api.agents import report as report_agent
from api.agents import retrieval as retrieval_agent
from api.providers.llm import get_client
from api.retrieval.store import get_store
from api.schemas.pipeline import (
    AnalysisReport,
    ExtractionOutput,
    PipelineContext,
    ReasoningOutput,
    RetrievalOutput,
)


class _Client(Protocol):
    def structured(self, **kwargs: object) -> object: ...


# ---------------------------------------------------------------------------
# Node wrappers
# ---------------------------------------------------------------------------


def _intake_node(state: PipelineContext) -> dict:
    out = intake_agent.run(state.raw_text, client=get_client())
    return {"intake": out}


def _extraction_node(state: PipelineContext) -> dict:
    assert state.intake is not None
    try:
        out = extraction_agent.run(state.intake, client=get_client())
        return {"extraction": out}
    except Exception as e:  # noqa: BLE001
        return {
            "extraction": ExtractionOutput(issues=[], evidence=[], extraction_confidence=0.0),
            "poisoned": True,
            "warnings": [*state.warnings, f"Extraction failed: {type(e).__name__}: {e}"],
        }


def _retrieval_node(state: PipelineContext) -> dict:
    if state.extraction is None or not state.extraction.issues:
        return {"retrieval": RetrievalOutput(references=[], retrieval_warnings=["No issues."])}
    try:
        store = get_store()
        store.ensure_loaded()
        out = retrieval_agent.run(state.extraction, store=store)
        return {"retrieval": out}
    except Exception as e:  # noqa: BLE001
        return {
            "retrieval": RetrievalOutput(references=[], retrieval_warnings=["retrieval failed"]),
            "poisoned": True,
            "warnings": [*state.warnings, f"Retrieval failed: {type(e).__name__}: {e}"],
        }


def _reasoning_node(state: PipelineContext) -> dict:
    if state.extraction is None or state.retrieval is None:
        return {"reasoning": ReasoningOutput(findings=[])}
    try:
        out = reasoning_agent.run(state.extraction, state.retrieval, client=get_client())
        return {"reasoning": out}
    except Exception as e:  # noqa: BLE001
        return {
            "reasoning": ReasoningOutput(findings=[]),
            "poisoned": True,
            "warnings": [*state.warnings, f"Reasoning failed: {type(e).__name__}: {e}"],
        }


def _critic_node(state: PipelineContext) -> dict:
    if state.reasoning is None or state.retrieval is None:
        from api.schemas.pipeline import CriticOutput

        return {"critic": CriticOutput(approved_finding_indices=[], flags=[], overall_faithfulness_score=0.0)}
    out = critic_agent.run(
        state.reasoning,
        state.retrieval,
        client=get_client(),
        poisoned=state.poisoned,
    )
    return {"critic": out}


def _report_node(state: PipelineContext) -> dict:
    out = report_agent.run(state)
    return {"final_report": out}


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------


def build_graph() -> object:
    g: StateGraph = StateGraph(PipelineContext)
    g.add_node("intake", _intake_node)
    g.add_node("extraction", _extraction_node)
    g.add_node("retrieval", _retrieval_node)
    g.add_node("reasoning", _reasoning_node)
    g.add_node("critic", _critic_node)
    g.add_node("report", _report_node)

    g.set_entry_point("intake")
    g.add_edge("intake", "extraction")
    g.add_edge("extraction", "retrieval")
    g.add_edge("retrieval", "reasoning")
    g.add_edge("reasoning", "critic")
    g.add_edge("critic", "report")
    g.add_edge("report", END)
    return g.compile()


def run_analysis(raw_text: str) -> AnalysisReport:
    """End-to-end pipeline invocation. Returns the assembled AnalysisReport."""
    graph = build_graph()
    initial = PipelineContext(raw_text=raw_text)
    final = graph.invoke(initial)
    if isinstance(final, PipelineContext):
        ctx = final
    else:
        ctx = PipelineContext.model_validate(final)
    if ctx.final_report is None:
        raise RuntimeError("Pipeline did not produce a final_report")
    return ctx.final_report
