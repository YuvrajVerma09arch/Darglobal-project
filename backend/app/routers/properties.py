"""Structured property browsing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import require_access_code
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Property
from app.schemas import PropertyFilters, PropertyListResponse, PropertyOut, SourceFilter
from app.services.retrieval import HybridRetriever

router = APIRouter(prefix="/properties", tags=["properties"], dependencies=[Depends(require_access_code)])
retriever = HybridRetriever()


def to_out(row: Property) -> PropertyOut:
    return PropertyOut(
        id=row.id,
        source=row.source,
        title=row.title,
        description=row.description,
        property_type=row.property_type,
        location=row.location,
        city=row.city,
        country=row.country,
        price=float(row.price) if row.price is not None else None,
        currency=row.currency,
        bedrooms=row.bedrooms,
        bathrooms=row.bathrooms,
        area=float(row.area) if row.area is not None else None,
        area_unit=row.area_unit,
        amenities=row.amenities or [],
        project_status=row.project_status,
        image_urls=row.image_urls or [],
        source_url=row.source_url,
        scraped_at=row.scraped_at,
        document_type=row.document_type,
    )


@router.get("", response_model=PropertyListResponse)
async def list_properties(
    source: SourceFilter = "both",
    location: str | None = None,
    city: str | None = None,
    property_type: str | None = None,
    listing_type: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    bedrooms: int | None = None,
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    filters = PropertyFilters(
        location=location,
        city=city,
        property_type=property_type,
        listing_type=listing_type if listing_type in {"sale", "rent", "both", "unknown"} else None,
        min_price=min_price,
        max_price=max_price,
        bedrooms=bedrooms,
    )
    rows, total = await retriever.search_without_vector(
        session, source, filters, limit=limit, offset=offset
    )
    return PropertyListResponse(
        items=[to_out(row) for row in rows], total=total, limit=limit, offset=offset
    )


@router.get("/{property_id}", response_model=PropertyOut)
async def get_property(property_id: str, session: AsyncSession = Depends(get_db)):
    row = await session.get(Property, property_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return to_out(row)
