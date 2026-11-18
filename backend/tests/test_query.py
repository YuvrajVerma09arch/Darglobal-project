"""Query classification and exact-constraint extraction tests."""

from app.schemas import PropertyFilters
from app.services.query import merge_filters, parse_query


def test_extracts_bedrooms_city_type_and_price_cap():
    filters, query_type, extracted = parse_query(
        "Show me 3 bedroom apartments in Riyadh under 2 million SAR"
    )
    assert filters.bedrooms == 3
    assert filters.city == "Riyadh"
    assert filters.property_type == "apartment"
    assert filters.max_price == 2_000_000
    assert extracted["bedrooms"] == 3
    assert query_type in {"listing", "general"}


def test_extracts_min_price_and_rental_intent():
    filters, _, extracted = parse_query("villas for rent in Dubai over 50000 AED")
    assert filters.listing_type == "rent"
    assert filters.min_price == 50_000
    assert filters.city == "Dubai"
    assert extracted["property_type"] == "villa"


def test_hyphenated_bedroom_count():
    filters, _, _ = parse_query("Find 3-bedroom apartments in Riyadh under 2 million SAR")
    assert filters.bedrooms == 3
    assert filters.max_price == 2_000_000


def test_comparison_query_classification():
    _, query_type, _ = parse_query("Compare Neptune with The Astera")
    assert query_type == "comparison"


def test_unknown_query_has_no_filters():
    filters, _, extracted = parse_query("What is the capital of France?")
    assert filters.is_empty()
    assert extracted == {}


def test_explicit_filters_win_over_parsed():
    parsed = PropertyFilters(city="Dubai", bedrooms=2)
    explicit = PropertyFilters(city="Riyadh")
    merged, applied = merge_filters(explicit, parsed)
    assert merged.city == "Riyadh"
    assert merged.bedrooms == 2
    assert applied["city"] == "Riyadh"


def test_invalid_price_range_rejected():
    import pydantic

    try:
        PropertyFilters(min_price=200, max_price=100)
    except pydantic.ValidationError:
        return
    raise AssertionError("Expected validation error")
