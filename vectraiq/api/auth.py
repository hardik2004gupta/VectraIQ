"""
Authentication endpoints.

POST /auth/register  — create a new user account
POST /auth/login     — authenticate and receive a JWT bearer token

Both endpoints are rate-limited per client IP using the sliding-window
rate limiter. Credentials are validated against the users table in
PostgreSQL (psycopg2 / v2 driver).
"""

from __future__ import annotations

import psycopg2
from fastapi import APIRouter, Request, status
from loguru import logger

from vectraiq.config import settings
from vectraiq.exceptions import AuthenticationError, ConflictError, RateLimitError
from vectraiq.middleware.auth import create_access_token, hash_password, verify_password
from vectraiq.middleware.rate_limiter import is_allowed_ip
from vectraiq.models import AuthRequest, TokenResponse

router = APIRouter(tags=["auth"])


def _get_db_conn() -> psycopg2.extensions.connection:
    return psycopg2.connect(settings.database_url)


@router.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    responses={
        409: {"description": "Username already exists"},
        429: {"description": "Registration rate limit exceeded"},
    },
)
async def register(request: Request, body: AuthRequest) -> TokenResponse:
    """Create a new user account and return a JWT bearer token."""
    client_ip = request.client.host if request.client else "unknown"
    allowed, _, _ = is_allowed_ip(
        client_ip,
        "/auth/register",
        limit=settings.auth_register_rate_limit_per_hour,
        window_seconds=3600,
    )
    if not allowed:
        raise RateLimitError("Registration rate limit exceeded. Try again in 1 hour.")

    password_hash = hash_password(body.password)
    conn = _get_db_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
            (body.username, password_hash),
        )
        conn.commit()
        logger.info("User registered | username={}", body.username)
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise ConflictError(f"Username '{body.username}' already exists") from None
    finally:
        cur.close()
        conn.close()

    token = create_access_token(body.username)
    return TokenResponse(
        token=token,
        expires_in=settings.jwt_expiration_minutes * 60,
    )


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT bearer token",
    responses={
        401: {"description": "Invalid credentials"},
        429: {"description": "Login rate limit exceeded"},
    },
)
async def login(request: Request, body: AuthRequest) -> TokenResponse:
    """Validate credentials and return a JWT bearer token."""
    client_ip = request.client.host if request.client else "unknown"
    allowed, _, _ = is_allowed_ip(
        client_ip,
        "/auth/login",
        limit=settings.auth_login_rate_limit_per_min,
        window_seconds=60,
    )
    if not allowed:
        raise RateLimitError("Login rate limit exceeded. Try again in 1 minute.")

    conn = _get_db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT password_hash, is_admin FROM users WHERE username = %s",
        (body.username,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None or not verify_password(body.password, row[0]):
        # Deliberate generic message — don't reveal whether username exists
        raise AuthenticationError("Invalid username or password")

    token = create_access_token(body.username, is_admin=bool(row[1]))
    logger.info("User authenticated | username={}", body.username)
    return TokenResponse(
        token=token,
        expires_in=settings.jwt_expiration_minutes * 60,
    )
