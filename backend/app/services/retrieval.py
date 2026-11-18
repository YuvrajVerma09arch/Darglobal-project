"""Hybrid retrieval: exact SQL constraints + pgvector semantic search, fused with RRF."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Chunk, Property
from app.schemas import Citation, PropertyFilters, SourceFilter

settings = get_settings()
from app.services.query import merge_filters, parse_query

logger = logging.getLogger(__name__)


@dataclass
class RetrievedItem:
    property_id: str
    source: str
    title: str | None
    description: str | None
    url: str
    location: str | None
    city: str | None
    price: float | None
    currency: str | None
    bedrooms: int | None
    bathrooms: int | None
    area: float | None
    property_type: str | None
    document_type: str | None
    image_urls: list[str]
    scraped_at: datetime | None
    snippet: str
    score: float
    semantic_score: float | None = None
    structured_match: bool = False

    def as_citation(self) -> Citation:
        return Citation(
            record_id=self.property_id,
            source=self.source,
            title=self.title,
            url=self.url,
            snippet=self.snippet,
            score=round(self.score, 6),
            document_type=self.document_type,
            property_type=self.property_type,
            location=self.location,
            price=self.price,
            currency=self.currency,
            bedrooms=self.bedrooms,
            bathrooms=self.bathrooms,
            area=self.area,
            image_urls=self.image_urls or [],
        )

    def as_record(self) -> dict[str, Any]:
        return {
            "id": self.property_id,
            "source": self.source,
            "title": self.title,
            "description": self.description,
            "property_type": self.property_type,
            "location": self.location,
            "city": self.city,
            "price": self.price,
            "currency": self.currency,
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "area": self.area,
            "document_type": self.document_type,
            "image_urls": self.image_urls or [],
            "source_url": self.url,
            "scraped_at": self.scraped_at,
        }


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_conditions(
    filters: PropertyFilters, source_filter: SourceFilter, model: type = Property
) -> list[Any]:
    """Build parameterised SQL conditions for exact constraint filtering."""
    conditions: list[Any] = []
    if source_filter != "both":
        conditions.append(model.source == source_filter)
    if filters.location:
        pattern = f"%{_escape_like(filters.location)}%"
        conditions.append(
            or_(
                model.location.ilike(pattern, escape="\\"),
                model.city.ilike(pattern, escape="\\"),
            )
        )
    if filters.city:
        conditions.append(model.city.ilike(f"%{_escape_like(filters.city)}%", escape="\\"))
    if filters.property_type:
        conditions.append(
            or_(
                model.property_type.ilike(f"%{_escape_like(filters.property_type)}%", escape="\\"),
                model.title.ilike(f"%{_escape_like(filters.property_type)}%", escape="\\"),
            )
        )
    # listing_type lives on the property JSONB column; Chunk has no such column,
    # so the vector channel must reach it via the property-id subquery instead.
    if model is Property and filters.listing_type and filters.listing_type != "both":
        conditions.append(
            func.coalesce(Property.metadata_["listing_type"].astext, "unknown")
            == filters.listing_type
        )
    if filters.min_price is not None:
        conditions.append(Property.price >= filters.min_price)
    if filters.max_price is not None:
        conditions.append(Property.price <= filters.max_price)
    # "3 bedroom apartments" is an exact constraint, not a minimum.
    if filters.bedrooms is not None:
        conditions.append(Property.bedrooms == filters.bedrooms)
    if filters.bathrooms is not None:
        conditions.append(Property.bathrooms == filters.bathrooms)
    return conditions


class HybridRetriever:
    def __init__(self, rrf_k: int = 60) -> None:
        self.rrf_k = rrf_k

    @staticmethod
    def _item(
        prop: Property,
        snippet: str,
        score: float,
        semantic_score: float | None = None,
        structured_match: bool = False,
    ) -> RetrievedItem:
        return RetrievedItem(
            property_id=prop.id,
            source=prop.source,
            title=prop.title,
            description=prop.description or "",
            url=prop.source_url,
            location=prop.location,
            city=prop.city,
            price=float(prop.price) if prop.price is not None else None,
            currency=prop.currency,
            bedrooms=prop.bedrooms,
            bathrooms=prop.bathrooms,
            area=float(prop.area) if prop.area is not None else None,
            property_type=prop.property_type,
            document_type=prop.document_type,
            image_urls=prop.image_urls or [],
            scraped_at=prop.scraped_at,
            snippet=snippet[:1600],
            score=score,
            semantic_score=semantic_score,
            structured_match=structured_match,
        )

    async def search(
        self,
        session: AsyncSession,
        query: str,
        query_vector: list[float],
        source_filter: SourceFilter = "both",
        explicit_filters: PropertyFilters | None = None,
        top_k: int = 8,
        candidate_k: int = 24,
        allow_relax: bool = True,
        use_query_filters: bool = True,
    ) -> tuple[list[RetrievedItem], str, dict[str, Any], str | None]:
        parsed, query_type, _ = parse_query(query)
        if use_query_filters:
            filters, applied = merge_filters(explicit_filters or PropertyFilters(), parsed)
        else:
            filters = explicit_filters or PropertyFilters()
            applied = {k: v for k, v in filters.model_dump().items() if v is not None}
        conditions = build_conditions(filters, source_filter)
        # The property-id subquery is the bridge between exact SQL constraints
        # and the vector channel: both channels see the same structural filter.
        candidate_ids = select(Property.id).where(and_(true(), *conditions))

        # --- Channel A: structural exact-match candidates -------------------
        structured_stmt: Select = (
            select(Property)
            .where(Property.id.in_(candidate_ids))
            .order_by(Property.scraped_at.desc())
            .limit(200)
        )
        structured_rows = (await session.execute(structured_stmt)).scalars().all()
        structured_by_id = {row.id: row for row in structured_rows}

        # --- Channel B: pgvector semantic candidates ------------------------
        distance = Chunk.embedding.cosine_distance(query_vector)
        stmt = (
            select(
                Chunk.id,
                Chunk.property_id,
                Chunk.source,
                Chunk.text,
                Chunk.document_type,
                Chunk.location,
                Chunk.scraped_at,
                distance.label("distance"),
            )
            .where(
                and_(
                    Chunk.property_id.in_(candidate_ids),
                    (Chunk.source == source_filter) if source_filter != "both" else True,
                    Chunk.embedding.is_not(None),
                )
            )
            .order_by(distance)
            .limit(candidate_k)
        )
        all_semantic_rows = (await session.execute(stmt)).all()
        # A vector index always returns nearest neighbours. Without a relevance
        # floor, an unrelated question would still look "grounded". Measured BGE
        # cosine similarity is ~0.77+ for on-topic and ~0.51 for off-topic.
        semantic_rows = [
            row for row in all_semantic_rows
            if (1.0 - float(row.distance or 1.0)) >= settings.min_semantic_similarity
        ]

        # --- Reciprocal rank fusion -----------------------------------------
        fused: dict[str, float] = {}
        semantic_rank: dict[str, float] = {}
        for rank, row in enumerate(semantic_rows, start=1):
            fused[row.property_id] = fused.get(row.property_id, 0.0) + 1.0 / (self.rrf_k + rank)
            semantic_rank[row.property_id] = 1.0 - float(row.distance or 0.0)

        # Structured ranking only contributes when the user actually supplied an
        # exact constraint. Otherwise it would inject arbitrary recent records.
        if not filters.is_empty():
            for rank, property_id in enumerate(structured_by_id, start=1):
                fused[property_id] = fused.get(property_id, 0.0) + 1.0 / (self.rrf_k + rank)

        # Property rows for semantically retrieved chunks not in the filtered set.
        needed_ids = set(fused) - set(structured_by_id)
        if needed_ids:
            rows = (
                await session.execute(select(Property).where(Property.id.in_(needed_ids)))
            ).scalars().all()
            for row in rows:
                structured_by_id[row.id] = row

        best_snippet: dict[str, str] = {}
        for row in semantic_rows:
            if row.property_id not in best_snippet:
                best_snippet[row.property_id] = row.text

        items: list[RetrievedItem] = []
        for property_id, score in sorted(fused.items(), key=lambda pair: pair[1], reverse=True)[:top_k]:
            prop = structured_by_id.get(property_id)
            if prop is None:
                continue
            items.append(
                self._item(
                    prop,
                    best_snippet.get(prop.id, prop.description or ""),
                    score,
                    semantic_rank.get(prop.id),
                    prop.id in structured_by_id and prop.id not in semantic_rank,
                )
            )

        relaxation_note: str | None = None
        if not items and allow_relax and not filters.is_empty():
            # Strict filters matched nothing. Relax one constraint group at a
            # time and return real alternatives instead of a dead end.
            base = filters.model_dump()
            plan: list[tuple[dict[str, Any], str]] = []

            def candidate(**drop: int) -> dict[str, Any]:
                return {k: v for k, v in base.items() if v is not None and k not in drop}

            plan.append((candidate(bedrooms=1, bathrooms=1), "Bedroom/bathroom counts were relaxed."))
            plan.append(
                (candidate(bedrooms=1, bathrooms=1, property_type=1), "Property type was relaxed.")
            )
            plan.append(
                (
                    candidate(bedrooms=1, bathrooms=1, property_type=1, location=1, city=1),
                    "Location was relaxed.",
                )
            )
            plan.append(
                (
                    candidate(
                        bedrooms=1, bathrooms=1, property_type=1, location=1, city=1,
                        min_price=1, max_price=1, listing_type=1,
                    ),
                    "Price and listing-type constraints were relaxed.",
                )
            )

            for relaxed_filters, note in plan:
                found, _, relaxed_applied, _ = await self.search(
                    session,
                    query=query,
                    query_vector=query_vector,
                    source_filter=source_filter,
                    explicit_filters=PropertyFilters(**relaxed_filters),
                    top_k=top_k,
                    candidate_k=candidate_k,
                    allow_relax=False,
                    use_query_filters=False,
                )
                if found:
                    items, applied, relaxation_note = found, relaxed_applied, note
                    break

            if not items:
                # Last resort: show other real records from the same source so
                # the user always has something concrete to refine from.
                rows, _ = await self.search_without_vector(
                    session, source_filter, PropertyFilters(), limit=top_k
                )
                items = [self._item(row, row.description or "", 0.0) for row in rows]
                applied = {}
                relaxation_note = "No exact match; showing other records from the snapshot."

        logger.info(
            "hybrid_retrieval",
            extra={
                "query_type": query_type,
                "structured": len(structured_rows),
                "semantic": len(semantic_rows),
                "returned": len(items),
                "filters": applied,
                "relaxed": bool(relaxation_note),
            },
        )
        return items, query_type, applied, relaxation_note

    async def search_without_vector(
        self,
        session: AsyncSession,
        source_filter: SourceFilter = "both",
        explicit_filters: PropertyFilters | None = None,
        limit: int = 24,
        offset: int = 0,
    ) -> tuple[list[Property], int]:
        """Pure structured query for the /properties endpoint."""
        filters = explicit_filters or PropertyFilters()
        conditions = build_conditions(filters, source_filter)
        total = await session.scalar(
            select(func.count()).select_from(Property).where(and_(true(), *conditions))
        )
        rows = (
            (
                await session.execute(
                    select(Property)
                    .where(and_(true(), *conditions))
                    .order_by(Property.scraped_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), int(total or 0)
