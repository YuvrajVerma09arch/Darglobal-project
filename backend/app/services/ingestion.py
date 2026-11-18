"""Reproducible, idempotent ingestion from saved public-data snapshots.

The scraper writes JSONL snapshots under `data/raw/`. This service normalises
them, upserts properties, re-chunks and re-embeds only changed content, and
records an ingestion run. Re-running it is safe.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.paths import project_root

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Chunk, IngestionRun, Property
from app.services.embeddings import embedding_service
from app.services.text import clean_text, chunk_text, content_hash, make_record_id, parse_timestamp, record_text

logger = logging.getLogger(__name__)
settings = get_settings()

DATA_DIR = Path(os.getenv("DATA_DIR", str(project_root() / "data")))
RAW_DIR = DATA_DIR / "raw"

OPTIONAL_LISTS = ("amenities", "image_urls")
OPTIONAL_STRINGS = (
    "title",
    "description",
    "property_type",
    "location",
    "city",
    "country",
    "currency",
    "area_unit",
    "project_status",
    "document_type",
)
OPTIONAL_NUMBERS = ("price", "bedrooms", "bathrooms", "area")
OPTIONAL_INTS = ("bedrooms", "bathrooms")


def normalise_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce a raw snapshot row into the normalized schema. Missing => null."""
    record: dict[str, Any] = {
        "source": str(raw.get("source") or "unknown").lower().strip(),
        "source_url": str(raw.get("source_url") or "").strip(),
    }
    for key in OPTIONAL_STRINGS:
        value = clean_text(str(raw.get(key))) if raw.get(key) is not None else None
        record[key] = value or None
    for key in OPTIONAL_NUMBERS:
        value = raw.get(key)
        if value in (None, ""):
            record[key] = None
        else:
            try:
                number = float(value)
                record[key] = int(number) if key in OPTIONAL_INTS else number
            except (TypeError, ValueError):
                record[key] = None
    for key in OPTIONAL_LISTS:
        value = raw.get(key)
        record[key] = [str(item) for item in value] if isinstance(value, (list, tuple)) else []
    record["document_type"] = record.get("document_type") or "property"
    record["scraped_at"] = parse_timestamp(raw.get("scraped_at")) or datetime.now(timezone.utc)
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    metadata = dict(metadata)
    for key in ("provenance", "snapshot_date", "notes", "acquisition"):
        if raw.get(key) is not None:
            metadata[key] = raw[key]
    record["metadata"] = metadata
    record["raw_content"] = clean_text(str(raw.get("raw_content") or ""))[:4000] or None
    record["id"] = make_record_id(record)
    record["content_hash"] = content_hash(record)
    return record


def load_snapshot_files(source: str) -> list[Path]:
    if not RAW_DIR.exists():
        return []
    files = sorted(RAW_DIR.glob("*.jsonl"))
    if source != "both":
        files = [path for path in files if source in path.name.lower()]
    return files


def read_records(files: list[Path]) -> tuple[list[dict[str, Any]], int]:
    records: dict[str, dict[str, Any]] = {}
    malformed = 0
    for path in files:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    normalised = normalise_record(raw)
                    if normalised["source_url"]:
                        records[normalised["id"]] = normalised
                except (json.JSONDecodeError, TypeError, ValueError):
                    malformed += 1
    return list(records.values()), malformed


class IngestionService:
    async def run(self, session: AsyncSession, source: str = "both") -> dict[str, Any]:
        started = datetime.now(timezone.utc)
        run = IngestionRun(source=source, status="running")
        session.add(run)
        await session.commit()

        files = load_snapshot_files(source)
        records, malformed = read_records(files)
        notes = [f"snapshot_files={len(files)}", f"malformed_lines={malformed}"]
        if not records:
            notes.append("no_records_found")
        records_upserted = 0
        chunks_indexed = 0

        try:
            for record in records:
                existing = await session.get(Property, record["id"])
                if existing and existing.content_hash == record["content_hash"]:
                    continue
                values = {key: value for key, value in record.items() if key != "id"}
                if existing:
                    for key, value in values.items():
                        setattr(existing, key, value)
                    prop = existing
                else:
                    prop = Property(id=record["id"], **values)
                    session.add(prop)
                records_upserted += 1

                # Re-embed only when content changed; delete stale chunks first.
                await self._replace_chunks(session, prop, record)
                chunks_indexed += 1

            await session.commit()
            status = "success"
        except Exception as exc:
            await session.rollback()
            status = "failed"
            notes.append(f"error={str(exc)[:200]}")
            logger.exception("ingestion_failed", extra={"error": str(exc)[:200]})

        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        run.pages_scraped = len(files)
        run.records_upserted = records_upserted
        run.chunks_indexed = chunks_indexed
        run.notes = " | ".join(notes)
        await session.commit()

        return {
            "status": status,
            "source": source,
            "pages_scraped": len(files),
            "records_upserted": records_upserted,
            "chunks_indexed": chunks_indexed,
            "started_at": started,
            "finished_at": run.finished_at,
            "notes": run.notes,
        }

    async def _replace_chunks(self, session: AsyncSession, prop: Property, record: dict[str, Any]) -> None:
        await session.execute(
            delete(Chunk).where(Chunk.property_id == prop.id).execution_options(synchronize_session=False)
        )

        text = record_text(record)
        parts = chunk_text(text)
        if not parts:
            return
        vectors = await embedding_service.embed_documents(parts)
        for index, (part, vector) in enumerate(zip(parts, vectors)):
            session.add(
                Chunk(
                    id=f"{prop.id}:{index}",
                    property_id=prop.id,
                    chunk_index=index,
                    text=part,
                    embedding=vector,
                    source=prop.source,
                    source_url=prop.source_url,
                    document_type=prop.document_type,
                    location=prop.location,
                    property_type=prop.property_type,
                    scraped_at=prop.scraped_at,
                    metadata_={
                        "city": prop.city,
                        "price": prop.price,
                        "currency": prop.currency,
                        "bedrooms": prop.bedrooms,
                        "provenance": (prop.metadata_ or {}).get("provenance"),
                    },
                )
            )


ingestion_service = IngestionService()
