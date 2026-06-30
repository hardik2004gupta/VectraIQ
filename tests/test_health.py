"""
Tests for admin / health endpoints.

Coverage:
- GET /admin/health — 200 all-ok, 503 degraded, partial degradation
- GET /admin/cache/stats — admin only, response shape
- POST /admin/cache/clear — admin only, clears cache
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    def test_health_all_ok_returns_200(
        self, client: TestClient, mock_all_healthy
    ):
        resp = client.get("/admin/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["postgres"] is True
        assert body["qdrant"] is True
        assert body["openai"] is True

    def test_health_postgres_down_returns_503(
        self, client: TestClient, mock_postgres_down
    ):
        resp = client.get("/admin/health")
        # Phase 4 fix: critical service down → 503
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["postgres"] is False

    def test_health_qdrant_down_returns_503(self, client: TestClient):
        with patch("vectraiq.api.admin._ping_postgres", return_value=True):
            with patch("vectraiq.api.admin._ping_qdrant", return_value=False):
                with patch("vectraiq.api.admin._ping_redis", return_value=True):
                    with patch("vectraiq.api.admin._ping_openai", return_value=True):
                        with patch("vectraiq.api.admin._ping_tavily", return_value=True):
                            resp = client.get("/admin/health")
        assert resp.status_code == 503
        assert resp.json()["qdrant"] is False

    def test_health_redis_down_is_not_critical(self, client: TestClient):
        """Redis is non-critical; its absence should not cause a 503."""
        with patch("vectraiq.api.admin._ping_postgres", return_value=True):
            with patch("vectraiq.api.admin._ping_qdrant", return_value=True):
                with patch("vectraiq.api.admin._ping_redis", return_value=False):
                    with patch("vectraiq.api.admin._ping_openai", return_value=True):
                        with patch("vectraiq.api.admin._ping_tavily", return_value=True):
                            resp = client.get("/admin/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["redis"] is False

    def test_health_response_shape(self, client: TestClient, mock_all_healthy):
        body = client.get("/admin/health").json()
        required_keys = {"status", "postgres", "qdrant", "redis", "openai", "tavily"}
        assert required_keys.issubset(body.keys())

    def test_health_no_auth_required(self, client: TestClient, mock_all_healthy):
        """Health endpoint must be accessible without credentials."""
        resp = client.get("/admin/health")
        assert resp.status_code != 401
        assert resp.status_code != 403


class TestCacheStatsEndpoint:
    def test_cache_stats_requires_admin(self, client: TestClient, user_headers: dict):
        resp = client.get("/admin/cache/stats", headers=user_headers)
        assert resp.status_code == 403

    def test_cache_stats_returns_expected_shape(
        self, client: TestClient, admin_headers: dict
    ):
        with patch("vectraiq.api.admin.query_cache") as mock_cache:
            mock_cache.stats.return_value = {
                "embedding": {"hits": 10, "misses": 2, "sets": 12, "hit_rate": 0.833},
                "rag_answer": {"hits": 5, "misses": 5, "sets": 10, "hit_rate": 0.5},
                "sql_gen": {"hits": 0, "misses": 1, "sets": 1, "hit_rate": 0.0},
                "sql_result": {"hits": 0, "misses": 0, "sets": 0, "hit_rate": 0.0},
                "intent": {"hits": 8, "misses": 2, "sets": 10, "hit_rate": 0.8},
            }
            resp = client.get("/admin/cache/stats", headers=admin_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert "embedding" in body
        assert "rag" in body
        assert "sql_gen" in body
        assert body["embedding"]["hits"] == 10
        assert body["embedding"]["hit_rate"] == pytest.approx(0.833)

    def test_cache_stats_no_auth_returns_403(self, client: TestClient):
        resp = client.get("/admin/cache/stats")
        assert resp.status_code in (401, 403)


class TestCacheClearEndpoint:
    def test_cache_clear_requires_admin(self, client: TestClient, user_headers: dict):
        resp = client.post("/admin/cache/clear", headers=user_headers)
        assert resp.status_code == 403

    def test_cache_clear_admin_success(
        self, client: TestClient, admin_headers: dict
    ):
        with patch("vectraiq.api.admin.query_cache") as mock_cache:
            mock_cache.clear.return_value = ["embedding", "rag_answer"]
            resp = client.post("/admin/cache/clear", headers=admin_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "cleared" in body

    def test_cache_clear_no_auth_returns_403(self, client: TestClient):
        resp = client.post("/admin/cache/clear")
        assert resp.status_code in (401, 403)
