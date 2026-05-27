"""Aggregate router exposing the v1 API surface."""
from __future__ import annotations

from fastapi import APIRouter

from app.api import routes_admin, routes_auth

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(routes_auth.router)
api_router.include_router(routes_admin.router)
