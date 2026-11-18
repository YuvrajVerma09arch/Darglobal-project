"""Environment-driven configuration. No secrets live in source code."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.paths import project_root

_PROJECT_ROOT = project_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(_PROJECT_ROOT / ".env"), ".env"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # Database
    postgres_user: str = "darglobal"
    postgres_password: str = "change-me"
    postgres_db: str = "realestate_ai"
    postgres_host: str = "db"
    postgres_port: int = 5432
    database_url: str | None = None

    # Auth / abuse controls
    admin_api_key: str = "replace-with-a-long-random-value"
    rate_limit_per_minute: int = 30
    chat_rate_limit_per_minute: int = 12

    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Embeddings
    embedding_provider: Literal["local", "openai"] = "local"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    openai_embedding_model: str = "text-embedding-3-small"

    # LLM (OpenAI-compatible interface; OpenRouter is the default base URL)
    llm_provider: str = "openrouter"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-4o-mini"
    llm_api_key: str = ""
    llm_temperature: float = 0.2
    llm_max_tokens: int = 900
    llm_timeout_seconds: int = 60
    llm_http_referer: str = "https://localhost"
    llm_app_name: str = "darglobal-wasalt-ai"
    llm_max_concurrency: int = 4

    # Fallback provider (Groq by default). Any OpenAI-compatible endpoint works.
    llm_fallback_provider: str = "groq"
    llm_fallback_api_key: str = ""
    llm_fallback_base_url: str = "https://api.groq.com/openai/v1"
    llm_fallback_model: str = "openai/gpt-oss-120b"
    # Convenience alias: GROQ_API_KEY is read automatically if the generic
    # LLM_FALLBACK_API_KEY is not set.
    groq_api_key: str = ""

    # Retrieval
    retrieval_top_k: int = 8
    retrieval_candidate_k: int = 24
    min_semantic_similarity: float = 0.65
    rrf_k: int = 60
    context_max_chars: int = 9000
    max_conversation_turns: int = 8

    # Scraper
    scraper_delay_seconds: float = 1.0
    scraper_timeout_seconds: int = 20
    scraper_max_retries: int = 2
    scraper_user_agent: str = (
        "Mozilla/5.0 (compatible; RealEstateResearchBot/1.0; +https://example.com/bot)"
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def normalise_origins(cls, value: str | list[str]) -> str:
        if isinstance(value, list):
            return ",".join(value)
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def fallback_api_key(self) -> str:
        return (self.llm_fallback_api_key or self.groq_api_key or "").strip()

    @property
    def is_llm_configured(self) -> bool:
        key = (self.llm_api_key or "").strip()
        primary = bool(key) and key != "replace-with-your-openrouter-key"
        return primary or bool(self.fallback_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
