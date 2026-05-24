"""Security primitives: headers, auth, rate limiting.

This package re-exports the public surface so callers can keep doing
`from app.security import SecurityHeadersMiddleware, limiter,
require_api_key` after the v1 layout was split into focused modules.
"""

from .auth import (
    CredentialChecker,
    Principal,
    TokenIssuer,
    TokenVerifier,
    require_admin,
    require_api_key,
    require_credentials,
)
from .headers import SECURITY_HEADERS, SecurityHeadersMiddleware
from .rate_limit import build_limiter, limiter

__all__ = [
    "SECURITY_HEADERS",
    "CredentialChecker",
    "Principal",
    "SecurityHeadersMiddleware",
    "TokenIssuer",
    "TokenVerifier",
    "build_limiter",
    "limiter",
    "require_admin",
    "require_api_key",
    "require_credentials",
]
