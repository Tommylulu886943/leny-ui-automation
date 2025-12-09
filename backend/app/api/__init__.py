"""
API routes package.
"""

from fastapi import APIRouter

from app.api.routes import tests, execution, health, generate

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(tests.router, prefix="/tests", tags=["Tests"])
api_router.include_router(execution.router, prefix="/execution", tags=["Execution"])
api_router.include_router(generate.router, prefix="/generate", tags=["Generation"])
