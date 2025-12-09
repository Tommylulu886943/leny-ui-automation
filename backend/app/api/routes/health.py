"""
Health check endpoints.
"""

from datetime import datetime

from fastapi import APIRouter

from app import __version__
from app.config import settings

router = APIRouter()


@router.get("")
async def health_check():
    """
    Basic health check endpoint.
    """
    return {
        "status": "healthy",
        "version": __version__,
        "environment": settings.app_env,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/ready")
async def readiness_check():
    """
    Readiness check - verifies all dependencies are available.
    """
    checks = {
        "api": True,
        "openai_configured": bool(settings.openai_api_key),
    }

    all_ready = all(checks.values())

    return {
        "ready": all_ready,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }
