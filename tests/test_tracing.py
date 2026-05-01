"""Tracing tests — every node records a span; trace store is bounded."""

from __future__ import annotations

from typing import Any

import pytest

from api.agents import graph as graph_mod
from api.agents.intake import IntakeClassification
from api.observability import TraceStore, get_trace_store, span
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


class _StubClient:
    def __init__(self, **by_model: Any) -> None:
        self._by_model = by_model

    def structured(self, *, response_model: type, **_: Any) -> Any:
        return self._by_model[response_model.__name__]


class _StubStore:
    def __init__(self, refs: list[RetrievedReference]) -> None:
        self._refs = refs

    def ensure_loaded(self) -> None:
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
        m = hit["meta"]
        return RetrievedReference(
            issue_index=issue_index,
            source_id=hit["source_id"],
            source_title=m["title"],
            authority_type=AuthorityType(m["authority_type"]),
            passage=m["passage"],
            url=m["url"] or None,
            relevance_score=round(1.0 / (1.0 + max(0.0, hit["distance"])), 4),
        )


def _stubs() -> tuple[_StubClient, _StubStore]:
    client = _StubClient(
        IntakeClassification=IntakeClassification(
            doc_type="administrative_denial", language="en", intake_warnings=[]
        ),
        ExtractionOutput=ExtractionOutput(
            issues=[
                DocumentIssue(
                    issue_text="x",
                    decision="denied",
                    stated_reason=None,
                    source_span=(0, 50),
                    confidence=0.8,
                )
            ],
            evidence=[
                EvidenceItem(
                    label="ev",
                    description="d",
                    source_type="document",
                    favorability="favorable",
                )
            ],
            extraction_confidence=0.8,
        ),
        ReasoningOutput=ReasoningOutput(
            findings=[
                ReasoningFinding(
                    issue_index=0,
                    finding_text="ok",
                    supporting_source_ids=["REG-X"],
                    confidence=0.8,
                )
            ]
        ),
        CriticOutput=CriticOutput(
            approved_finding_indices=[0], flags=[], overall_faithfulness_score=0.9
        ),
    )
    store = _StubStore(
        [
            RetrievedReference(
                issue_index=0,
                source_id="REG-X",
                source_title="t",
                authority_type=AuthorityType.BINDING_REGULATION,
                passage="p",
                relevance_score=0.9,
            )
        ]
    )
    return client, store


def test_run_records_one_span_per_node(monkeypatch: pytest.MonkeyPatch) -> None:
    client, store = _stubs()
    monkeypatch.setattr(graph_mod, "get_client", lambda: client)
    monkeypatch.setattr(graph_mod, "get_store", lambda: store)

    text = "x" * 200
    report, trace = graph_mod.run_analysis_traced(text)

    span_names = [s.name for s in trace.spans]
    assert span_names == ["intake", "extraction", "retrieval", "reasoning", "critic", "report"]

    # Every span closed cleanly.
    for s in trace.spans:
        assert s.status == "ok", f"{s.name} status={s.status} error={s.error}"
        assert s.ended_at is not None
        assert s.duration_ms is not None and s.duration_ms >= 0

    # Trace closed.
    assert trace.ended_at is not None
    assert trace.duration_ms is not None and trace.duration_ms >= 0

    # The report is the same one from run_analysis().
    assert len(report.findings) == 1


def test_trace_store_is_bounded() -> None:
    store = TraceStore(max_traces=3)
    ids = [store.start().run_id for _ in range(5)]
    # Earliest two should be evicted; only the last 3 remain.
    assert store.get(ids[0]) is None
    assert store.get(ids[1]) is None
    for rid in ids[2:]:
        assert store.get(rid) is not None


def test_span_records_error_status() -> None:
    store = TraceStore()
    trace = store.start()
    with pytest.raises(RuntimeError):
        with span(trace, "boom"):
            raise RuntimeError("kaboom")
    assert trace.spans[0].status == "error"
    assert trace.spans[0].error and "kaboom" in trace.spans[0].error


def test_global_store_is_singleton() -> None:
    a = get_trace_store()
    b = get_trace_store()
    assert a is b
