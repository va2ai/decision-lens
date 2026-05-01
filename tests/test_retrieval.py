"""Retrieval agent + ChromaDB store tests."""

from __future__ import annotations

from api.agents.retrieval import run as retrieval_run
from api.retrieval.store import RetrievalStore
from api.schemas.pipeline import DocumentIssue, ExtractionOutput


def test_store_loads_corpus() -> None:
    store = RetrievalStore()
    store.ensure_loaded()
    hits = store.query(query_text="benefit of the doubt evidence equipoise", top_k=2)
    assert len(hits) >= 1
    ids = [h["source_id"] for h in hits]
    # The benefit-of-the-doubt regulation should be in or near the top hits.
    assert any("REG-5107" in i or i.startswith("REG-") for i in ids)


def test_retrieval_agent_returns_per_issue_references() -> None:
    store = RetrievalStore()
    extraction = ExtractionOutput(
        issues=[
            DocumentIssue(
                issue_text="Service connection denied for chronic respiratory condition",
                decision="denied",
                stated_reason="Examiner opined less likely than not.",
                source_span=(0, 50),
                confidence=0.9,
            ),
            DocumentIssue(
                issue_text="Adequacy of agency examination challenged",
                decision="denied",
                stated_reason="Examiner did not address secondary causation.",
                source_span=(60, 100),
                confidence=0.85,
            ),
        ],
        extraction_confidence=0.9,
    )
    out = retrieval_run(extraction, store=store, top_k=2)
    # Two issues × top_k=2 = up to 4 references
    assert len(out.references) > 0
    assert len(out.references) <= 4
    issue_indices = {ref.issue_index for ref in out.references}
    assert issue_indices.issubset({0, 1})
    # Relevance scores in [0, 1]
    for ref in out.references:
        assert 0.0 <= ref.relevance_score <= 1.0
        assert ref.source_id


def test_retrieval_handles_empty_extraction() -> None:
    store = RetrievalStore()
    out = retrieval_run(ExtractionOutput(issues=[], extraction_confidence=0.0), store=store)
    assert out.references == []
    assert any("No issues" in w for w in out.retrieval_warnings)
