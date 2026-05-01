"""Intake agent tests — deterministic normalization + LLM classification (mocked)."""

from __future__ import annotations

from typing import Any

import pytest

from api.agents.intake import IntakeClassification, normalize_text, run
from api.schemas.pipeline import DocumentType, IntakeOutput


class StubClient:
    """Stub structured-output client. Records calls; returns a canned response."""

    def __init__(self, classification: IntakeClassification) -> None:
        self._classification = classification
        self.calls: list[dict] = []

    def structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self._classification


# ---------------------------------------------------------------------------
# Pure normalization (no LLM)
# ---------------------------------------------------------------------------


def test_normalize_collapses_whitespace_runs() -> None:
    assert normalize_text("a   b\t\tc") == "a b c"


def test_normalize_strips_control_chars() -> None:
    assert normalize_text("hello\x00world\x07!") == "helloworld!"


def test_normalize_collapses_excessive_blank_lines() -> None:
    assert normalize_text("a\n\n\n\nb") == "a\n\nb"


def test_normalize_idempotent() -> None:
    s = "  Demo   text\n\n\n with    spaces.  "
    assert normalize_text(normalize_text(s)) == normalize_text(s)


# ---------------------------------------------------------------------------
# Agent run
# ---------------------------------------------------------------------------


def _long_text(prefix: str = "DEMO BOARD ADMINISTRATIVE DECISION") -> str:
    return prefix + " " + ("lorem ipsum " * 20)


def test_run_returns_full_intake_output() -> None:
    client = StubClient(
        IntakeClassification(
            doc_type="administrative_denial",
            language="en",
            intake_warnings=[],
        )
    )
    out = run(_long_text(), client=client)

    assert isinstance(out, IntakeOutput)
    assert out.doc_type is DocumentType.ADMINISTRATIVE_DENIAL
    assert out.language == "en"
    assert out.char_count == len(out.normalized_text)
    assert out.char_count > 50


def test_run_rejects_short_input() -> None:
    client = StubClient(IntakeClassification(doc_type="unknown"))
    with pytest.raises(ValueError, match="too short"):
        run("Too short.", client=client)


def test_run_passes_snippet_not_full_text_when_long() -> None:
    long_doc = "X" * 8000
    client = StubClient(IntakeClassification(doc_type="unknown"))
    out = run(long_doc, client=client)

    # Full normalized text persisted on output, but snippet was truncated.
    assert out.char_count == 8000
    assert any("first 4000" in w for w in out.intake_warnings)
    sent_user = client.calls[0]["user"]
    assert len(sent_user) < 8000


def test_run_merges_warnings_from_llm_and_normalization() -> None:
    client = StubClient(
        IntakeClassification(
            doc_type="legal_letter",
            intake_warnings=["Document mixes English and Spanish."],
        )
    )
    out = run(_long_text(), client=client)
    assert "Document mixes English and Spanish." in out.intake_warnings


def test_run_returns_unknown_when_classifier_says_unknown() -> None:
    client = StubClient(IntakeClassification(doc_type="unknown"))
    out = run(_long_text("MISC TEXT"), client=client)
    assert out.doc_type is DocumentType.UNKNOWN
