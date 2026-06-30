"""
JWT authentication middleware.

- hash_password / verify_password  — bcrypt helpers used at registration / login
- create_access_token               — HS256 JWT with configurable TTL
- get_current_user                  — FastAPI dependency (raises AuthenticationError)
- require_admin                     — FastAPI dependency (raises AuthorizationError)

Tokens carry { sub, exp, iat, is_admin } claims.
"""

from __future__ import annotations

import datetime

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from vectraiq.config import settings
from vectraiq.exceptions import AuthenticationError, AuthorizationError, TokenExpiredError

_bearer = HTTPBearer()


class User(BaseModel):
    username: str
    is_admin: bool = False


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


# ── Token helpers ─────────────────────────────────────────────────────────────

def create_access_token(
    username: str,
    expires_delta_seconds: int | None = None,
    is_admin: bool = False,
) -> str:
    if expires_delta_seconds is None:
        expires_delta_seconds = settings.jwt_expiration_minutes * 60
    now = datetime.datetime.now(datetime.UTC)
    expire = now + datetime.timedelta(seconds=expires_delta_seconds)
    payload = {
        "sub": username,
        "exp": expire,
        "iat": now,
        "is_admin": is_admin,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> User:
    """Validate the Bearer JWT and return the authenticated User.

    Raises VectraIQError subclasses (handled by the global exception handler).
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError() from None
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid authentication token") from None

    username = payload.get("sub")
    if not isinstance(username, str) or not username:
        raise AuthenticationError("Token is missing subject claim")

    return User(username=username, is_admin=bool(payload.get("is_admin", False)))


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Extend get_current_user — additionally requires is_admin=True."""
    if not user.is_admin:
        raise AuthorizationError("Admin access required")
    return user
