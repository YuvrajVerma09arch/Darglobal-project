"""Optional live-DB integration test.

Run with `RUN_DB_TESTS=1 pytest tests/test_integration_live.py` after ingestion.
Skipped by default so the unit suite needs no Postgres. All async work runs in a
single event loop because the asyncpg pool is created at import time.
"""

from __future__ import annotations

import asyncio
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1", reason="requires a running Postgres with ingested data"
)


def test_live_hybrid_pipeline():
    from app.db import SessionLocal, engine
    from app.schemas import ChatRequest, PropertyFilters
    from app.services.embeddings import embedding_service
    from app.services.rag import rag_service
    from app.services.retrieval import HybridRetriever

    async def run():
        # TestClient's lifespan may have bound pooled connections to another loop.
        await engine.dispose()
        retriever = HybridRetriever()
        async with SessionLocal() as session:
            vector = await embedding_service.embed_query(
                "3 bedroom apartments in Riyadh under 2 million SAR"
            )
            items, query_type, applied = await retriever.search(
                session,
                "3 bedroom apartments in Riyadh under 2 million SAR",
                vector,
                source_filter="wasalt",
                explicit_filters=PropertyFilters(),
                top_k=10,
            )
            assert items and query_type == "listing"
            assert applied["bedrooms"] == 3 and applied["max_price"] == 2_000_000
            for item in items:
                assert item.source == "wasalt"
                assert item.bedrooms == 3
                assert item.price is None or item.price <= 2_000_000

            darglobal, _, _ = await retriever.search(
                session, "developments", vector, source_filter="darglobal", top_k=10
            )
            assert darglobal and all(item.source == "darglobal" for item in darglobal)

            unsupported = await rag_service.chat(
                session, ChatRequest(message="What is the population of Brazil?")
            )
            assert unsupported.citations == []
            assert "don't have that information" in unsupported.answer

            grounded = await rag_service.chat(
                session, ChatRequest(message="Show me apartments in Riyadh")
            )
            assert grounded.retrieved_count > 0
            for citation in grounded.citations:
                assert citation.url.startswith("https://")
                assert citation.source in {"darglobal", "wasalt"}
                assert citation.record_id

    asyncio.run(run())
