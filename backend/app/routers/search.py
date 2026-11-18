"""Hybrid search without generation — useful for UI filtering and debugging."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import SearchRequest, SearchResponse, SearchResult
from app.services.embeddings import embedding_service
from app.services.retrieval import HybridRetriever

router = APIRouter(prefix="/search", tags=["search"])
retriever = HybridRetriever()


@router.post("", response_model=SearchResponse)
async def search(request: SearchRequest, session: AsyncSession = Depends(get_db)):
    vector = await embedding_service.embed_query(request.query)
    items, query_type, applied = await retriever.search(
        session,
        query=request.query,
        query_vector=vector,
        source_filter=request.source_filter,
        explicit_filters=request.filters,
        top_k=request.top_k,
    )
    stamps = [item.scraped_at for item in items if item.scraped_at]
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
    )
