"""Deterministic stub `StructuredClient` for the live frontend demo path.

Activated when `DEMO_MODE=1` (or when a real LLM provider isn't configured).
The Intake / Extraction / Reasoning stages get keyword-driven canned outputs;
**Retrieval runs against real ChromaDB**, the **Critic deterministic guard runs**,
and the **frontend / tracing / report** layers are completely real. This is
exactly the wiring exercised by the production path — only the model calls
are replaced — so a green demo response is meaningful evidence the rest of
the pipeline is correct.

Real LLM call results would be richer; the deterministic stub is intentionally
narrow so the response is reproducible run-to-run for screenshots and CI.
"""

from __future__ import annotations

from typing import Any

from api.agents.intake import IntakeClassification
from api.schemas.pipeline import (
    CriticOutput,
    DocumentIssue,
    DocumentType,
    EvidenceItem,
    ExtractionOutput,
    ReasoningFinding,
    ReasoningOutput,
)


def _classify_doc_type(text: str) -> DocumentType:
    lower = text.lower()
    if "denied" in lower or "denial" in lower:
        return DocumentType.ADMINISTRATIVE_DENIAL
    if "appeal" in lower or "remand" in lower:
        return DocumentType.APPEAL_DECISION
    if "examination" in lower and "report" in lower:
        return DocumentType.MEDICAL_EXAMINATION
    if "memo" in lower or "policy" in lower:
        return DocumentType.POLICY_MEMO
    return DocumentType.UNKNOWN


def _seed_issue(text: str) -> DocumentIssue:
    """Pull a one-sentence issue from the text via simple regex-y heuristics."""
    lower = text.lower()
    if "service connection" in lower:
        topic = "Service connection"
    elif "tdiu" in lower or "unemployability" in lower:
        topic = "Total disability based on individual unemployability"
    elif "secondary" in lower:
        topic = "Secondary service connection"
    else:
        topic = "Claim adjudication"

    decision = "denied" if "denied" in lower or "denial" in lower else "other"
    snippet_end = min(220, len(text))
    return DocumentIssue(
        issue_text=f"{topic} adjudicated as {decision}",
        decision=decision,  # type: ignore[arg-type]
        stated_reason=(
            "The examiner's negative opinion was relied upon without addressing "
            "all relevant theories raised by the record."
        ),
        source_span=(0, snippet_end),
        confidence=0.78,
    )


def _seed_evidence() -> list[EvidenceItem]:
    return [
        EvidenceItem(
            label="Examiner's negative opinion",
            description="One-line opinion stating less likely than not without reasoned analysis.",
            source_type="document",
            favorability="adverse",
        ),
        EvidenceItem(
            label="Missing private nexus opinion",
            description="No private medical opinion currently of record addressing causation.",
            source_type="missing",
            favorability="missing",
        ),
    ]


_FINDING_TEMPLATE = (
    "The agency examination is inadequate because it did not confront the "
    "credibly raised theory; reliance on it without remand is procedural error."
)


def _seed_reasoning(retrieved_ids: list[str]) -> ReasoningOutput:
    """Construct a single grounded finding citing whatever Retrieval returned.

    Citing real retrieved ids guarantees the deterministic Critic guard
    approves the finding, so the demo produces a non-empty Findings tab.
    """
    cited = retrieved_ids[:2] or ["REG-3.159"]
    return ReasoningOutput(
        findings=[
            ReasoningFinding(
                issue_index=0,
                finding_text=_FINDING_TEMPLATE,
                supporting_source_ids=cited,
                confidence=0.74,
            )
        ],
        identified_weaknesses=[
            "Examiner did not address the secondary-causation theory raised by the lay record."
        ],
    )


class DemoClient:
    """Deterministic stand-in for `StructuredClient` used by the live demo path."""

    def __init__(self) -> None:
        # Per-request state: Retrieval populates these so Reasoning can cite real ids.
        self._raw_text: str = ""
        self._retrieved_ids: list[str] = []

    # ------------------------------------------------------------------
    # Hooks called by the orchestrator before specific stages run.
    # ------------------------------------------------------------------
    def set_raw_text(self, text: str) -> None:
        self._raw_text = text

    def set_retrieved_ids(self, ids: list[str]) -> None:
        self._retrieved_ids = ids

    # ------------------------------------------------------------------
    # StructuredClient surface — exactly what every agent calls.
    # ------------------------------------------------------------------
    def structured(self, *, response_model: type, **_: Any) -> Any:
        name = response_model.__name__
        if name == "IntakeClassification":
            return IntakeClassification(
                doc_type=_classify_doc_type(self._raw_text).value,
                language="en",
                intake_warnings=["Demo mode: deterministic stub responses."],
            )
        if name == "ExtractionOutput":
            return ExtractionOutput(
                issues=[_seed_issue(self._raw_text)],
                evidence=_seed_evidence(),
                parties={"claimant": "Demo Claimant", "issuing_body": "Demo Review Board"},
                extraction_confidence=0.78,
            )
        if name == "ReasoningOutput":
            return _seed_reasoning(self._retrieved_ids)
        if name == "CriticOutput":
            # Real deterministic critic guard runs upstream of this stub;
            # if execution reaches here, the LLM critic is a no-op approver.
            return CriticOutput(
                approved_finding_indices=[0],
                flags=[],
                overall_faithfulness_score=0.85,
            )
        raise AssertionError(f"DemoClient has no canned output for {name}")
