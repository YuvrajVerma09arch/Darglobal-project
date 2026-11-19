"""Async database engine, session factory and schema bootstrap."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()

# Neon provides `?sslmode=require&channel_binding=require` in its connection
# string. SQLAlchemy's asyncpg dialect forwards unknown query params straight to
# asyncpg.connect(), where `sslmode` is not a valid keyword (it wants `ssl=True`).
# Strip those params and translate sslmode into a proper connect argument.
_parsed = urlparse(settings.sqlalchemy_url)
_query = dict(parse_qsl(_parsed.query))
_sslmode = _query.pop("sslmode", None)
_query.pop("channel_binding", None)
_clean_url = urlunparse(_parsed._replace(query=urlencode(_query)))
_connect_args: dict[str, object] = {}
if _sslmode in {"require", "verify-full", "true", "1"}:
    _connect_args["ssl"] = True

engine = create_async_engine(
    _clean_url,
    connect_args=_connect_args,
    echo=False,
    pool_pre_ping=True,
    # Render/Postgres can close idle connections; a small pool keeps things predictable.
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Log only scheme/host/database — never credentials — so a bad DATABASE_URL on
# a hosted platform is diagnosable from the logs alone.
logger.info(
    "database_target_configured scheme=%s host=%s database=%s ssl=%s",
    _parsed.scheme,
    _parsed.hostname,
    _parsed.path.lstrip("/"),
    bool(_connect_args),
)
if _parsed.scheme != "postgresql+asyncpg":
    logger.error(
        "database_url_scheme_wrong expected=postgresql+asyncpg got=%s", _parsed.scheme
    )


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
