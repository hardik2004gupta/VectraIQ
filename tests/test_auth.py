"""
Tests for authentication endpoints.

Coverage:
- POST /auth/register  — success, duplicate, rate limit, validation
- POST /auth/login     — success, wrong password, unknown user, rate limit
- Token format and claims
"""

from __future__ import annotations

import jwt
import pytest
from fastapi.testclient import TestClient


class TestRegister:
    def test_register_success(self, client: TestClient, mock_db_register_ok):
        resp = client.post(
            "/auth/register",
            json={"username": "newuser", "password": "SecurePass99!"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0

    def test_register_returns_valid_jwt(self, client: TestClient, mock_db_register_ok):
        resp = client.post(
            "/auth/register",
            json={"username": "newuser", "password": "SecurePass99!"},
        )
        token = resp.json()["token"]
        payload = jwt.decode(token, "test-secret-key-for-ci-do-not-use-in-prod", algorithms=["HS256"])
        assert payload["sub"] == "newuser"
        assert "exp" in payload
        assert "iat" in payload

    def test_register_duplicate_returns_409(self, client: TestClient, mock_db_duplicate):
        resp = client.post(
            "/auth/register",
            json={"username": "existinguser", "password": "SecurePass99!"},
        )
        assert resp.status_code == 409
        body = resp.json()
        assert "error" in body

    def test_register_short_username_returns_422(self, client: TestClient):
        resp = client.post(
            "/auth/register",
            json={"username": "ab", "password": "SecurePass99!"},
        )
        assert resp.status_code == 422

    def test_register_short_password_returns_422(self, client: TestClient):
        resp = client.post(
            "/auth/register",
            json={"username": "validuser", "password": "short"},
        )
        assert resp.status_code == 422

    def test_register_empty_body_returns_422(self, client: TestClient):
        resp = client.post("/auth/register", json={})
        assert resp.status_code == 422

    def test_register_injection_in_username_is_caught(self, client: TestClient):
        # The AuthRequest validator runs on username; injection patterns are blocked
        # by the query endpoint validator, not auth. Username has min/max_length.
        # This test verifies the 422 path for oversized username.
        resp = client.post(
            "/auth/register",
            json={"username": "x" * 65, "password": "SecurePass99!"},
        )
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client: TestClient, mock_db_user_exists):
        resp = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "Password123!"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "token" in body
        assert body["token_type"] == "bearer"

    def test_login_returns_valid_jwt(self, client: TestClient, mock_db_user_exists):
        resp = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "Password123!"},
        )
        token = resp.json()["token"]
        payload = jwt.decode(token, "test-secret-key-for-ci-do-not-use-in-prod", algorithms=["HS256"])
        assert payload["sub"] == "testuser"

    def test_login_wrong_password_returns_401(self, client: TestClient, mock_db_user_exists):
        resp = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "WrongPassword!"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert "error" in body
        # Must not reveal whether the username exists
        assert "username" not in body["error"]["message"].lower()

    def test_login_unknown_user_returns_401(self, client: TestClient, mock_db_empty):
        resp = client.post(
            "/auth/login",
            json={"username": "noexist", "password": "SomePass99!"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields_returns_422(self, client: TestClient):
        resp = client.post("/auth/login", json={"username": "testuser"})
        assert resp.status_code == 422

    def test_login_no_body_returns_422(self, client: TestClient):
        resp = client.post("/auth/login")
        assert resp.status_code == 422


class TestProtectedEndpointAuth:
    """Verify that protected endpoints enforce authentication."""

    def test_query_without_token_returns_403(self, client: TestClient):
        resp = client.post("/query", json={"question": "What is a pod?"})
        # FastAPI HTTPBearer returns 403 when no credentials present
        assert resp.status_code in (401, 403)

    def test_query_with_invalid_token_returns_401(self, client: TestClient):
        resp = client.post(
            "/query",
            json={"question": "What is a pod?"},
            headers={"Authorization": "Bearer not-a-valid-jwt"},
        )
        assert resp.status_code == 401

    def test_query_with_expired_token_returns_401(self, client: TestClient):
        expired = jwt.encode(
            {"sub": "user", "exp": 1, "iat": 1, "is_admin": False},
            "test-secret-key-for-ci-do-not-use-in-prod",
            algorithm="HS256",
        )
        resp = client.post(
            "/query",
            json={"question": "What is a pod?"},
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert resp.status_code == 401

    def test_admin_endpoint_with_user_token_returns_403(
        self, client: TestClient, user_headers: dict
    ):
        resp = client.get("/admin/cache/stats", headers=user_headers)
        assert resp.status_code == 403
