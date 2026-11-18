"""Source inventory and corpus statistics."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Chunk, IngestionRun, Property
from app.schemas import SourcesResponse, SourceStat, StatsResponse

router = APIRouter(prefix="/sources", tags=["metadata"])
stats_router = APIRouter(tags=["metadata"])
access_router = APIRouter(tags=["metadata"])


@access_router.get("/access")
async def access_requirement():
    """Public: tells the UI whether a shared access code is required."""
    from app.config import get_settings

    return {"access_required": bool(get_settings().app_access_code.strip())}


@router.get("", response_model=SourcesResponse)
async def sources(session: AsyncSession = Depends(get_db)):
    rows = (
        await session.execute(
            select(
                Property.source,
                func.count(Property.id),
                func.max(Property.scraped_at),
            ).group_by(Property.source)
        )
    ).all()
    chunk_counts = dict(
        (
            await session.execute(select(Chunk.source, func.count(Chunk.id)).group_by(Chunk.source))
        ).all()
    )
    return SourcesResponse(
        sources=[
            SourceStat(
                source=source,
                records=records,
                chunks=int(chunk_counts.get(source, 0)),
                last_scraped_at=last,
            )
            for source, records, last in rows
        ],
        generated_at=datetime.now(timezone.utc),
    )


@stats_router.get("/stats", response_model=StatsResponse, include_in_schema=True)
async def stats(session: AsyncSession = Depends(get_db)):
    records = await session.scalar(select(func.count()).select_from(Property))
    chunks = await session.scalar(select(func.count()).select_from(Chunk))
    by_source = dict(
        (
            await session.execute(
                select(Property.source, func.count(Property.id)).group_by(Property.source)
            )
        ).all()
    )
    by_type = dict(
        (
            await session.execute(
                select(Property.property_type, func.count(Property.id))
                .where(Property.property_type.is_not(None))
                .group_by(Property.property_type)
            )
        ).all()
    )
    by_city = dict(
        (
            await session.execute(
                select(Property.city, func.count(Property.id))
                .where(Property.city.is_not(None))
                .group_by(Property.city)
            )
        ).all()
    )
    last_scraped = await session.scalar(select(func.max(Property.scraped_at)))
    last_run = (
        await session.execute(
            select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    return StatsResponse(
        records=int(records or 0),
        chunks=int(chunks or 0),
        sources={str(k): int(v) for k, v in by_source.items()},
        property_types={str(k): int(v) for k, v in by_type.items()},
        cities={str(k): int(v) for k, v in by_city.items()},
        last_scraped_at=last_scraped,
        last_ingestion=(
            {
                "status": last_run.status,
                "source": last_run.source,
                "started_at": last_run.started_at,
                "finished_at": last_run.finished_at,
                "pages_scraped": last_run.pages_scraped,
                "records_upserted": last_run.records_upserted,
                "chunks_indexed": last_run.chunks_indexed,
            }
            if last_run
            else None
        ),
    )
