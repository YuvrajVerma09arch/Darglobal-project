"""Latency attribution: Server-Timing header, SSE timing frame, PhaseTimer.

These are the regression guard for the performance pass: if a change stops
reporting phase timings, the next person loses the ability to tell which
phase blew the budget (see scripts/perf_bench.py and PERF.md).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import Response
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.observability import PhaseTimer
from app.routers import properties as properties_router
from app.routers import search as search_router
from app.schemas import ChatRequest, SearchRequest
from app.services import rag
from app.services.rag import rag_service
from app.services.retrieval import RetrievedItem


def make_item() -> RetrievedItem:
    return RetrievedItem(
        property_id="r_perf1",
        source="wasalt",
        title="Marina apartment",
        description="Two bedrooms by the water.",
        url="https://wasalt.sa/en/property/sale/perf1",
        location="Jeddah",
        city="Jeddah",
        price=900_000.0,
        currency="SAR",
        bedrooms=2,
        bathrooms=2,
        area=110.0,
        property_type="apartment",
        document_type="listing",
        image_urls=[],
        scraped_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        snippet="Two bedrooms by the water.",
        score=0.42,
    )


def parse_frames(frames: list[str]) -> list[tuple[str, dict]]:
    events = []
    for frame in frames:
        event, data = "message", ""
        for line in frame.split("\n"):
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data = line[6:]
        if data:
            events.append((event, json.loads(data)))
    return events


def test_phase_timer_formats_server_timing_header():
    timer = PhaseTimer()
    with timer.phase("embed"):
        pass
    timer.record("llm_ttfb", 12.5)

    header = timer.header()
    assert "embed;dur=" in header
    assert "llm_ttfb;dur=12.5" in header
    assert "total;dur=" in header
    assert set(timer.phases) == {"embed", "llm_ttfb"}
    assert timer.frame_data()["llm_ttfb"] == 12.5
    assert timer.frame_data()["total"] >= 0


def test_health_reports_db_phase():
    """Health must expose its DB time so budget misses are attributable."""

    class FakeSession:
        async def execute(self, *args, **kwargs):
            return None

        async def scalar(self, *args, **kwargs):
            return None

    app.dependency_overrides[get_db] = lambda: FakeSession()
    try:
        with TestClient(app) as http:
            response = http.get("/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    timing = response.headers.get("server-timing", "")
    assert "db;dur=" in timing
    assert "total;dur=" in timing


def test_properties_route_renders_with_timing(monkeypatch):
    """Guard the route against NameErrors in its instrumentation imports."""

    async def fake_search_without_vector(*args, **kwargs):
        return [], 0

    monkeypatch.setattr(
        properties_router.retriever, "search_without_vector", fake_search_without_vector
    )
    app.dependency_overrides[get_db] = lambda: None
    try:
        with TestClient(app) as http:
            response = http.get("/api/v1/properties")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert "db;dur=" in response.headers.get("server-timing", "")


async def test_search_reports_embed_and_retrieve_phases(monkeypatch):
    async def fake_embed(query: str):
        return [0.0] * 384

    async def fake_search(*args, **kwargs):
        return [], "general", {}, None

    monkeypatch.setattr(search_router.embedding_service, "embed_query", fake_embed)
    monkeypatch.setattr(search_router.retriever, "search", fake_search)

    response = Response()
    result = await search_router.search(SearchRequest(query="marina"), response, session=None)

    timing = response.headers["server-timing"]
    assert "embed;dur=" in timing
    assert "retrieve;dur=" in timing
    assert "total;dur=" in timing
    assert result.query_type == "general"


def test_chat_route_sets_server_timing_header(monkeypatch):
    async def fake_retrieve(*args, **kwargs):
        return [], "general", {}, None

    async def fake_history(session, conversation_id):
        return conversation_id or "abc", []

    async def fake_persist(*args, **kwargs):
        return None

    async def fake_no_evidence(session, message):
        return "No evidence available."

    monkeypatch.setattr(rag_service, "_retrieve", fake_retrieve)
    monkeypatch.setattr(rag_service, "_history", fake_history)
    monkeypatch.setattr(rag_service, "_persist", fake_persist)
    monkeypatch.setattr(rag, "no_evidence_answer", fake_no_evidence)

    app.dependency_overrides[get_db] = lambda: None
    try:
        with TestClient(app) as http:
            resp = http.post("/api/v1/chat", json={"message": "hello"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    timing = resp.headers.get("server-timing", "")
    assert "retrieve;dur=" in timing
    assert "history;dur=" in timing
    assert "no_evidence;dur=" in timing
    assert "total;dur=" in timing


async def test_stream_emits_timing_frame_before_done(monkeypatch):
    async def fake_retrieve(*args, **kwargs):
        return [make_item()], "general", {}, None

    async def fake_history(session, conversation_id):
        return conversation_id or "abc", []

    async def fake_persist(*args, **kwargs):
        return None

    async def fake_astream(messages):
        yield "Marina apartment [1] is available."

    monkeypatch.setattr(rag_service, "_retrieve", fake_retrieve)
    monkeypatch.setattr(rag_service, "_history", fake_history)
    monkeypatch.setattr(rag_service, "_persist", fake_persist)
    monkeypatch.setattr(rag.settings, "llm_api_key", "test-key")
    monkeypatch.setattr(rag.llm_client, "astream", fake_astream)

    frames = []
    async for frame in rag_service.stream(ChatRequest(message="marina?")):
        frames.append(frame)

    events = parse_frames(frames)
    names = [name for name, _ in events]
    assert "timing" in names
    assert "done" in names
    assert names.index("timing") < names.index("done")
    # Unknown SSE events are ignored by the client, so a token stream must
    # still be intact alongside the timing frame.
    assert "token" in names

    timing = next(payload for name, payload in reversed(events) if name == "timing")
    for phase in ("retrieve", "history", "llm_ttfb", "llm_total", "total"):
        assert phase in timing, f"missing phase {phase}: {timing}"
    assert timing["llm_ttfb"] >= 0 and timing["total"] >= timing["llm_ttfb"]
