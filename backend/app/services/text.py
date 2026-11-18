"""Text cleanup, deterministic chunking and record identity helpers."""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime
from typing import Any

_WS = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")


def clean_text(value: str | None) -> str:
    """Strip markup/boilerplate-ish noise and normalise whitespace."""
    if not value:
        return ""
    text = html.unescape(value)
    text = _TAG.sub(" ", text)
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    text = _WS.sub(" ", text).strip()
    return text


def content_hash(record: dict[str, Any]) -> str:
    """Stable hash of the semantic content; used for idempotent re-indexing."""
    canonical = {
        key: record.get(key)
        for key in (
            "source",
            "title",
            "description",
            "property_type",
            "location",
            "price",
            "currency",
            "bedrooms",
            "bathrooms",
            "area",
            "amenities",
            "project_status",
            "source_url",
        )
    }
    payload = json.dumps(canonical, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_record_id(record: dict[str, Any]) -> str:
    seed = f"{record.get('source', '')}|{record.get('source_url', '')}"
    return "r_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def chunk_text(text: str, target: int = 900, overlap: int = 120) -> list[str]:
    """Split text on paragraph/sentence boundaries with a small overlap."""
    text = clean_text(text)
    if not text:
        return []
    if len(text) <= target:
        return [text]

    paragraphs = [clean_text(p) for p in re.split(r"\n\s*\n|(?<=[.!?])\s+", text)]
    paragraphs = [p for p in paragraphs if p]

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(para) > target:
            if current:
                chunks.append(current.strip())
                current = ""
            words = para.split()
            start = 0
            while start < len(words):
                piece: list[str] = []
                while start < len(words) and len(" ".join(piece + [words[start]])) <= target:
                    piece.append(words[start])
                    start += 1
                if not piece:
                    piece = [words[start]]
                    start += 1
                chunks.append(" ".join(piece))
                if start >= len(words):
                    break
            continue
        candidate = f"{current} {para}".strip()
        if len(candidate) <= target:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
                tail = " ".join(current.split()[-overlap // 5 :]) if overlap else ""
                current = f"{tail} {para}".strip()
            else:
                current = para

    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if c]


def record_text(record: dict[str, Any]) -> str:
    """Build the indexed text for a record from all available structured fields."""
    parts: list[str] = []
    for key, label in (
        ("title", "Title"),
        ("description", "Description"),
        ("property_type", "Property type"),
        ("location", "Location"),
        ("city", "City"),
        ("country", "Country"),
        ("project_status", "Status"),
    ):
        value = clean_text(str(record.get(key) or ""))
        if value:
            parts.append(f"{label}: {value}")

    price = record.get("price")
    if price not in (None, ""):
        parts.append(f"Price: {record.get('currency') or ''} {price}".strip())

    specs = []
    if record.get("bedrooms") is not None:
        specs.append(f"{record['bedrooms']} bedrooms")
    if record.get("bathrooms") is not None:
        specs.append(f"{record['bathrooms']} bathrooms")
    if record.get("area") is not None:
        specs.append(f"{record['area']} {record.get('area_unit') or ''}".strip())
    if specs:
        parts.append("Specifications: " + ", ".join(specs))

    amenities = record.get("amenities") or []
    if isinstance(amenities, (list, tuple)) and amenities:
        parts.append("Amenities: " + ", ".join(str(a) for a in amenities))

    metadata = record.get("metadata") or {}
    if isinstance(metadata, dict):
        for key in ("listing_type", "category", "developer", "agent", "platform_info"):
            value = clean_text(str(metadata.get(key) or ""))
            if value:
                parts.append(f"{key.replace('_', ' ').title()}: {value}")

    return "\n".join(parts)


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
