"""Normalisation and idempotency tests for ingestion."""

import json

from app.services import ingestion
from app.services.ingestion import normalise_record, read_records


def test_missing_fields_remain_null_and_lists_are_empty():
    record = normalise_record({"source": "wasalt", "source_url": "https://wasalt.sa/x"})
    assert record["title"] is None
    assert record["price"] is None
    assert record["bedrooms"] is None
    assert record["amenities"] == []
    assert record["image_urls"] == []
    assert record["document_type"] == "property"
    assert record["source"] == "wasalt"


def test_provenance_is_preserved_in_metadata():
    record = normalise_record(
        {
            "source": "darglobal",
            "source_url": "https://darglobal.co.uk/neptune",
            "provenance": "archived_snapshot",
            "snapshot_date": "2025-06-01",
        }
    )
    assert record["metadata"]["provenance"] == "archived_snapshot"
    assert record["metadata"]["snapshot_date"] == "2025-06-01"


def test_duplicate_urls_are_deduplicated(tmp_path, monkeypatch):
    monkeypatch.setattr(ingestion, "RAW_DIR", tmp_path)
    row = {"source": "wasalt", "source_url": "https://wasalt.sa/en/property/sale/x-1", "title": "X"}
    for name in ("wasalt_a.jsonl", "wasalt_b.jsonl"):
        (tmp_path / name).write_text(json.dumps(row) + "\n", encoding="utf-8")
    files = ingestion.load_snapshot_files("wasalt")
    records, malformed = read_records(files)
    assert len(records) == 1
    assert malformed == 0


def test_malformed_lines_are_counted(tmp_path, monkeypatch):
    monkeypatch.setattr(ingestion, "RAW_DIR", tmp_path)
    (tmp_path / "bad.jsonl").write_text("{not json}\n", encoding="utf-8")
    records, malformed = read_records(ingestion.load_snapshot_files("both"))
    assert records == []
    assert malformed == 1
