# Security

This document captures the threat model the project defends against, the
guarantees it does **not** make, and how to deploy it safely behind a
corporate boundary.

## Scope

GenericRagGenerator is a local-first RAG service intended to run either on
a developer workstation or inside a trusted corporate network. It is not
designed to be exposed directly to the public internet without a
hardening reverse proxy in front of it (nginx, Traefik, an enterprise
API gateway, etc.).

## Threat model

### In scope

- **Malicious uploaded content** — PDF, HTML, DOCX, ZIP, source code.
  The loader stack is sandboxed via in-memory parsing, the ZIP extractor
  rejects path traversal, symlinks, absolute paths and drive prefixes,
  enforces per-file (10 MB), total (100 MB) and member-count (5000)
  caps, and skips well-known clutter directories.
- **Credential leaks via commits** — every commit is scanned with
  [`detect-secrets`](https://github.com/Yelp/detect-secrets) against a
  baseline; new high-entropy strings, AWS keys, GitHub tokens, JWTs and
  cloud credentials must be acknowledged explicitly before they land.
- **Common Python sec smells** — [`bandit`](https://github.com/PyCQA/bandit)
  runs on `backend/` in pre-commit and in CI, blocking shell-injection
  patterns, weak crypto, hardcoded passwords, `assert`-as-validation,
  unsafe deserialization, etc.
- **Known dependency CVEs** — [`pip-audit`](https://github.com/pypa/pip-audit)
  runs on every CI build. Findings remain visible even when the build
  is allowed to soft-fail (see *Known limitations* below).
- **Cross-site request abuse** — strict CORS allowlist (no wildcards),
  `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy:
  no-referrer`, `Permissions-Policy` and a tight `Content-Security-
  Policy` are stamped on every response by `SecurityHeadersMiddleware`.
- **Unauthenticated API access in shared deployments** — `API_KEY`
  (constant-time `hmac.compare_digest`) and/or interactive JWT bearer
  (HS256, scoped) gate every state-changing endpoint. `require_admin`
  protects `/api/admin/reset`. Health probes deliberately stay free.
- **Credential stuffing on the login endpoint** —
  `POST /api/auth/login` is rate-limited per IP (5/minute by default)
  via `slowapi`; failed and successful attempts are both audit-logged
  so brute-force patterns surface in SIEM ingestion.
- **Chat-endpoint abuse** — `slowapi` also enforces a per-IP rate
  limit on `/api/chat` (default 30/minute), configurable via
  `RATE_LIMIT_CHAT`.
- **Forensics + correlation** — `RequestIdMiddleware` stamps every
  request with an `X-Request-ID` (mints one when the client omits it,
  echoes it otherwise). `AuditLogger` emits one-line JSON entries on
  `ggrag.audit` for `login.failed`, `login.success`, `admin.reset`
  and `admin.reset.failed` events with `principal`, `client`,
  `request_id` and reason fields so operators can trace a single
  action across the access log and the audit log.

### OWASP API Security Top 10 alignment

| Risk                                                            | Posture                                                                                                   |
|-----------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| API1 – Broken Object Level Authorisation                        | Single-tenant by design; no per-user objects. Scope a deployment behind a reverse proxy for multi-tenant. |
| API2 – Broken Authentication                                    | `hmac.compare_digest` API key + HS256 JWT, login rate-limit, scoped tokens, audit log of every attempt.   |
| API3 – Excessive Data Exposure                                  | Responses serialised via explicit Pydantic schemas; no model-derived fields leak by accident.             |
| API4 – Lack of Resources & Rate Limiting                        | `slowapi` per-IP limits on `/api/chat` + `/api/auth/login`; upload size caps; ZIP member-count cap.       |
| API5 – Broken Function Level Authorisation                      | `require_admin` scope check on destructive endpoints; OpenAPI tags + descriptions are explicit.           |
| API6 – Mass Assignment                                          | Pydantic `BaseModel` defines every accepted field; unknown body fields are rejected by default.           |
| API7 – Security Misconfiguration                                | Strict CSP / XFO DENY / HSTS / Permissions-Policy headers stamped on every response; `/docs` disablable.   |
| API8 – Injection                                                | No SQL; Chroma metadata filters go through typed `MetadataFilter` objects, not raw string interpolation.  |
| API9 – Improper Asset Management                                | OpenAPI versioning via `version: "0.2.0"`; `DOCS_ENABLED` flag hides discovery surfaces in prod.         |
| API10 – Insufficient Logging & Monitoring                       | `RequestIdMiddleware` + structured `AuditLogger` emit JSON events on every security-relevant action.      |

### Out of scope (assumed trusted)

- **Operator and trusted network** — anyone with `API_KEY` is treated as
  a legitimate user. There is no multi-tenant authorisation, no row-
  level RBAC, no audit trail.
- **Ollama and ChromaDB sockets** — communication with the local Ollama
  instance and the embedded ChromaDB happens over loopback. We do not
  attempt to authenticate them.
- **Outbound LLM responses** — the chat model is constrained by the
  system prompt to cite only the supplied excerpts, but a determined
  prompt-injection payload inside an uploaded document could still
  steer the model. Treat assistant output as advisory, not as the basis
  for downstream automation.
- **Data exfiltration via prompt** — embedded documents are returned
  verbatim in answers when relevant; do not ingest sensitive material
  that anyone with access to the chat UI must not see.
- **Public-internet exposure** — putting this service directly on the
  open internet is unsupported. Use a reverse proxy with TLS
  termination, IP allowlisting and request-body size limits.

## Deployment guidance

1. **Always set `API_KEY`** when more than one machine can reach the
   service. Pass it via a secrets manager (Vault, AWS Secrets Manager,
   Kubernetes secrets); never bake it into the image or commit it.
2. **Lock `CORS_ORIGINS`** to the exact hostnames that should reach
   the API. Leave the list empty if the API is consumed only by the
   bundled static UI on the same host.
3. **Run behind a reverse proxy** that enforces:
   - TLS termination + HSTS (the app already emits the header).
   - Request body limits (≤ 25 MB documents, ≤ 50 MB ZIP archives).
   - Upload-endpoint rate limiting (slowapi's decorator cannot wrap the
     `UploadFile` handlers, so this throttle is intentionally pushed to
     the proxy layer).
4. **Run as a non-root user** in production. The provided Dockerfile
   (planned in J.4) sets up a dedicated `app` user; if you build your
   own image, mirror that.
5. **Keep dependencies fresh**. Re-run `pip-audit` weekly. The
   `requirements.txt` is fully pinned, so upgrades are explicit.
6. **Wipe `./data/`** when decommissioning. ChromaDB and the raw upload
   archive live there in cleartext.

## Known limitations / open advisories

`pip-audit` may report findings on dependencies pulled in transitively
by LlamaIndex and FastAPI. We track them but **do not** block CI on
them, because patches frequently require a downstream release first.
Notable open advisories at the time of this hardening pass:

- `pypdf 5.1.0` — multiple CVEs fixed in the 6.x line. Bumping to 6.x
  requires API surface verification across the loader; tracked.
- `pytest 8.3.4` — fixed in 9.x (test-only, not in the runtime tree).
- `starlette 0.41.3` — fixed in 0.49.x; awaiting compatible FastAPI
  release before bumping.
- `setuptools 65.5.0` — bundled with the venv tooling; refreshed by
  rebuilding the virtual environment with the latest pip.

When you upgrade any of these, regenerate the eval and run
`pre-commit run --all-files` to confirm nothing regressed.

## Reporting a vulnerability

If you find a security issue, please open a private report rather than a
public GitHub issue:

- Email: **jakubvonsyrek@gmail.com**
- Include: reproduction steps, affected endpoints, and a suggested fix
  if you have one.

You can expect an acknowledgement within five working days. Coordinated
disclosure timelines are negotiated case by case.
