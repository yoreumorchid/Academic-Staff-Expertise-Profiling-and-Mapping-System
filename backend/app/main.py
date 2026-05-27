"""FastAPI application factory.

Run with::

    uvicorn app.main:app --reload
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ExpertiseInsight API",
        version="0.1.0",
        description=(
            "Backend service implementing the use cases UC-1 through UC-18 "
            "specified in use_cases.md."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health", tags=["meta"], summary="Liveness probe.")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
