"""Critic agent tests — including the hallucination-injection assertion."""

from __future__ import annotations

from typing import Any

from api.agents.critic import run
from api.schemas.pipeline import (
    AuthorityType,
    CriticFinding,
    CriticOutput,
    ReasoningFinding,
    ReasoningOutput,
    RetrievalOutput,
    RetrievedReference,
)


class StubClient:
    def __init__(self, payload: CriticOutput) -> None:
        self.payload = payload

    def structured(self, **_: Any) -> Any:
        return self.payload


def _retrieval(*ids: str) -> RetrievalOutput:
    return RetrievalOutput(
        references=[
            RetrievedReference(
                issue_index=0,
                source_id=sid,
                source_title=sid,
                authority_type=AuthorityType.BINDING_REGULATION,
                passage="passage",
                relevance_score=0.9,
            )
            for sid in ids
        ]
    )


def test_hallucination_injection_is_flagged_without_llm() -> None:
    """A finding citing a source_id NOT in retrieval must be auto-blocked.

    This is the load-bearing test: the deterministic guard must catch
    hallucinations before they reach the LLM critic, with no LLM call required.
    """
    reasoning = ReasoningOutput(
        findings=[
            ReasoningFinding(
                issue_index=0,
                finding_text="Made-up authority.",
                supporting_source_ids=["REG-PHANTOM"],
                confidence=0.9,
            )
        ]
    )
    out = run(reasoning, _retrieval("REG-3.303"), client=None)
    assert out.approved_finding_indices == []
    assert any(fl.flag_type == "hallucination" and fl.severity == "block" for fl in out.flags)
    assert out.overall_faithfulness_score == 0.0


def test_clean_finding_is_approved_without_llm() -> None:
    reasoning = ReasoningOutput(
        findings=[
            ReasoningFinding(
                issue_index=0,
                finding_text="Real cite.",
                supporting_source_ids=["REG-3.303"],
                confidence=0.8,
            )
        ]
    )
    out = run(reasoning, _retrieval("REG-3.303"), client=None)
    assert out.approved_finding_indices == [0]
    # No client provided -> no LLM flags, no LLM score; deterministic share=0 -> 1.0.
    assert out.overall_faithfulness_score == 1.0


def test_llm_block_flag_drops_finding_from_approved() -> None:
    reasoning = ReasoningOutput(
        findings=[
            ReasoningFinding(
                issue_index=0,
                finding_text="Cited but overreaching.",
                supporting_source_ids=["REG-3.303"],
                confidence=0.7,
            )
        ]
    )
    llm_payload = CriticOutput(
        approved_finding_indices=[],
        flags=[
            CriticFinding(
                target_index=0,
                flag_type="overreach",
                explanation="Claim exceeds the cited authority's scope.",
                severity="block",
            )
        ],
        overall_faithfulness_score=0.4,
    )
    out = run(reasoning, _retrieval("REG-3.303"), client=StubClient(llm_payload))
    assert out.approved_finding_indices == []
    assert any(fl.flag_type == "overreach" for fl in out.flags)


def test_llm_warn_flag_does_not_block_finding() -> None:
    reasoning = ReasoningOutput(
        findings=[
            ReasoningFinding(
                issue_index=0,
                finding_text="Cited, with a note.",
                supporting_source_ids=["REG-3.303"],
                confidence=0.7,
            )
        ]
    )
    llm_payload = CriticOutput(
        approved_finding_indices=[0],
        flags=[
            CriticFinding(
                target_index=0,
                flag_type="weak_citation",
                explanation="Citation is loosely related.",
                severity="warn",
            )
        ],
        overall_faithfulness_score=0.7,
    )
    out = run(reasoning, _retrieval("REG-3.303"), client=StubClient(llm_payload))
    assert out.approved_finding_indices == [0]


def test_poisoned_blocks_every_finding() -> None:
    reasoning = ReasoningOutput(
        findings=[
            ReasoningFinding(
                issue_index=0,
                finding_text="x",
                supporting_source_ids=["REG-3.303"],
                confidence=0.9,
            ),
            ReasoningFinding(
                issue_index=0,
                finding_text="y",
                supporting_source_ids=["REG-3.303"],
                confidence=0.9,
            ),
        ]
    )
    out = run(reasoning, _retrieval("REG-3.303"), client=None, poisoned=True)
    assert out.approved_finding_indices == []
    assert len(out.flags) == 2
    assert all(fl.severity == "block" for fl in out.flags)


def test_drops_llm_flag_with_out_of_range_index() -> None:
    reasoning = ReasoningOutput(
        findings=[
            ReasoningFinding(
                issue_index=0,
                finding_text="ok",
                supporting_source_ids=["REG-3.303"],
                confidence=0.8,
            )
        ]
    )
    llm_payload = CriticOutput(
        approved_finding_indices=[0],
        flags=[
            CriticFinding(
                target_index=99,  # out of range — should be dropped
                flag_type="hallucination",
                explanation="phantom",
                severity="block",
            )
        ],
        overall_faithfulness_score=0.9,
    )
    out = run(reasoning, _retrieval("REG-3.303"), client=StubClient(llm_payload))
    assert out.approved_finding_indices == [0]
    # Only deterministic flags should remain; LLM phantom flag dropped.
    assert all(fl.target_index == 0 for fl in out.flags) or out.flags == []
