"""JWT checking (PROVIDED -- read it, do not modify; Kelly reviews it in task K3).

Think of a JWT as a passport. The Auth service issues it; every other service only checks
that it is genuine. A token is three base64 parts: header.payload.signature. We use the
HS256 algorithm: the signature is an HMAC of header+payload with a secret shared by all
services (environment variable JWT_SECRET).

The payload (the "claims") that we expect:
    sub   the user's id (a UUID string)          -> who is calling
    role  exams_officer | examiner | moderator | hod
    exp   expiry time (Unix seconds)             -> checked automatically by the library

Two things you will use in the path operations:

    user: User = Depends(current_user)                         # any logged-in user
    user: User = Depends(require_roles("exams_officer"))       # only these roles

* no / unreadable / expired / wrongly signed token  -> 401 Unauthorized
* valid token but the role is not allowed           -> 403 Forbidden
"""
import os
from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me-please-0123456789")
JWT_ALGORITHM = "HS256"
ROLES = ("exams_officer", "examiner", "moderator", "hod")

bearer_scheme = HTTPBearer(auto_error=False)     # we raise our own 401 (see below)


@dataclass(frozen=True)
class User:
    """The caller, as read from a verified token."""

    id: str
    role: str
    token: str          # the raw token, so that a service can forward it to another service


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, message, headers={"WWW-Authenticate": "Bearer"})


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> User:
    """Dependency: the verified caller, or 401."""
    if credentials is None:
        raise _unauthorized("Not authenticated")
    try:
        claims = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM],
                            options={"require": ["sub", "role", "exp"]})
    except jwt.PyJWTError:
        raise _unauthorized("Invalid or expired token") from None
    if claims["role"] not in ROLES:
        raise _unauthorized("Unknown role in token")
    try:
        user_id = str(UUID(str(claims["sub"])))      # user ids are UUIDs everywhere in ScriptChain (canonical form)
    except ValueError:
        raise _unauthorized("Invalid subject in token") from None
    return User(id=user_id, role=claims["role"], token=credentials.credentials)


def require_roles(*allowed: str):
    """Build a dependency that accepts only the given roles (403 otherwise)."""

    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"Role '{user.role}' is not allowed here (allowed: {', '.join(allowed)})")
        return user

    return dependency
