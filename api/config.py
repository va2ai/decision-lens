"""Runtime settings — env-var driven, single source of truth."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All config flows through here. No bare os.getenv calls in agent code."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM — provider-agnostic via LiteLLM.
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    llm_max_retries: int = 2
    llm_timeout_s: float = 60.0

    # Embeddings (used in Phase 2)
    embedding_model: str = "text-embedding-3-small"

    # Observability
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

    # Runtime
    log_level: str = "INFO"
    trace_dir: str = "./traces"
    chroma_dir: str = "./.chroma"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
