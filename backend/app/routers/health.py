"""Health and lightweight readiness endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.db import get_db
from app.models import Chunk, IngestionRun

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.api_route("/health", methods=["GET", "HEAD"])
async def health(session: AsyncSession = Depends(get_db)):
    try:
        await session.execute(text("SELECT 1"))
        chunks = await session.scalar(select(func.count()).select_from(Chunk))
        last = await session.scalar(select(func.max(IngestionRun.finished_at)))
        return {
            "status": "ok",
            "version": __version__,
            "database": "connected",
            "indexed_chunks": int(chunks or 0),
            "last_ingest_at": last.isoformat() if last else None,
        }
    except Exception as exc:  # pragma: no cover
        from app.logging_config import redact

        logger.error("health_check_failed: %s", redact(exc)[:300])
        # A degraded service must fail its platform health check instead of
        # reporting 200 forever (Render polls /health to decide restarts).
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "version": __version__,
                "database": "unavailable",
                "indexed_chunks": 0,
                "last_ingest_at": None,
            },
        )
