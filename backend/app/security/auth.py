"""Authentication primitives: API key + JWT bearer tokens.

Design patterns at play:

- **Strategy / Policy** — `TokenIssuer` and `TokenVerifier` are small
  policy objects encapsulating the signing algorithm and the secret;
  the rest of the codebase never touches `jwt.encode` directly.
- **Specification / Value Object** — `Principal` is the immutable
  identity established for one request, carrying its `method` and
  `scopes` so downstream handlers can `principal.has_scope("admin")`.
- **Chain of Responsibility** — `require_credentials` first tries the
  static API key, then falls back to the Bearer JWT. Both go through
  constant-time `hmac.compare_digest`.
"""

from __future__ import annotations

import hmac
import time
from dataclasses import dataclass, field
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, status

from ..config import Settings, get_settings


@dataclass(frozen=True)
class Principal:
    """Authenticated identity established for one request."""

    name: str
    method: str
    scopes: tuple[str, ...] = field(default_factory=tuple)

    def has_scope(self, scope: str) -> bool:
        """Check whether this principal carries a given scope.

        @param scope Scope name to test.
        @returns True when present.
        """
        return scope in self.scopes


class TokenIssuer:
    """Signs short-lived JWT bearers (HS256)."""

    def __init__(self, *, secret: str, expires_seconds: int) -> None:
        """Configure the issuer.

        @param secret           HMAC signing secret.
        @param expires_seconds  Lifetime of issued tokens in seconds.
        """
        self._secret = secret
        self._expires_seconds = expires_seconds

    def issue(self, *, subject: str, scopes: tuple[str, ...] = ()) -> tuple[str, int]:
        """Mint a signed bearer for `subject`.

        @param subject Principal name (`sub` claim).
        @param scopes  Authorisation scopes baked into the token.
        @returns Tuple of `(token, expires_in_seconds)`.
        """
        now = int(time.time())
        payload: dict[str, Any] = {
            "sub": subject,
            "iat": now,
            "exp": now + self._expires_seconds,
            "scopes": list(scopes),
        }
        return jwt.encode(payload, self._secret, algorithm="HS256"), self._expires_seconds


class TokenVerifier:
    """Verifies JWT bearer signatures and decodes claims."""

    def __init__(self, *, secret: str) -> None:
        """Configure the verifier.

        @param secret HMAC signing secret (must match issuer's).
        """
        self._secret = secret

    def verify(self, token: str) -> dict[str, Any] | None:
        """Decode + verify a token; return claims when valid, `None` otherwise.

        @param token Raw JWT string.
        @returns Decoded claims dict or `None`.
        """
        try:
            return jwt.decode(token, self._secret, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            return None


class CredentialChecker:
    """Constant-time username + password verifier (Value Object)."""

    def __init__(self, *, username: str, password: str) -> None:
        """Configure the expected credentials.

        @param username Stored username.
        @param password Stored password.
        """
        self._username = username
        self._password = password

    def check(self, *, username: str, password: str) -> bool:
        """Compare supplied credentials in constant time.

        @param username Presented username.
        @param password Presented password.
        @returns True when both match exactly.
        """
        u_ok = hmac.compare_digest(self._username.encode(), username.encode())
        p_ok = hmac.compare_digest(self._password.encode(), password.encode())
        return u_ok and p_ok


def _extract_bearer(authorization: str | None) -> str | None:
    """Pull the token out of an `Authorization: Bearer <token>` header.

    @param authorization Raw header value (or `None`).
    @returns Token string when well-formed, `None` otherwise.
    """
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def require_credentials(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> Principal:
    """FastAPI dependency that accepts either `X-API-Key` or a Bearer JWT.

    When neither `API_KEY` nor `JWT_SECRET` is configured, the dependency
    is a no-op and returns an anonymous principal — convenient for local
    dev. Otherwise the chain tries API key first (cheap, constant-time
    comparison) then Bearer JWT.

    @param x_api_key     Value of the `X-API-Key` header.
    @param authorization Value of the `Authorization` header.
    @param settings      Application settings.
    @returns Authenticated `Principal`.
    @raises HTTPException 401 when credentials are required but missing/invalid.
    """
    api_key_secret = settings.api_key.get_secret_value() if settings.api_key else None
    jwt_secret = settings.jwt_secret.get_secret_value() if settings.jwt_secret else None
    if not api_key_secret and not jwt_secret:
        return Principal(name="anonymous", method="none")
    if api_key_secret and x_api_key and hmac.compare_digest(x_api_key, api_key_secret):
        return Principal(name="apikey", method="api_key", scopes=("admin",))
    if jwt_secret:
        token = _extract_bearer(authorization)
        if token:
            claims = TokenVerifier(secret=jwt_secret).verify(token)
            if claims:
                return Principal(
                    name=str(claims.get("sub", "user")),
                    method="jwt",
                    scopes=tuple(claims.get("scopes") or ()),
                )
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid credentials.")


def require_admin(principal: Principal = Depends(require_credentials)) -> Principal:
    """FastAPI dependency that enforces the `admin` scope on top of auth.

    @param principal Result of `require_credentials`.
    @returns The principal unchanged.
    @raises HTTPException 403 when the principal lacks `admin` scope.
    """
    if not principal.has_scope("admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin scope required.")
    return principal


def require_api_key(_: Principal = Depends(require_credentials)) -> None:
    """Backward-compatible alias of `require_credentials`.

    Existing routers / tests import `require_api_key`; keeping the name
    avoids a churny migration. The underlying check is the new combined
    API-key + JWT verifier.

    @param _ Authenticated principal (discarded; presence is the assertion).
    """
    return None
