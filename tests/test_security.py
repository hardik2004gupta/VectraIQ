"""
Tests for security utilities — JWT helpers, password hashing, config validation.

These tests do not hit external services.
"""

from __future__ import annotations

import datetime
import time

import jwt
import pytest

from vectraiq.middleware.auth import (
    create_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        h = hash_password("MyPassword1!")
        assert h != "MyPassword1!"

    def test_valid_password_verifies(self):
        pw = "CorrectPassword99!"
        h = hash_password(pw)
        assert verify_password(pw, h) is True

    def test_wrong_password_fails(self):
        h = hash_password("CorrectPassword99!")
        assert verify_password("WrongPassword99!", h) is False

    def test_different_hashes_for_same_password(self):
        pw = "SamePassword1!"
        h1 = hash_password(pw)
        h2 = hash_password(pw)
        # bcrypt uses random salt each time
        assert h1 != h2
        # But both verify correctly
        assert verify_password(pw, h1) is True
        assert verify_password(pw, h2) is True

    def test_empty_string_hashes(self):
        """Ensure the hasher doesn't crash on empty string (auth layer blocks this upstream)."""
        h = hash_password("")
        assert verify_password("", h) is True
        assert verify_password("x", h) is False


class TestJWTCreation:
    SECRET = "test-secret-key-for-ci-do-not-use-in-prod"

    def test_token_decodes_correctly(self):
        token = create_access_token("alice")
        payload = jwt.decode(token, self.SECRET, algorithms=["HS256"])
        assert payload["sub"] == "alice"
        assert payload["is_admin"] is False

    def test_admin_flag_propagates(self):
        token = create_access_token("admin", is_admin=True)
        payload = jwt.decode(token, self.SECRET, algorithms=["HS256"])
        assert payload["is_admin"] is True

    def test_token_has_exp_and_iat(self):
        token = create_access_token("user")
        payload = jwt.decode(token, self.SECRET, algorithms=["HS256"])
        assert "exp" in payload
        assert "iat" in payload
        assert payload["exp"] > payload["iat"]

    def test_custom_expiry(self):
        token = create_access_token("user", expires_delta_seconds=120)
        payload = jwt.decode(token, self.SECRET, algorithms=["HS256"])
        exp = datetime.datetime.fromtimestamp(payload["exp"], tz=datetime.timezone.utc)
        iat = datetime.datetime.fromtimestamp(payload["iat"], tz=datetime.timezone.utc)
        delta = (exp - iat).total_seconds()
        assert 119 <= delta <= 121  # allow 1s clock drift

    def test_expired_token_raises(self):
        token = create_access_token("user", expires_delta_seconds=1)
        time.sleep(2)
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, self.SECRET, algorithms=["HS256"])

    def test_wrong_secret_raises(self):
        token = create_access_token("user")
        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode(token, "wrong-secret", algorithms=["HS256"])


class TestSettingsValidation:
    """Verify that Settings validators catch bad values."""

    def test_invalid_log_level_raises(self):
        from pydantic import ValidationError
        from vectraiq.config import Settings

        with pytest.raises(ValidationError):
            Settings(log_level="VERBOSE", _env_file=None)

    def test_invalid_storage_backend_raises(self):
        from pydantic import ValidationError
        from vectraiq.config import Settings

        with pytest.raises(ValidationError):
            Settings(storage_backend="gcs", _env_file=None)

    def test_invalid_reranker_backend_raises(self):
        from pydantic import ValidationError
        from vectraiq.config import Settings

        with pytest.raises(ValidationError):
            Settings(reranker_backend="cohere", _env_file=None)

    def test_valid_settings_accepted(self):
        from vectraiq.config import Settings

        s = Settings(
            log_level="DEBUG",
            storage_backend="local",
            reranker_backend="local",
            _env_file=None,
        )
        assert s.log_level == "DEBUG"

    def test_redis_enabled_property(self):
        from vectraiq.config import Settings

        s_no_redis = Settings(upstash_redis_url="", upstash_redis_token="", _env_file=None)
        assert s_no_redis.redis_enabled is False

        s_with_redis = Settings(
            upstash_redis_url="https://example.upstash.io",
            upstash_redis_token="token",
            _env_file=None,
        )
        assert s_with_redis.redis_enabled is True


class TestErrorResponseEnvelope:
    """Verify the global error envelope shape is consistent."""

    def test_all_error_responses_have_envelope(self, client, user_headers):
        """Any 4xx from the API must include the error envelope."""
        from fastapi.testclient import TestClient

        # 422 from validation
        resp = client.post("/query", json={}, headers=user_headers)
        assert resp.status_code == 422
        body = resp.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
        assert "request_id" in body

    def test_401_has_envelope(self, client):
        from fastapi.testclient import TestClient

        resp = client.post(
            "/query",
            json={"question": "What is a pod?"},
            headers={"Authorization": "Bearer invalid"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert "error" in body
