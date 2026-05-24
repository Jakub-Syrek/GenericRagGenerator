"""Unit tests for the security middleware and API-key gating."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_rag_service
from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Plain TestClient with no service overrides (health endpoint is enough)."""
    return TestClient(app)


def test_security_headers_are_stamped(client: TestClient) -> None:
    """Every response carries the hardened header set."""
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "Strict-Transport-Security" in response.headers
    assert "Content-Security-Policy" in response.headers
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_api_key_required_when_configured(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """Setting API_KEY forces /api/documents to require the matching header."""
    monkeypatch.setenv("API_KEY", "shibboleth")
    get_settings.cache_clear()
    try:

        class _Stub:
            def list_documents(self):
                return []

        app.dependency_overrides[get_rag_service] = lambda: _Stub()
        try:
            unauthorised = client.get("/api/documents")
            assert unauthorised.status_code == 401
            authorised = client.get("/api/documents", headers={"X-API-Key": "shibboleth"})
            assert authorised.status_code == 200
            wrong = client.get("/api/documents", headers={"X-API-Key": "nope"})
            assert wrong.status_code == 401
        finally:
            app.dependency_overrides.pop(get_rag_service, None)
    finally:
        monkeypatch.delenv("API_KEY", raising=False)
        get_settings.cache_clear()


def test_api_key_skipped_when_unset(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """When API_KEY is unset, requests without the header pass through."""
    monkeypatch.delenv("API_KEY", raising=False)
    get_settings.cache_clear()

    class _Stub:
        def list_documents(self):
            return []

    app.dependency_overrides[get_rag_service] = lambda: _Stub()
    try:
        response = client.get("/api/documents")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.pop(get_rag_service, None)


def test_health_never_requires_api_key(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """Health probes are usable by load balancers even when API_KEY is set."""
    monkeypatch.setenv("API_KEY", "shibboleth")
    get_settings.cache_clear()
    try:
        response = client.get("/api/health")
        assert response.status_code == 200
    finally:
        monkeypatch.delenv("API_KEY", raising=False)
        get_settings.cache_clear()


def test_request_id_is_echoed_when_supplied(client: TestClient) -> None:
    """`X-Request-ID` supplied by the client is echoed back unchanged."""
    response = client.get("/api/health", headers={"X-Request-ID": "trace-42"})
    assert response.headers["X-Request-ID"] == "trace-42"


def test_request_id_is_minted_when_missing(client: TestClient) -> None:
    """Missing `X-Request-ID` triggers a freshly minted correlation id."""
    response = client.get("/api/health")
    assert response.headers["X-Request-ID"]
    assert len(response.headers["X-Request-ID"]) >= 16
