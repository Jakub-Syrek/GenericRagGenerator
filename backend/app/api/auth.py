"""Login + identity endpoints (JWT bearer flow)."""

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, SecretStr

from ..config import Settings, get_settings
from ..security import audit, limiter
from ..security.auth import (
    CredentialChecker,
    Principal,
    TokenIssuer,
    require_credentials,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_LOGIN_RATE_LIMIT = "5/minute"

_log = logging.getLogger("ggrag.auth")


class LoginRequest(BaseModel):
    """Credentials payload for `POST /api/auth/login`."""

    username: str = Field(min_length=1, max_length=128)
    password: SecretStr


class TokenResponse(BaseModel):
    """JWT bearer issuance response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    scopes: list[str]


class WhoamiResponse(BaseModel):
    """Identity / scope echo for `GET /api/auth/whoami`."""

    name: str
    method: str
    scopes: list[str]


@router.post("/login", response_model=TokenResponse)
@limiter.limit(_LOGIN_RATE_LIMIT)
def login(
    request: Request,
    payload: LoginRequest = Body(...),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Verify credentials and issue a short-lived JWT bearer.

    The endpoint is rate-limited per IP (5/minute) to make credential
    stuffing cost-prohibitive. Failed and successful attempts are both
    routed through the audit log so downstream sinks (SIEM / journald)
    can flag suspicious patterns.

    @param request  Incoming HTTP request (used by slowapi + correlation id).
    @param payload  Login credentials.
    @param settings Application settings.
    @returns Signed bearer + expiry.
    @raises HTTPException 503 when auth is disabled, 401 on bad credentials.
    """
    request_id = getattr(request.state, "request_id", None)
    if not settings.auth_password or not settings.jwt_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Login is disabled. Set AUTH_PASSWORD and JWT_SECRET to enable it.",
        )
    checker = CredentialChecker(
        username=settings.auth_username,
        password=settings.auth_password.get_secret_value(),
    )
    if not checker.check(username=payload.username, password=payload.password.get_secret_value()):
        audit.event(
            "login.failed",
            username=payload.username,
            request_id=request_id,
            client=_client_ip(request),
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials.")
    issuer = TokenIssuer(
        secret=settings.jwt_secret.get_secret_value(),
        expires_seconds=settings.jwt_expires_minutes * 60,
    )
    token, expires_in = issuer.issue(subject=payload.username, scopes=("admin",))
    audit.event(
        "login.success",
        username=payload.username,
        request_id=request_id,
        client=_client_ip(request),
    )
    return TokenResponse(access_token=token, expires_in=expires_in, scopes=["admin"])


@router.get("/whoami", response_model=WhoamiResponse)
def whoami(principal: Principal = Depends(require_credentials)) -> WhoamiResponse:
    """Echo the authenticated principal back to the client.

    @param principal Identity established by `require_credentials`.
    @returns Name, auth method and scopes.
    """
    return WhoamiResponse(
        name=principal.name,
        method=principal.method,
        scopes=list(principal.scopes),
    )


def _client_ip(request: Request) -> str | None:
    """Best-effort client IP extraction (logs the literal when no proxy headers).

    @param request Incoming request.
    @returns Resolved client IP or `None`.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
