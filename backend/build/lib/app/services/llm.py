"""LangChain LLM factory.

Centralizes construction of the ``ChatOpenAI`` client so every consumer
(semantic normalization in UC-8, narrative synthesis in UC-15/17, etc.)
shares the same OpenAI-compatible endpoint configuration.

When ``OPENAI_API_BASE`` is set in the environment, it is forwarded to
``ChatOpenAI`` as the ``base_url`` parameter. This routes requests to
any OpenAI-compatible gateway (DeepSeek, Azure-style proxies, local
llama.cpp servers, etc.) instead of the official OpenAI endpoint.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError


@lru_cache(maxsize=1)
def get_chat_llm() -> ChatOpenAI:
    """Return a cached ``ChatOpenAI`` instance configured from settings."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise ExternalServiceError(
            "LLM is not configured.",
            details={"setting": "OPENAI_API_KEY"},
        )

    kwargs: dict = {
        "model": settings.llm_model,
        "api_key": settings.openai_api_key,
        "temperature": settings.llm_temperature,
    }
    # Only forward base_url when explicitly configured so that the
    # default code path keeps targeting the official OpenAI endpoint.
    if settings.openai_api_base:
        kwargs["base_url"] = settings.openai_api_base
    return ChatOpenAI(**kwargs)
