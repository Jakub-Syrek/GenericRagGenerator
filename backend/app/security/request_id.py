"""Per-request correlation id (Decorator pattern around each request).

`RequestIdMiddleware` reads `X-Request-ID` from the client (echoes it
back when present) or mints a fresh UUID, exposes it on
`request.state.request_id` so handlers and the audit logger can stamp
their entries, and writes it onto the response. Operators can then
follow one request across the access log, the audit log, and the
client's network trace.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Stamp every request + response with a stable correlation id."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Echo the supplied `X-Request-ID` or mint a fresh one.

        @param request   Incoming ASGI request.
        @param call_next Downstream ASGI handler.
        @returns Response with the correlation id stamped on its headers.
        """
        rid = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = rid
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = rid
        return response
