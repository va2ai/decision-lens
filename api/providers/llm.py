"""Provider-agnostic structured-output client.

Why this layer exists:
- LiteLLM gives us OpenAI/Anthropic/Vertex/Bedrock/local models behind one API.
- Instructor gives us Pydantic-validated structured outputs with automatic retries
  on validation failure.
- This module composes the two so every agent can call llm.structured(...) and
  receive a typed Pydantic model — never a raw dict, never a JSON string.
"""

from __future__ import annotations

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
        self._client = instructor.from_litellm(litellm_completion)

    def structured(
        self,
        *,
        response_model: type[T],
        system: str,
        user: str,
        max_tokens: int | None = None,
    ) -> T:
        """Call the model and return a validated instance of `response_model`."""
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
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return self._client.chat.completions.create(**kwargs)


@lru_cache(maxsize=1)
def get_client() -> StructuredClient:
    s = get_settings()
    return StructuredClient(
        model=s.llm_model,
        temperature=s.llm_temperature,
        max_retries=s.llm_max_retries,
        timeout_s=s.llm_timeout_s,
    )
