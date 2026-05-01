"""LangGraph state machine wiring the pipeline nodes together.

Phase 1: only the Intake node is wired. The graph compiles and runs; downstream
nodes (extraction, retrieval, reasoning, critic, report) will be added in
Phase 2 as conditional edges off this graph.
"""

from __future__ import annotations

from typing import Protocol

from langgraph.graph import END, StateGraph

from api.agents import intake as intake_agent
from api.providers.llm import get_client
from api.schemas.pipeline import PipelineContext


class _Client(Protocol):
    def structured(self, **kwargs: object) -> object: ...


def _intake_node(state: PipelineContext) -> dict:
    """LangGraph node wrapper: receives state, returns partial state update."""
    client = get_client()
    out = intake_agent.run(state.raw_text, client=client)
    return {"intake": out}


def build_graph() -> object:
    """Compile the LangGraph state machine.

    Returns a compiled graph with .invoke(state) -> final state.
    """
    g: StateGraph = StateGraph(PipelineContext)
    g.add_node("intake", _intake_node)
    g.set_entry_point("intake")
    g.add_edge("intake", END)
    return g.compile()


def run_analysis(raw_text: str) -> PipelineContext:
    """End-to-end pipeline invocation. Phase 1: returns context after intake only."""
    graph = build_graph()
    initial = PipelineContext(raw_text=raw_text)
    # LangGraph returns either a state dict or a state object depending on version;
    # we coerce back to PipelineContext for type safety.
    final = graph.invoke(initial)
    if isinstance(final, PipelineContext):
        return final
    return PipelineContext.model_validate(final)
