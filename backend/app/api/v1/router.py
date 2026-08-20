"""Aggregates all v1 API routes.

Further business routers (events, cases, etc.) will be added here in
later phases.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import feedback, fraud, health, transactions

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(fraud.router)
api_router.include_router(transactions.router)
api_router.include_router(feedback.router)
