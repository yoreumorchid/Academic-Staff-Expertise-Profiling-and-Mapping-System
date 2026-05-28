"""Aggregate router exposing the v1 API surface."""
from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    routes_admin,
    routes_auth,
    routes_benchmarking,
    routes_export,
    routes_mapping,
    routes_profile,
    routes_sync,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(routes_auth.router)
api_router.include_router(routes_admin.router)
api_router.include_router(routes_profile.router)
api_router.include_router(routes_sync.router)
api_router.include_router(routes_mapping.router)
api_router.include_router(routes_benchmarking.router)
api_router.include_router(routes_export.router)
