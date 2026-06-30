"""
Shared pytest fixtures for VectraIQ test suite.

Design decisions:
- Uses FastAPI TestClient (synchronous httpx under the hood).
- All external I/O (Postgres, Qdrant, Redis, OpenAI, LangGraph) is mocked via
  unittest.mock so tests run offline with no credentials.
- JWT_SECRET is hardcoded to a test value; tokens created here are valid for
  the duration of a test but won't work against a real server.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── Set test environment BEFORE importing the app ─────────────────────────────
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-ci-do-not-use-in-prod")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")


from vectraiq.main import create_app  # noqa: E402
from vectraiq.middleware.auth import create_access_token  # noqa: E402


# ── App + Client ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    """Create a single app instance for the entire test session."""
    return create_app()


@pytest.fixture(scope="session")
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── Auth tokens ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def user_token() -> str:
    """Valid JWT for a regular (non-admin) user."""
    return create_access_token("testuser", expires_delta_seconds=3600, is_admin=False)


@pytest.fixture(scope="session")
def admin_token() -> str:
    """Valid JWT for an admin user."""
    return create_access_token("adminuser", expires_delta_seconds=3600, is_admin=True)


@pytest.fixture(scope="session")
def user_headers(user_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture(scope="session")
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


# ── Postgres mock ─────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_db_user_exists():
    """Mock psycopg2 so the DB returns a known user row (password: 'Password123!')."""
    from vectraiq.middleware.auth import hash_password
    pw_hash = hash_password("Password123!")

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (pw_hash, False)   # (password_hash, is_admin)
    mock_conn.cursor.return_value = mock_cur

    with patch("vectraiq.api.auth.psycopg2.connect", return_value=mock_conn):
        yield mock_conn


@pytest.fixture()
def mock_db_empty():
    """Mock psycopg2 so the DB returns no user (username not found)."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = None
    mock_conn.cursor.return_value = mock_cur

    with patch("vectraiq.api.auth.psycopg2.connect", return_value=mock_conn):
        yield mock_conn


@pytest.fixture()
def mock_db_register_ok():
    """Mock psycopg2 so INSERT succeeds and returns a new user id."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (42,)   # new user id
    mock_conn.cursor.return_value = mock_cur

    with patch("vectraiq.api.auth.psycopg2.connect", return_value=mock_conn):
        yield mock_conn


@pytest.fixture()
def mock_db_duplicate():
    """Mock psycopg2 so INSERT raises UniqueViolation (duplicate username)."""
    import psycopg2.errors

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.execute.side_effect = psycopg2.errors.UniqueViolation("duplicate key")
    mock_conn.cursor.return_value = mock_cur

    with patch("vectraiq.api.auth.psycopg2.connect", return_value=mock_conn):
        yield mock_conn


# ── LangGraph mock ────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_graph_rag():
    """Mock LangGraph graph.invoke to return a clean RAG result."""
    result: dict[str, Any] = {
        "final_answer": "To restart a crashed pod, run: kubectl delete pod <name>",
        "sources": ["k8s-pods.md"],
        "intent": "rag",
        "confidence": 0.92,
        "cache_hit": False,
        "metadata": {},
    }
    with patch("vectraiq.api.query.graph") as mock_g:
        mock_g.invoke.return_value = result
        yield mock_g


@pytest.fixture()
def mock_graph_sql_pending():
    """Mock LangGraph graph.invoke to return an SQL interrupt."""
    result: dict[str, Any] = {
        "__interrupt__": [
            MagicMock(
                value={
                    "sql": "SELECT COUNT(*) FROM deployments WHERE status = 'failed'",
                    "explanation": "Counts failed deployments",
                }
            )
        ]
    }
    with patch("vectraiq.api.query.graph") as mock_g:
        mock_g.invoke.return_value = result
        yield mock_g


@pytest.fixture()
def mock_graph_sql_result():
    """Mock LangGraph graph.invoke to return a completed SQL result."""
    result: dict[str, Any] = {
        "final_answer": "There are 3 failed deployments.",
        "sources": [],
        "intent": "sql",
        "confidence": 0.88,
        "cache_hit": False,
        "metadata": {},
    }
    with patch("vectraiq.api.query.graph") as mock_g:
        mock_g.invoke.return_value = result
        yield mock_g


# ── Rate limiter passthrough ───────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def bypass_rate_limiter():
    """Always allow rate-limited endpoints in tests."""
    with patch("vectraiq.api.query.is_allowed_user", return_value=(True, 100, 60)):
        with patch("vectraiq.api.auth.is_allowed_ip", return_value=(True, 100, 60)):
            yield


# ── Token budget passthrough ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def bypass_token_budget():
    """Always pass token budget check in tests."""
    with patch("vectraiq.api.query.check_budget", return_value=(True, 99_000)):
        with patch("vectraiq.api.query.consume_budget"):
            yield


# ── Security pipeline passthrough ─────────────────────────────────────────────

@pytest.fixture(autouse=True)
def bypass_security_pipeline():
    """Pass input through the security pipeline unchanged in tests.

    This allows us to test the endpoint logic without needing llm-guard models.
    Override this fixture in specific tests that test the security pipeline itself.
    """
    with patch("vectraiq.api.query.check_input_safe", return_value=(True, "")):
        with patch("vectraiq.api.query.moderate_and_redact", return_value=(True, "{input}", "")):
            yield


# ── Health probe mocks ────────────────────────────────────────────────────────

@pytest.fixture()
def mock_all_healthy():
    """Mock all health probes to return True."""
    with patch("vectraiq.api.admin._ping_postgres", return_value=True):
        with patch("vectraiq.api.admin._ping_qdrant", return_value=True):
            with patch("vectraiq.api.admin._ping_redis", return_value=True):
                with patch("vectraiq.api.admin._ping_openai", return_value=True):
                    with patch("vectraiq.api.admin._ping_tavily", return_value=True):
                        yield


@pytest.fixture()
def mock_postgres_down():
    """Mock health probes with Postgres unavailable."""
    with patch("vectraiq.api.admin._ping_postgres", return_value=False):
        with patch("vectraiq.api.admin._ping_qdrant", return_value=True):
            with patch("vectraiq.api.admin._ping_redis", return_value=True):
                with patch("vectraiq.api.admin._ping_openai", return_value=True):
                    with patch("vectraiq.api.admin._ping_tavily", return_value=True):
                        yield
