"""Per-IP rate limiting via `slowapi`."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address


def build_limiter() -> Limiter:
    """Return a shared `slowapi.Limiter` keyed on the client IP.

    @returns Limiter instance ready to be attached to the FastAPI app.
    """
    return Limiter(key_func=get_remote_address)


limiter: Limiter = build_limiter()
