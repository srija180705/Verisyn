"""Aggregates all v1 API routes.

Business routers (events, fraud assessments, cases, etc.) will be added
here in later phases. Only the health endpoint exists today.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import health

api_router = APIRouter()
api_router.include_router(health.router)
