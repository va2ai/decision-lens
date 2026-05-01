"""Retrieval agent — per-issue concurrent corpus lookup.

No LLM call. The query for each issue is built deterministically from the
issue_text + stated_reason. Results come from the ChromaDB-backed
RetrievalStore. The agent fans out queries with asyncio.gather.
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from api.schemas.pipeline import (
    DocumentIssue,
    ExtractionOutput,
    RetrievalOutput,
    RetrievedReference,
)


class _Store(Protocol):
    def query(self, *, query_text: str, top_k: int = ...) -> list[dict]: ...
    def to_reference(self, *, issue_index: int, hit: dict) -> RetrievedReference: ...


def _query_for_issue(issue: DocumentIssue) -> str:
    parts = [issue.issue_text]
    if issue.stated_reason:
        parts.append(issue.stated_reason)
    return " ".join(parts)


async def _query_one(store: _Store, idx: int, issue: DocumentIssue, top_k: int) -> list[RetrievedReference]:
    q = _query_for_issue(issue)
    # ChromaDB query is sync; offload so the gather is meaningfully concurrent
    hits = await asyncio.to_thread(store.query, query_text=q, top_k=top_k)
    return [store.to_reference(issue_index=idx, hit=h) for h in hits]


async def run_async(extraction: ExtractionOutput, *, store: _Store, top_k: int = 3) -> RetrievalOutput:
    if not extraction.issues:
        return RetrievalOutput(references=[], retrieval_warnings=["No issues to retrieve for."])

    tasks = [
        _query_one(store, idx, issue, top_k)
        for idx, issue in enumerate(extraction.issues)
    ]
    grouped = await asyncio.gather(*tasks)
    references = [ref for group in grouped for ref in group]
    warnings: list[str] = []
    for idx, group in enumerate(grouped):
        if not group:
            warnings.append(f"Issue {idx}: no references retrieved.")
    return RetrievalOutput(references=references, retrieval_warnings=warnings)


def run(extraction: ExtractionOutput, *, store: _Store, top_k: int = 3) -> RetrievalOutput:
    """Sync entry point. Spins a private event loop so callers can be sync."""
    return asyncio.run(run_async(extraction, store=store, top_k=top_k))
