"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings
from app.logging_config import configure_logging
from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.routers import admin, chat, health, meta, properties, search

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application_starting", extra={"env": settings.app_env})
    try:
        from app.db import init_db

        await init_db()
        logger.info("database_ready")
    except Exception as exc:
        logger.error("database_init_failed", extra={"error": str(exc)[:200]})
    yield
    logger.info("application_stopping")


app = FastAPI(
    title="DarGlobal & Wasalt Real Estate Intelligence API",
    description=(
        "Grounded, source-attributed RAG over publicly available DarGlobal and Wasalt "
        "real-estate information. Hybrid SQL + pgvector retrieval."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(health.router)
app.include_router(meta.router, prefix=settings.api_v1_prefix)
app.include_router(meta.stats_router, prefix=settings.api_v1_prefix)
app.include_router(chat.router, prefix=settings.api_v1_prefix)
app.include_router(properties.router, prefix=settings.api_v1_prefix)
app.include_router(search.router, prefix=settings.api_v1_prefix)
app.include_router(admin.router, prefix=settings.api_v1_prefix)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    logger.exception("unhandled_error", extra={"path": request.url.path})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/", tags=["health"])
async def root():
    return {
        "name": "DarGlobal & Wasalt Real Estate Intelligence Assistant",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }
