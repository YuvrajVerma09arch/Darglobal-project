"""Text cleaning and chunking tests."""

from app.services.text import clean_text, chunk_text, content_hash, make_record_id, record_text


def test_clean_text_removes_markup_and_normalises_whitespace():
    assert clean_text("  <p>Hello&nbsp; <b>world</b></p>\n\n  again ") == "Hello world again"


def test_clean_text_handles_missing():
    assert clean_text(None) == ""
    assert clean_text("") == ""


def test_chunk_text_splits_long_text_with_overlap():
    text = ("Apartment in Riyadh with three bedrooms and a large terrace. " * 40)
    chunks = chunk_text(text, target=300, overlap=60)
    assert len(chunks) > 1
    assert all(len(chunk) <= 320 for chunk in chunks)
    assert "Riyadh" in chunks[0]


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_hash_is_stable_and_id_is_url_derived():
    record = {"source": "wasalt", "source_url": "https://wasalt.sa/en/property/sale/x-1", "title": "X"}
    assert content_hash(record) == content_hash(record)
    assert make_record_id(record) == make_record_id(record)
    assert make_record_id(record).startswith("r_")


def test_record_text_includes_available_attributes_only():
    text = record_text(
        {
            "title": "Villa",
            "description": "A family villa.",
            "bedrooms": 5,
            "amenities": ["Pool", "Garden"],
            "price": None,
        }
    )
    assert "Villa" in text
    assert "5 bedrooms" in text
    assert "Pool" in text
    assert "Price" not in text
