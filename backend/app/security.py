"""Security middleware, headers and the optional API-key dependency.

Hardens the app for corp-style deployments:

- `SecurityHeadersMiddleware` stamps every response with `X-Content-Type-
  Options`, `X-Frame-Options`, `Referrer-Policy`, `Strict-Transport-
  Security` and a tight CSP that matches the bundled static frontend.
- `require_api_key` is a FastAPI dependency that gates protected routers
  when `API_KEY` is set in the environment; when unset (local dev) it is
  a no-op.
- `build_limiter` returns a shared `slowapi.Limiter`, keyed on the
  client IP, ready to be applied per endpoint via `@limiter.limit(...)`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, Header, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import Settings, get_settings

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Stamp every response with the configured security headers."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Run the downstream handler and add security headers to the response.

        @param request   Incoming ASGI request.
        @param call_next Downstream ASGI handler.
        @returns Response with hardened headers.
        """
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


def require_api_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """FastAPI dependency that enforces a static API key when one is configured.

    Health probes deliberately skip this dependency. When `API_KEY` is unset
    (typical local-dev case) the check is a no-op so the UI works without
    additional headers.

    @param x_api_key Value of the `X-API-Key` header (optional).
    @param settings  Application settings (injected via DI).
    @raises HTTPException 401 when an API key is configured and the header
            is missing or does not match.
    """
    configured = settings.api_key.get_secret_value() if settings.api_key else None
    if not configured:
        return
    if x_api_key is None or x_api_key != configured:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key.")


def build_limiter() -> Limiter:
    """Return a shared `slowapi.Limiter` keyed on the client IP.

    @returns Limiter instance ready to be attached to the FastAPI app.
    """
    return Limiter(key_func=get_remote_address)


limiter: Limiter = build_limiter()
