"""Application configuration loaded from environment variables.

Centralizing settings here keeps secrets out of the source tree and lets
both the Alembic migration environment and the runtime service share a
single validated configuration object (Pydantic v2 ``BaseSettings``).
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_cors_origins: str = "http://localhost:5173"

    # Security
    jwt_secret: str = Field(min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 60
    password_reset_ttl_minutes: int = 30

    # Database
    database_url: str

    # SMTP (UC-5)
    smtp_host: str
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str
    smtp_starttls: bool = True

    # External APIs
    orcid_api_base: str = "https://pub.orcid.org/v3.0"
    openalex_api_base: str = "https://api.openalex.org"
    openalex_mailto: str | None = None
    ieee_xplore_api_base: str = (
        "https://ieeexploreapi.ieee.org/api/v1/search/articles"
    )
    ieee_xplore_api_key: str | None = None

    # LLM (LangChain). ``openai_api_base`` is passed through to the
    # OpenAI-compatible client so the same code path can target official
    # OpenAI, DeepSeek, Azure-compatible gateways, or local llama.cpp
    # servers without code changes.
    llm_provider: str = "openai"
    openai_api_key: str | None = None
    openai_api_base: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1

    # NLP models
    scibert_model: str = "allenai/scibert_scivocab_uncased"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Frontend
    frontend_base_url: str = "http://localhost:5173"

    @field_validator("app_cors_origins")
    @classmethod
    def _strip_origins(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings singleton."""
    return Settings()  # type: ignore[call-arg]
