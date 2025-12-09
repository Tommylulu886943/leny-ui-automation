"""
Leny UI Automation - FastAPI Application

AI-powered UI automation testing platform.
"""

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import settings
from app.api import api_router


def configure_logging():
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
            if settings.log_format == "json"
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup: Initialize resources
    Shutdown: Clean up resources
    """
    logger = structlog.get_logger()

    # Startup
    logger.info(
        "application_starting",
        version=__version__,
        environment=settings.app_env,
    )

    # Initialize Playwright browsers (download if needed)
    # This is optional - browsers are downloaded on first use
    # from playwright.async_api import async_playwright
    # async with async_playwright() as p:
    #     await p.chromium.launch()

    yield

    # Shutdown
    logger.info("application_shutting_down")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    configure_logging()

    app = FastAPI(
        title="Leny UI Automation",
        description="""
## AI-Powered UI Automation Testing Platform

Leny provides intelligent UI test automation with:
- **Natural Language Tests**: Write tests in plain English
- **Multi-Strategy Locators**: Resilient element finding
- **AI-Powered Generation**: Convert descriptions to test scripts
- **Cross-Browser Support**: Chromium, Firefox, WebKit

### Quick Start

1. **Create a test from natural language**:
   ```
   POST /api/v1/generate/from-natural-language
   {
     "description": "Go to example.com, click login, enter credentials"
   }
   ```

2. **Save and execute the test**:
   ```
   POST /api/v1/execution/run
   {
     "test_case": { ... }
   }
   ```

3. **View results**:
   ```
   GET /api/v1/execution/history
   ```
        """,
        version=__version__,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",  # Next.js dev server
            "http://localhost:8000",  # API server
            "https://*.vercel.app",  # Vercel deployments
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(api_router, prefix="/api/v1")

    # Root endpoint
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "name": "Leny UI Automation",
            "version": __version__,
            "docs": "/docs" if settings.is_development else "Disabled in production",
            "api": "/api/v1",
        }

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger = structlog.get_logger()
        logger.exception("unhandled_exception", error=str(exc))

        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if settings.is_development else "An error occurred",
            },
        )

    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
