"""Tests for the JWT login flow and the admin reset endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_rag_service
from app.main import app


class _AdminFakeService:
    """Tiny stub exposing only what /api/admin/reset and /api/auth/whoami need."""

    def __init__(self) -> None:
        self.wipe_calls: int = 0

    def wipe(self) -> int:
        """Pretend to wipe a known number of chunks."""
        self.wipe_calls += 1
        return 42

    def list_documents(self) -> list:
        """Stub for routes that share the dependency override."""
        return []


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable the bearer flow with a known password + secret."""
    monkeypatch.setenv("AUTH_PASSWORD", "letmein")
    monkeypatch.setenv("JWT_SECRET", "test-secret-xyz")
    monkeypatch.setenv("JWT_EXPIRES_MINUTES", "5")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("JWT_EXPIRES_MINUTES", raising=False)
    get_settings.cache_clear()


@pytest.fixture
def client(auth_env: None) -> TestClient:
    """Fresh `TestClient` after the env mutations take effect."""
    _ = auth_env
    stub = _AdminFakeService()
    app.dependency_overrides[get_rag_service] = lambda: stub
    yield TestClient(app)
    app.dependency_overrides.pop(get_rag_service, None)


def test_login_disabled_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without AUTH_PASSWORD / JWT_SECRET the login endpoint refuses."""
    monkeypatch.delenv("AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    get_settings.cache_clear()
    response = TestClient(app).post(
        "/api/auth/login",
        json={"username": "admin", "password": "anything"},  # pragma: allowlist secret
    )
    assert response.status_code == 503


def test_login_rejects_bad_credentials(client: TestClient) -> None:
    """Bad password yields 401."""
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong"},  # pragma: allowlist secret
    )
    assert response.status_code == 401


def test_login_issues_bearer_with_admin_scope(client: TestClient) -> None:
    """Correct credentials yield a bearer token carrying the admin scope."""
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "letmein"},  # pragma: allowlist secret
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert "admin" in body["scopes"]
    assert body["expires_in"] == 5 * 60


def test_whoami_returns_principal_for_bearer(client: TestClient) -> None:
    """The whoami endpoint echoes the JWT subject + method."""
    token = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "letmein"},  # pragma: allowlist secret
    ).json()["access_token"]
    response = client.get("/api/auth/whoami", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "admin"
    assert body["method"] == "jwt"
    assert body["scopes"] == ["admin"]


def test_admin_reset_requires_bearer(client: TestClient) -> None:
    """Without credentials the admin reset is rejected with 401."""
    response = client.post("/api/admin/reset")
    assert response.status_code == 401


def test_admin_reset_invokes_wipe_when_authenticated(client: TestClient) -> None:
    """A valid bearer with admin scope wipes the index."""
    token = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "letmein"},  # pragma: allowlist secret
    ).json()["access_token"]
    response = client.post("/api/admin/reset", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["chunks_removed"] == 42
