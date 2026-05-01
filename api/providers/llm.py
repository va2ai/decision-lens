"""Provider-agnostic structured-output client.

Why this layer exists:
- LiteLLM gives us OpenAI/Anthropic/Vertex/Bedrock/local models behind one API.
- Instructor gives us Pydantic-validated structured outputs with automatic retries
  on validation failure.
- This module composes the two so every agent can call llm.structured(...) and
  receive a typed Pydantic model — never a raw dict, never a JSON string.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TypeVar

import instructor
from litellm import completion as litellm_completion
from pydantic import BaseModel

from api.config import get_settings

T = TypeVar("T", bound=BaseModel)


class StructuredClient:
    """Thin wrapper around instructor + litellm.

    Each agent injects this rather than importing a concrete provider, which
    makes every agent trivially testable with a stub client.
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.0,
        max_retries: int = 2,
        timeout_s: float = 60.0,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self.timeout_s = timeout_s
        # Instructor's litellm adapter: returns a client with the same
        # chat.completions.create surface, but response_model gives us a
        # validated Pydantic instance back.
        #
        # Mode selection: Gemini's TOOLS mode emits multiple parallel function
        # calls for nested schemas, which Instructor rejects with "does not
        # support multiple tool calls". JSON mode side-steps that — the model
        # produces a single JSON document we re-validate. Other providers stay
        # on the default TOOLS mode where it works fine.
        is_gemini = "gemini" in model.lower() or "vertex_ai/gemini" in model.lower()
        self._client = instructor.from_litellm(
            litellm_completion,
            mode=instructor.Mode.JSON if is_gemini else instructor.Mode.TOOLS,
        )

    def structured(
        self,
        *,
        response_model: type[T],
        system: str,
        user: str,
        max_tokens: int | None = None,
    ) -> T:
        """Call the model and return a validated instance of `response_model`.

        Wraps the call in an exponential-backoff retry on 429 rate-limit errors,
        which the Gemini free tier returns at 5 req/min/project/model. The
        pipeline makes ~4 calls per analysis — without backoff a back-to-back
        run trips the limit. Production should use paid-tier quota.
        """
        # Default ceiling generous enough for the largest schema (ExtractionOutput
        # with multi-issue lists). Gemini-flash-latest's default is ~512 which
        # truncates JSON-mode responses mid-object and triggers max_tokens errors.
        kwargs: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_model": response_model,
            "temperature": self.temperature,
            "max_retries": self.max_retries,
            "timeout": self.timeout_s,
            "max_tokens": max_tokens if max_tokens is not None else 8192,
        }

        # Disable Gemini "thinking" tokens for structured-output calls. Gemini
        # 2.5-flash burns ~1900 reasoning tokens before emitting output, which
        # truncates JSON mid-string under max_tokens. We don't need a chain of
        # thought to fill a Pydantic schema — the schema is the constraint.
        # LiteLLM's normalized `reasoning_effort="minimal"` maps to Gemini's
        # `thinking_config.thinking_budget=0` for 2.5-flash.
        if "gemini" in self.model.lower():
            kwargs["reasoning_effort"] = "minimal"

        import time

        for attempt in range(4):
            try:
                return self._client.chat.completions.create(**kwargs)
            except Exception as exc:  # noqa: BLE001
                msg = str(exc).lower()
                is_rate_limit = "rate" in msg or "429" in msg or "resource_exhausted" in msg
                if not is_rate_limit or attempt == 3:
                    raise
                wait = 2 ** attempt * 8  # 8s, 16s, 32s — safely past the 1-min window
                time.sleep(wait)
        raise RuntimeError("unreachable")


@lru_cache(maxsize=1)
def get_client() -> "StructuredClient":
    """Return the active client.

    When `DEMO_MODE=1` the orchestrator runs the deterministic `DemoClient`
    so the live demo path exercises real Retrieval, real Critic guard, real
    tracing, and real frontend without burning an LLM key.
    """
    if os.environ.get("DEMO_MODE", "").strip() in {"1", "true", "yes"}:
        from api.providers.demo_client import DemoClient

        return DemoClient()  # type: ignore[return-value]
    s = get_settings()
    return StructuredClient(
        model=s.llm_model,
        temperature=s.llm_temperature,
        max_retries=s.llm_max_retries,
        timeout_s=s.llm_timeout_s,
    )
