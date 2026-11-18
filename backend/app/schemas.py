"""Pydantic request/response contracts shared by every API endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

SourceFilter = Literal["both", "darglobal", "wasalt"]
DocumentType = Literal["property", "development", "faq", "platform", "unknown"]


class PropertyFilters(BaseModel):
    """Exact structured constraints applied in SQL before semantic retrieval."""

    location: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=80)
    property_type: str | None = Field(default=None, max_length=64)
    listing_type: Literal["sale", "rent", "both", "unknown"] | None = None
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    bedrooms: int | None = Field(default=None, ge=0, le=20)
    bathrooms: int | None = Field(default=None, ge=0, le=20)

    @model_validator(mode="after")
    def check_price_range(self) -> "PropertyFilters":
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price must be <= max_price")
        return self

    def is_empty(self) -> bool:
        return all(
            value is None
            for value in (
                self.location,
                self.city,
                self.property_type,
                self.listing_type,
                self.min_price,
                self.max_price,
                self.bedrooms,
                self.bathrooms,
            )
        )


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(
        default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    )
    source_filter: SourceFilter = "both"
    filters: PropertyFilters = Field(default_factory=PropertyFilters)
    stream: bool = False


class Citation(BaseModel):
    record_id: str
    source: str
    title: str | None
    url: str
    snippet: str
    score: float
    document_type: str | None = None
    property_type: str | None = None
    location: str | None = None
    price: float | None = None
    currency: str | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    area: float | None = None
    image_urls: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    citations: list[Citation]
    records: list[dict[str, Any]]
    retrieved_count: int
    query_type: str
    filters_applied: dict[str, Any]
    data_as_of: datetime | None = None
    model: str
    warnings: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    source_filter: SourceFilter = "both"
    filters: PropertyFilters = Field(default_factory=PropertyFilters)
    top_k: int = Field(default=8, ge=1, le=30)


class SearchResult(BaseModel):
    citation: Citation
    semantic_score: float | None = None
    structured_match: bool = False


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query_type: str
    filters_applied: dict[str, Any]
    data_as_of: datetime | None = None
    note: str | None = None


class PropertyOut(BaseModel):
    id: str
    source: str
    title: str | None = None
    description: str | None = None
    property_type: str | None = None
    location: str | None = None
    city: str | None = None
    country: str | None = None
    price: float | None = None
    currency: str | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    area: float | None = None
    area_unit: str | None = None
    amenities: list[str] = Field(default_factory=list)
    project_status: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    source_url: str
    scraped_at: datetime | None = None
    document_type: str | None = None


class PropertyListResponse(BaseModel):
    items: list[PropertyOut]
    total: int
    limit: int
    offset: int


class SourceStat(BaseModel):
    source: str
    records: int
    chunks: int
    last_scraped_at: datetime | None = None


class SourcesResponse(BaseModel):
    sources: list[SourceStat]
    generated_at: datetime


class StatsResponse(BaseModel):
    records: int
    chunks: int
    sources: dict[str, int]
    property_types: dict[str, int]
    cities: dict[str, int]
    bedrooms: list[int] = Field(default_factory=list)
    max_price: float | None = None
    last_scraped_at: datetime | None = None
    last_ingestion: dict[str, Any] | None = None


class IngestResponse(BaseModel):
    status: str
    source: str
    pages_scraped: int
    records_upserted: int
    chunks_indexed: int
    started_at: datetime
    finished_at: datetime
    notes: str | None = None
