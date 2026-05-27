"""Typed exception hierarchy and FastAPI handlers.

Every external failure mode mandated by the use cases (e.g. UC-8 / UC-12
API timeouts) and every domain validation error funnels through these
classes so the frontend receives a consistent JSON envelope rather than
raw stack traces.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class DomainError(Exception):
    """Base class for predictable, business-rule failures."""

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str, *, details: Dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class UnauthorizedError(DomainError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(DomainError):
    status_code = 403
    code = "forbidden"


class ValidationFailure(DomainError):
    status_code = 422
    code = "validation_failed"


class ExternalServiceError(DomainError):
    """Used for ORCID / OpenAlex / IEEE Xplore connectivity failures.

    Maps to HTTP 503 per instructions.md §4 rule 4.
    """

    status_code = 503
    code = "external_service_unavailable"


def _envelope(code: str, message: str, details: Dict[str, Any] | None) -> Dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    """Wire the handlers onto a FastAPI application instance."""

    @app.exception_handler(DomainError)
    async def _domain_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope(
                "validation_failed",
                "Request payload failed validation.",
                {"errors": exc.errors()},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("http_error", str(exc.detail), None),
        )
