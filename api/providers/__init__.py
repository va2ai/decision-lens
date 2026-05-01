"""LLM provider abstraction — LiteLLM under the hood, Instructor on top.

Every agent talks to the model through llm.structured() so swapping models
(OpenAI → Anthropic → Vertex/Gemini) is a single env var change.
"""

from api.providers.llm import StructuredClient, get_client

__all__ = ["StructuredClient", "get_client"]
