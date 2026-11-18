"""API contract, validation, auth and header tests (no live DB required)."""

from fastapi.testclient import TestClient

from app.main import app


def client():
    # lifespan logs a DB init failure locally, but the app still starts so the
    # validation/auth/header contract can be exercised without Postgres.
    return TestClient(app)


def test_root_and_openapi():
    with client() as http:
        body = http.get("/").json()
        assert body["docs"] == "/docs"
        assert http.get("/openapi.json").status_code == 200


def test_health_returns_structured_payload():
    with client() as http:
        response = http.get("/health")
        # With a live DB this is 200/ok; without one it must be 503/degraded so
        # a platform health check actually detects the broken dependency.
        assert response.status_code in {200, 503}
        body = response.json()
        assert body["status"] in {"ok", "degraded"}
        assert body["database"] in {"connected", "unavailable"}
        assert "indexed_chunks" in body
        if response.status_code == 503:
            assert body["status"] == "degraded"


def test_health_supports_head_for_uptime_monitors():
    with client() as http:
        response = http.head("/health")
        assert response.status_code in {200, 503}
        assert response.headers.get("allow", "").find("GET") >= 0 or response.status_code == 200


def test_chat_rejects_empty_message():
    with client() as http:
        response = http.post("/api/v1/chat", json={"message": ""})
        assert response.status_code == 422


def test_chat_rejects_unknown_source_filter():
    with client() as http:
        response = http.post(
            "/api/v1/chat", json={"message": "hello", "source_filter": "random"}
        )
        assert response.status_code == 422


def test_chat_rejects_impossible_price_range():
    with client() as http:
        response = http.post(
            "/api/v1/chat",
            json={"message": "hello", "filters": {"min_price": 200, "max_price": 100}},
        )
        assert response.status_code == 422


def test_admin_ingest_requires_key():
    with client() as http:
        assert http.post("/api/v1/admin/ingest", json={}).status_code == 401
        assert (
            http.post(
                "/api/v1/admin/ingest",
                json={},
                headers={"X-Admin-Key": "wrong-key"},
            ).status_code
            == 401
        )


def test_security_headers_present():
    with client() as http:
        response = http.get("/health")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert "referrer-policy" in response.headers


def test_cors_allows_configured_origin():
    with client() as http:
        response = http.options(
            "/api/v1/chat",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_access_gate_when_code_configured(monkeypatch):
    from app.deps import settings as deps_settings

    monkeypatch.setattr(deps_settings, "app_access_code", "secret-code")
    with client() as http:
        assert http.get("/api/v1/access").json()["access_required"] is True
        assert http.post("/api/v1/chat", json={"message": "hi"}).status_code == 401
        ok = http.post(
            "/api/v1/chat",
            json={"message": "hi"},
            headers={"X-Access-Code": "secret-code"},
        )
        # 200 (retrieval path) or 503 (no DB) — both prove the dependency passed.
        assert ok.status_code in {200, 503}


def test_unknown_endpoint_returns_404():
    with client() as http:
        assert http.get("/api/v1/does-not-exist").status_code == 404
