"""
Master API v1 Router.

Consolidates domain feature routers into a unified API router structure.
"""

from fastapi import APIRouter

from app.domains.audit.router import router as audit_router
from app.domains.auth.router import router as auth_router
from app.domains.campaigns.router import router as campaigns_router
from app.domains.donations.router import router as donations_router
from app.domains.ledger.router import router as ledger_router
# from app.domains.webhooks.router import router as webhooks_router

api_router = APIRouter()

# Mount all domain feature routers under the v1 API prefix
api_router.include_router(auth_router)
api_router.include_router(campaigns_router)
api_router.include_router(donations_router)
api_router.include_router(audit_router)
api_router.include_router(ledger_router)
# api_router.include_router(webhooks_router)