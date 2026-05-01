"""Intake agent — validate, normalize, classify.

Splits responsibility cleanly:
  - Deterministic code: text normalization, char counting (cheap, reliable, no LLM)
  - LLM: doc_type classification, language detection, surfacing intake warnings

The LLM only returns a small classification dict (`IntakeClassification`),
which the agent then merges with the deterministic fields to produce the full
`IntakeOutput`. This keeps the LLM's job small and testable.
"""

from __future__ import annotations

import re
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from api.prompts.intake import PROMPT_VERSION, SYSTEM, USER_TEMPLATE
from api.schemas.pipeline import DocumentType, IntakeOutput

__all__ = ["PROMPT_VERSION", "IntakeClassification", "run"]


class IntakeClassification(BaseModel):
    """The narrow slice we ask the LLM to produce."""

    doc_type: Literal[
        "administrative_denial",
        "legal_letter",
        "appeal_decision",
        "unknown",
    ]
    language: str = Field(default="en", description="ISO 639-1 language code")
    intake_warnings: list[str] = Field(default_factory=list)


class _Client(Protocol):
    def structured(
        self,
        *,
        response_model: type,
        system: str,
        user: str,
        max_tokens: int | None = ...,
    ) -> object: ...


_WS_RE = re.compile(r"[ \t]+")
_NEWLINES_RE = re.compile(r"\n{3,}")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MIN_CHARS = 50


def normalize_text(raw: str) -> str:
    """Strip control chars, collapse whitespace runs, normalize newlines.

    Deterministic. No LLM. Identical input always yields identical output.
    """
    text = _CTRL_RE.sub("", raw)
    text = _WS_RE.sub(" ", text)
    text = _NEWLINES_RE.sub("\n\n", text)
    return text.strip()


def run(raw_text: str, *, client: _Client) -> IntakeOutput:
    """Classify and normalize a document.

    Raises ValueError for inputs too small to analyze — Intake is a hard-abort
    stage. Everything downstream assumes normalized_text has real content.
    """
    normalized = normalize_text(raw_text)
    char_count = len(normalized)

    warnings: list[str] = []
    if char_count < _MIN_CHARS:
        raise ValueError(
            f"Document too short for analysis ({char_count} chars; min={_MIN_CHARS})"
        )

    snippet = normalized[:4000]
    if len(normalized) > 4000:
        warnings.append(f"Classification used first 4000 of {len(normalized)} chars.")

    classification = client.structured(
        response_model=IntakeClassification,
        system=SYSTEM,
        user=USER_TEMPLATE.format(snippet=snippet),
        max_tokens=400,
    )
    assert isinstance(classification, IntakeClassification)

    return IntakeOutput(
        normalized_text=normalized,
        doc_type=DocumentType(classification.doc_type),
        char_count=char_count,
        language=classification.language,
        intake_warnings=[*warnings, *classification.intake_warnings],
    )
