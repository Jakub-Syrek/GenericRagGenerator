"""Structured-JSON audit log for security-relevant events.

Each event is emitted as one JSON line through the `ggrag.audit` Python
logger so operators can ship it to whatever log sink they prefer
(stdout, file, syslog, journald, OpenTelemetry collector). The
`AuditLogger` is the only producer the application code interacts with;
everything else (filters, formatters, sinks) plugs in via standard
`logging` configuration.

Patterns:

- **Facade** — a single class hides the JSON-serialisation detail from
  every caller.
- **Strategy via logging** — the underlying `logging.Logger` is a
  pluggable Strategy: users can swap handlers without touching the
  application.
"""

from __future__ import annotations

import json
import logging
from typing import Any

LOGGER_NAME = "ggrag.audit"
_LOGGER = logging.getLogger(LOGGER_NAME)


class AuditLogger:
    """Emit one structured JSON line per security event."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Configure the backing Python logger.

        @param logger Optional override (mostly for tests); defaults to the
                      package-level `ggrag.audit` logger so handlers attached
                      to it are picked up automatically.
        """
        self._log = logger or _LOGGER

    def event(self, event: str, **fields: Any) -> None:
        """Record a single security event.

        @param event  Short event identifier (e.g. `login.failed`).
        @param fields Arbitrary supporting key/value pairs (request_id, ip,
                      username, reason, ...). Values are coerced to strings
                      via `default=str` so dataclasses / datetimes survive.
        """
        self._log.info(json.dumps({"event": event, **fields}, default=str))


audit = AuditLogger()
