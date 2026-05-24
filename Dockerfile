# syntax=docker/dockerfile:1.7
# Multi-stage build: dependencies isolated from the runtime layer so the
# final image stays small and free of build-time tooling.

FROM python:3.11-slim AS builder

ARG PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ARG APP_UID=10001

RUN groupadd --system --gid ${APP_UID} app \
    && useradd --system --uid ${APP_UID} --gid ${APP_UID} --shell /sbin/nologin \
       --home-dir /home/app --create-home app \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/home/app/.local/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    CHROMA_DIR=/data/chroma \
    UPLOAD_DIR=/data/uploads

WORKDIR /app

COPY --from=builder --chown=app:app /root/.local /home/app/.local
COPY --chown=app:app backend ./backend
COPY --chown=app:app frontend ./frontend

RUN mkdir -p /data/chroma /data/uploads && chown -R app:app /data

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --silent --fail http://127.0.0.1:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--app-dir", "backend"]
