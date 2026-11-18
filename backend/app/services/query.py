"""Deterministic query classification and exact-constraint extraction.

No extra LLM call is needed for the common real-estate query shapes. This keeps
latency low and makes filtering auditable. The LLM is only used to generate the
final grounded answer.
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas import PropertyFilters

CITY_ALIASES: dict[str, str] = {
    "riyadh": "Riyadh",
    "الرياض": "Riyadh",
    "jeddah": "Jeddah",
    "jeddah": "Jeddah",
    "dammam": "Dammam",
    "mecca": "Mecca",
    "makkah": "Mecca",
    "medina": "Medina",
    "dubai": "Dubai",
    "abu dhabi": "Abu Dhabi",
    "sharjah": "Sharjah",
    "marbella": "Marbella",
    "london": "London",
    "istanbul": "Istanbul",
    "new york": "New York",
    "lisbon": "Lisbon",
    "miami": "Miami",
    "paris": "Paris",
}

TYPE_ALIASES: dict[str, str] = {
    "apartment": "apartment",
    "apartments": "apartment",
    "flat": "apartment",
    "flats": "apartment",
    "villa": "villa",
    "villas": "villa",
    "townhouse": "townhouse",
    "townhouses": "townhouse",
    "penthouse": "penthouse",
    "penthouses": "penthouse",
    "house": "house",
    "houses": "house",
    "studio": "studio",
    "land": "land",
    "office": "office",
    "commercial": "commercial",
}

_BED_RE = re.compile(r"\b(\d+)\s*[- ]?\s*(?:bed(?:room)?s?|br|beds?)\b", re.I)
_BATH_RE = re.compile(r"\b(\d+)\s*[- ]?\s*(?:bath(?:room)?s?|baths?)\b", re.I)
_PRICE_RE = re.compile(
    r"(?:sar|riyal|dubai?\s*dirham|aed|usd|\$|د\.?ك)?\s*"
    r"([\d,.]+)\s*(million|m|k|thousand)?",
    re.I,
)
_COMPARE_WORDS = ("compare", "comparison", "versus", "vs", "difference between", "differ")


def _extract_price(query: str) -> tuple[float | None, float | None]:
    """Return (min, max) for 'under/below X' and 'over/above X' patterns only."""
    low = query.lower()
    result: tuple[float | None, float | None] = (None, None)
    match = re.search(
        r"(?:under|below|less than|up to|at most|<=)\s*(?:sar|aed|usd|\$)?\s*([\d,.]+)\s*(million|m|k)?",
        low,
    )
    if match:
        value = float(match.group(1).replace(",", ""))
        if match.group(2) and match.group(2).lower() in {"million", "m"}:
            value *= 1_000_000
        elif match.group(2) and match.group(2).lower() == "k":
            value *= 1_000
        result = (result[0], value)
    match = re.search(
        r"(?:over|above|more than|at least|>=)\s*(?:sar|aed|usd|\$)?\s*([\d,.]+)\s*(million|m|k)?",
        low,
    )
    if match:
        value = float(match.group(1).replace(",", ""))
        if match.group(2) and match.group(2).lower() in {"million", "m"}:
            value *= 1_000_000
        elif match.group(2) and match.group(2).lower() == "k":
            value *= 1_000
        result = (value, result[1])
    return result


def parse_query(query: str) -> tuple[PropertyFilters, str, dict[str, Any]]:
    """Extract exact filters, classify intent, and return audit metadata."""
    low = query.lower()
    filters = PropertyFilters()
    extracted: dict[str, Any] = {}

    for alias, canonical in CITY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", low):
            extracted["city"] = canonical
            break

    for alias, canonical in TYPE_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", low):
            extracted["property_type"] = canonical
            break

    bed = _BED_RE.search(low)
    if bed:
        extracted["bedrooms"] = int(bed.group(1))
    bath = _BATH_RE.search(low)
    if bath:
        extracted["bathrooms"] = int(bath.group(1))

    minimum, maximum = _extract_price(query)
    if minimum is not None:
        extracted["min_price"] = minimum
    if maximum is not None:
        extracted["max_price"] = maximum

    if re.search(r"\bfor\s+sale\b|\bbuy\b|\bpurchase\b|\bsale\b", low):
        extracted["listing_type"] = "sale"
    elif re.search(r"\bfor\s+rent\b|\brental\b|\bto\s+rent\b|\blease\b", low):
        extracted["listing_type"] = "rent"

    filters = PropertyFilters(**extracted)

    if any(word in low for word in _COMPARE_WORDS):
        query_type = "comparison"
    elif re.search(r"\b(show|find|list|which|what properties|apartments|villas|homes)\b", low):
        query_type = "listing"
    elif re.search(r"\b(tell me about|what is|describe|details|amenities|about)\b", low):
        query_type = "detail"
    else:
        query_type = "general"

    return filters, query_type, extracted


def merge_filters(
    explicit: PropertyFilters, parsed: PropertyFilters
) -> tuple[PropertyFilters, dict[str, Any]]:
    """Explicit UI filters win; parsed filters fill the gaps."""
    merged = explicit.model_copy(update={
        key: value
        for key, value in parsed.model_dump().items()
        if value is not None and getattr(explicit, key) is None
    })
    return merged, {k: v for k, v in merged.model_dump().items() if v is not None}
