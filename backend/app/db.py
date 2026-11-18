"""Async database engine, session factory and schema bootstrap."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()

engine = create_async_engine(
    settings.sqlalchemy_url,
    echo=False,
    pool_pre_ping=True,
    # Render/Postgres can close idle connections; a small pool keeps things predictable.
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create the pgvector extension, tables and retrieval index (idempotent)."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    await ensure_vector_index()


async def ensure_vector_index() -> None:
    """Create an ANN index; fall back gracefully on older pgvector builds."""
    statements = (
        "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw "
        "ON chunks USING hnsw (embedding vector_cosine_ops)",
        "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_ivfflat "
        "ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)",
    )
    async with engine.begin() as conn:
        for statement in statements:
            try:
                await conn.execute(text(statement))
                logger.info("vector_index_ready", extra={"statement": statement.split("ON")[0]})
                return
            except Exception as exc:  # pgvector version / extension variation
                logger.warning("vector_index_skipped", extra={"error": str(exc)[:200]})
