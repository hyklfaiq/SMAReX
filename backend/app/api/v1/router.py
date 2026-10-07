"""Aggregates every v1 router under a single /api/v1 prefix."""

from fastapi import APIRouter

from app.api.v1 import admin, auth, interactions, resources

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(resources.router)
api_router.include_router(interactions.router)
api_router.include_router(admin.router)

__all__ = ["api_router"]