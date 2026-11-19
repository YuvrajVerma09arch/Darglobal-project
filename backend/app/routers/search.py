"""Hybrid search without generation — useful for UI filtering and debugging."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import require_access_code
from app.db import get_db
from app.observability import PhaseTimer
from app.schemas import SearchRequest, SearchResponse, SearchResult
from app.services.embeddings import embedding_service
from app.services.retrieval import HybridRetriever

router = APIRouter(prefix="/search", tags=["search"], dependencies=[Depends(require_access_code)])
retriever = HybridRetriever()


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    timer = PhaseTimer()
    with timer.phase("embed"):
        vector = await embedding_service.embed_query(request.query)
    with timer.phase("retrieve"):
        items, query_type, applied, relaxation_note = await retriever.search(
            session,
            query=request.query,
            query_vector=vector,
            source_filter=request.source_filter,
            explicit_filters=request.filters,
            top_k=request.top_k,
        )
    stamps = [item.scraped_at for item in items if item.scraped_at]
    response.headers["Server-Timing"] = timer.header()
    return SearchResponse(
        results=[
            SearchResult(
                citation=item.as_citation(),
                semantic_score=item.semantic_score,
                structured_match=item.structured_match,
            )
            for item in items
        ],
        query_type=query_type,
        filters_applied=applied,
        data_as_of=max(stamps) if stamps else None,
        note=relaxation_note,
    )
