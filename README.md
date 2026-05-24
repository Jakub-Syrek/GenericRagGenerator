# GenericRagGenerator

[![100% LOCAL](https://img.shields.io/badge/100%25-LOCAL-16a34a?style=for-the-badge&logoColor=white)](#)
[![NO CLOUD](https://img.shields.io/badge/NO-CLOUD-DC2626?style=for-the-badge)](#)
[![SELF-HOSTED](https://img.shields.io/badge/SELF--HOSTED-3B82F6?style=for-the-badge&logo=homeassistant&logoColor=white)](#)
[![YOUR DATA STAYS HERE](https://img.shields.io/badge/your%20data-stays%20on%20your%20box-7C3AED?style=for-the-badge&logo=lock&logoColor=white)](#)

[![CI](https://github.com/Jakub-Syrek/GenericRagGenerator/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Jakub-Syrek/GenericRagGenerator/actions/workflows/ci.yml)
[![tests](https://img.shields.io/badge/tests-60%20passed-brightgreen)](https://github.com/Jakub-Syrek/GenericRagGenerator/tree/main/tests)
[![eval](https://img.shields.io/badge/eval-24%2F24-brightgreen)](https://github.com/Jakub-Syrek/GenericRagGenerator/blob/main/eval/sample-result.md)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Ollama](https://img.shields.io/badge/Ollama-local-000000?logo=ollama&logoColor=white)](https://ollama.com/)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.12-FB923C)](https://docs.llamaindex.ai/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-embedded-FACC15)](https://www.trychroma.com/)
[![Ruff](https://img.shields.io/badge/lint-ruff-d7ff64?logo=ruff&logoColor=black)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/types-mypy-2A6DB2)](http://mypy-lang.org/)
[![bandit](https://img.shields.io/badge/security-bandit-FFC107)](https://github.com/PyCQA/bandit)
[![detect-secrets](https://img.shields.io/badge/secrets-detect--secrets-FF5722)](https://github.com/Yelp/detect-secrets)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://pre-commit.com/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![Windows service](https://img.shields.io/badge/Windows%20service-NSSM-0078D4?logo=windows&logoColor=white)](scripts/install-windows-service.ps1)

> **Runs entirely on your own machine.** The LLM (Ollama), the embedding
> model, the vector store (ChromaDB) and the uploaded files all live on
> your host. **No external API calls, no telemetry, no data ever leaves
> your box.** Run it on a laptop, a dev box, an air-gapped corporate
> server — same code, same behaviour.

Local Retrieval-Augmented Generation (RAG) service. Upload documents *or* a
whole repository (code + docs), then chat with a local LLM that answers
strictly from the indexed content and cites the exact file (with line range,
for code).

## What it can ingest

- **Prose docs**: `.pdf`, `.txt`, `.md` / `.markdown`, `.rst`, `.html` /
  `.htm`, `.docx`.
- **Source code** (≈ 30 languages): Python, TypeScript / JavaScript / TSX /
  JSX, Java, Kotlin, Scala, Go, Rust, C / C++ / headers, C#, Ruby, PHP,
  Swift, shells (bash / zsh / sh), PowerShell, SQL, plus common config
  formats (YAML, TOML, JSON, XML, INI, CSS, SCSS).
- **Whole repositories**: drop a `.zip` archive; the safe extractor rejects
  path traversal, symlinks, oversize members, and skips clutter like
  `.git/`, `node_modules/`, `__pycache__/`, `dist/`, `build/`, `target/`,
  `vendor/`, IDE caches.

Each chunk carries `kind` (`code`/`doc`), `language`, optional
`line_start`/`line_end` and `repository_id` metadata. Source chips in the
chat UI render `repo/path/to/file.py:42-101` for code and the plain path
for docs.

## Stack

| Layer             | Choice                                                            |
|-------------------|-------------------------------------------------------------------|
| Backend           | Python 3.11 + FastAPI                                             |
| LLM runtime       | [Ollama](https://ollama.com) (local, OSS)                         |
| Chat model        | `llama3.1:8b` (configurable via `CHAT_MODEL`)                     |
| Embedding model   | `nomic-embed-text` with `search_query:` / `search_document:` prefixes |
| RAG orchestration | [LlamaIndex](https://docs.llamaindex.ai)                          |
| Vector store      | [ChromaDB](https://www.trychroma.com) (embedded, on-disk)         |
| Chunking          | `MarkdownNodeParser` (md) / `CodeChunker` (code) / `SentenceSplitter` (default) |
| Frontend          | Plain HTML + CSS + ES6 (CSP-compliant, no inline scripts)         |
| Security          | bandit + detect-secrets + pip-audit, security headers, slowapi, optional API key |
| CI                | GitHub Actions (ruff + mypy + bandit + pytest + pip-audit)        |

## Prerequisites

1. Python 3.11+
2. Ollama running locally: `ollama serve`
3. Required models pulled once:
   ```powershell
   ollama pull llama3.1:8b
   ollama pull nomic-embed-text
   ```

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
.\run.ps1
```

Then open <http://127.0.0.1:8000>. Upload documents *or* a project ZIP from
the sidebar, then ask questions in the chat pane. The assistant streams the
answer token-by-token and shows citation chips for every chunk it pulled
from the vector store.

## Optional: install as a Windows service

NSSM ([nssm.cc](https://nssm.cc)) wraps the `.venv` uvicorn process as a
proper Windows service with auto-start, log rotation and restart-on-failure.
Two PowerShell helpers under `scripts/` automate it:

```powershell
# 1. Install NSSM once (admin PowerShell):
winget install NSSM.NSSM
# or:  choco install nssm
# or:  drop nssm.exe somewhere on PATH manually

# 2. From the project root, in an *elevated* PowerShell:
.\scripts\install-windows-service.ps1
```

The script registers the service under the name `GenericRagGenerator`,
binds to `127.0.0.1:8000` (default `local` mode), captures stdout/stderr
into rotated logs under `.\logs\service-*.log` (10 MB rotation) and
restarts the process after 5 s on failure.

Two install profiles via `-Mode`:

| Mode      | Bind         | When to use                                            |
|-----------|--------------|--------------------------------------------------------|
| `local`   | `127.0.0.1`  | Single-user / personal box. API reachable only locally. |
| `public`  | `0.0.0.0`    | Shared host / corp deployment. Refuses to install unless `API_KEY` (or `AUTH_PASSWORD` + `JWT_SECRET`) is set in `.env`. |

```powershell
# Local-only (default): API on http://127.0.0.1:8000
.\scripts\install-windows-service.ps1

# Public bind on a custom port (must set auth in .env first)
.\scripts\install-windows-service.ps1 -Mode public -Port 9000

# Public + hide Swagger / Redoc / OpenAPI
.\scripts\install-windows-service.ps1 -Mode public -DisableDocs
```

Operational commands:

```powershell
Get-Service GenericRagGenerator        # status
Restart-Service GenericRagGenerator    # reload after .env / code changes
Stop-Service GenericRagGenerator       # graceful stop (15 s window)
.\scripts\uninstall-windows-service.ps1
```

Notes for production:
- Ollama itself ships as a service via its installer; both can run
  side-by-side on the same box.
- Run the service under a least-privileged local account
  (`nssm set GenericRagGenerator ObjectName .\rag-user <password>`)
  rather than `LocalSystem` when the host is shared.
- Set `API_KEY` in `.env` before installing the service so the public
  surface is gated from the first start.

## Run in Docker (corp-friendly)

```bash
docker compose up -d
docker exec ggrag-ollama ollama pull llama3.1:8b
docker exec ggrag-ollama ollama pull nomic-embed-text
```

The compose stack runs both the app and Ollama with:
- non-root user (`UID 10001`) and no shell in the app image,
- `read_only: true` root filesystem with tmpfs only for `/tmp` and
  `/home/app/.cache`,
- `cap_drop: ALL` and `no-new-privileges: true` on both services,
- a healthcheck on `/api/health`,
- separate named volumes for Chroma data and the Ollama model cache.

See [`SECURITY.md`](SECURITY.md) for the full threat model and corp
deployment guidance.

## REST API

Whatever run mode you pick (`run.ps1`, the Windows service, the Docker
compose stack) the same surface is exposed on the same port — there is
no "service" vs "API" distinction. Interactive OpenAPI docs live at
`/docs` (Swagger UI) and `/redoc`; set `DOCS_ENABLED=false` to hide both
plus `/openapi.json` in production.

| Method | Path                                | Purpose                                                |
|--------|-------------------------------------|--------------------------------------------------------|
| GET    | `/api/health`                       | Service + Ollama reachability (always unauthenticated) |
| POST   | `/api/auth/login`                   | Verify credentials, issue a JWT bearer                 |
| GET    | `/api/auth/whoami`                  | Echo the authenticated principal + scopes              |
| POST   | `/api/admin/reset`                  | Wipe every chunk in the index (admin scope only)       |
| GET    | `/api/documents`                    | List indexed documents                                 |
| POST   | `/api/documents`                    | Upload one document (multipart)                        |
| GET    | `/api/documents/{id}`               | Document detail (kind, language, preview)              |
| GET    | `/api/documents/{id}/chunks`        | List every chunk produced from a document              |
| DELETE | `/api/documents/{id}`               | Remove a document and its chunks                       |
| GET    | `/api/repositories`                 | List indexed repositories                              |
| POST   | `/api/repositories`                 | Upload a project ZIP (multipart)                       |
| GET    | `/api/repositories/{id}`            | Repository detail with per-file ingest list            |
| GET    | `/api/repositories/{id}/files`      | List every file ingested from a repository             |
| DELETE | `/api/repositories/{id}`            | Remove a repository and all its chunks                 |
| GET    | `/api/projects`                     | List indexed multi-source projects                     |
| POST   | `/api/projects`                     | Upload many raw files as one project (multipart)       |
| GET    | `/api/projects/{id}`                | Project detail with per-file ingest list               |
| GET    | `/api/projects/{id}/files`          | List every file ingested into a project                |
| DELETE | `/api/projects/{id}`                | Remove a project and all its chunks                    |
| POST   | `/api/search`                       | Retrieval-only similarity search (no LLM call)         |
| POST   | `/api/query`                        | Synchronous RAG answer (one JSON, non-streaming)       |
| POST   | `/api/chat`                         | Streaming RAG answer (NDJSON)                          |

### Authentication

Two flows, accepted on every protected route:

- **Static `X-API-Key`** — set `API_KEY` in the environment, then send
  `X-API-Key: <secret>` on every request. Compared in constant time
  (`hmac.compare_digest`); good for service-to-service.
- **Interactive JWT bearer** — set `AUTH_PASSWORD` *and* `JWT_SECRET` in
  the environment, then:
  ```bash
  TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"…"}' | jq -r .access_token)
  curl http://127.0.0.1:8000/api/auth/whoami -H "Authorization: Bearer $TOKEN"
  ```
  Bearer tokens are HS256-signed, carry a `sub` + `scopes` claim, and
  expire after `JWT_EXPIRES_MINUTES` (default 60). The token from
  `/api/auth/login` carries the `admin` scope, required by
  `/api/admin/reset`.

When neither `API_KEY` nor `JWT_SECRET` is configured, authentication
is disabled and every endpoint runs as an `anonymous` principal — fine
for local dev, never use in production.

### Resource payloads

```json
POST /api/projects        // multipart
files=<file>&files=<file>&name=<string>
```

```json
POST /api/query
{
  "messages": [{"role": "user", "content": "How does slugify work?"}],
  "document_ids":   ["..."],
  "repository_ids": ["..."],
  "project_ids":    ["..."]
}
// returns { "answer": "...", "sources": [...] }
```

```json
POST /api/search
{
  "query": "how does slugify work?",
  "top_k": 10,
  "document_ids": ["..."],
  "repository_ids": ["..."],
  "kinds": ["code", "doc"]
}
// returns { "query": "...", "results": [...], "total": N }
```

```json
POST /api/admin/reset    // Authorization: Bearer <admin-token>
// returns { "chunks_removed": N }
```

## Architecture

The codebase is intentionally SOLID-shaped and uses a handful of named
design patterns where they buy something concrete:

| Pattern                       | Where                                              |
|-------------------------------|----------------------------------------------------|
| **Strategy + Registry**       | `services/chunking.py` — `Chunker` protocol, `SentenceChunker`/`MarkdownChunker`/`CodeChunker`, `ChunkerRegistry` for `(kind, language) -> Chunker` resolution |
| **Repository**                | `services/index_catalog.py` — `IndexCatalog` is the only class that imports `chromadb`; returns frozen domain dataclasses |
| **Facade**                    | `services/rag_service.py` — `RagService` delegates to loader / chunker registry / catalog / LLM client; routes never see the pieces |
| **Adapter**                   | `_PrefixedOllamaEmbedding` adapts `OllamaEmbedding` to nomic's asymmetric query/document prefixes |
| **Specification / Value Object** | `security/auth.py` — `Principal` is the immutable identity for one request; `has_scope("admin")` reads as a specification |
| **Chain of Responsibility**   | `require_credentials` tries API key first, then Bearer JWT, before failing closed |
| **Decorator (middleware)**    | `SecurityHeadersMiddleware`, `SlowAPIMiddleware`, `CORSMiddleware` wrap every request without leaking into handler code |
| **Dependency Injection**      | Pervasive via FastAPI `Depends`; cached singletons via `functools.lru_cache` providers in `dependencies.py` |

The chat stream emits one JSON event per line:
- `{"type": "sources", "sources": [...]}` once at the top, where each
  source carries `document_id`, `filename`, `kind`, `language`,
  `repository_name` (when ingested via a repo), and `line_start` /
  `line_end` for code chunks.
- `{"type": "delta", "content": "..."}` per generated token batch.
- `{"type": "done"}` on success, or `{"type": "error", "message": "..."}`
  if Ollama or Chroma fail mid-stream.

## Project layout

```
backend/app/
  api/             HTTP routes (auth, admin, documents, repository,
                   projects, search, query, chat, health)
  services/        RagService (facade), chunking (Strategy/Registry),
                   index_catalog (Repository), document_loader
  models/          Pydantic schemas
  security/        Headers middleware, API-key + JWT auth, rate limiter
  config.py        Settings (env-driven)
  dependencies.py  FastAPI DI providers (cached singletons via lru_cache)
  main.py          FastAPI entry, middleware wiring, static frontend mount
frontend/          Static UI (documents + repository forms, source chips)
eval/              RAG quality eval (corpus + runner + sample report)
  sample_repo/     Synthetic mini_parser fixture (code + HTML + Markdown)
tests/             Pytest suite (unit + API integration with TestClient)
data/              Runtime (uploads + Chroma persistence) - gitignored
logs/              Windows-service stdout / stderr (NSSM-managed) - gitignored
scripts/           PowerShell helpers (install / uninstall Windows service)
Dockerfile         Multi-stage, non-root, healthcheck
docker-compose.yml App + Ollama + hardening
SECURITY.md        Threat model and deployment guidance
```

## Quality eval

```powershell
.\.venv\Scripts\python.exe -m eval.run_eval
```

Downloads four Wikipedia article intros (RAG, Vector database, Word
embedding, Photosynthesis), bundles `eval/sample_repo/` into a ZIP, pushes
both corpora through the live API, runs 24 canned questions over
`/api/chat`, and scores each answer on four axes:

- **`retrieval_top1_precision`** — top-1 source matches the expected file.
- **`answer_substring_match`** — answer contains any of the expected
  substrings (case-insensitive).
- **`kind_precision`** — for code/doc-tagged questions, top-1 source is of
  the expected kind.
- **`ooc_refusal_rate`** — out-of-corpus probes correctly refuse.

Results land under `eval/results/` (timestamped JSON + Markdown). A
checked-in baseline lives at [`eval/sample-result.md`](eval/sample-result.md).

Latest local run on `llama3.1:8b` + `nomic-embed-text`:

- **24/24** composite pass
- retrieval_top1 1.0, answer_match 1.0, kind 1.0, ooc_refusal 1.0
- average latency ~0.6 s per turn warm

## Development workflow

```powershell
# One-time setup
pip install -r requirements.txt
pre-commit install

# Per change
pre-commit run --all-files
pytest
```

`pre-commit` runs:

- whitespace / EOL / large-file hygiene,
- `ruff` (lint + format),
- `mypy` on `backend/`,
- `bandit` (Python security smells),
- `detect-secrets` against `.secrets.baseline`.

CI on push and PR runs the same pre-commit suite plus `pip-audit`
(advisories logged but non-blocking; see `SECURITY.md`).

Integration-style end-to-end checks against a live Ollama are kept out of
CI and live in `smoke_test.py` plus the `eval/` package.

## Configuration knobs (env)

| Variable                    | Default                       | Purpose                                                     |
|-----------------------------|-------------------------------|-------------------------------------------------------------|
| `OLLAMA_HOST`               | `http://localhost:11434`      | Where to reach Ollama.                                      |
| `CHAT_MODEL`                | `llama3.1:8b`                 | Chat completion model.                                      |
| `EMBEDDING_MODEL`           | `nomic-embed-text`            | Embedding model.                                            |
| `EMBEDDING_QUERY_PREFIX`    | `"search_query: "`            | Prefix prepended to query embeddings (nomic asymmetric).    |
| `EMBEDDING_DOCUMENT_PREFIX` | `"search_document: "`         | Prefix prepended to document embeddings.                    |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `800` / `120`              | Sentence-splitter window in characters.                     |
| `TOP_K`                     | `60`                          | Retriever top-k. Tuned for small local corpora; drop to 4–8 on large indexes. |
| `API_KEY`                   | *(unset)*                     | When set, gates `/api/documents`, `/api/repositories`, `/api/chat` behind `X-API-Key`. |
| `CORS_ORIGINS`              | `["http://localhost:8000", ...]` | Strict allowlist for browsers.                          |
| `RATE_LIMIT_CHAT`           | `30/minute`                   | Per-IP slowapi limit on `/api/chat`.                        |
| `RATE_LIMIT_UPLOADS`        | `10/minute`                   | Documented for reverse-proxy use (slowapi can't wrap `UploadFile`). |
| `AUTH_USERNAME`             | `admin`                       | Username accepted by `POST /api/auth/login`.                |
| `AUTH_PASSWORD`             | *(unset)*                     | Password accepted by login. Required to enable the bearer flow. |
| `JWT_SECRET`                | *(unset)*                     | HS256 signing secret for issued JWT bearers. Required to enable login. |
| `JWT_EXPIRES_MINUTES`       | `60`                          | Lifetime of issued bearer tokens.                           |
| `DOCS_ENABLED`              | `true`                        | Set to `false` to hide `/docs`, `/redoc` and `/openapi.json` in prod. |

## Security

A full threat model, in-scope / out-of-scope guarantees, deployment
guidance and the open dependency advisories live in
[`SECURITY.md`](SECURITY.md). In short:

- Local-first / corp-network target; not for direct public-internet
  exposure without a reverse proxy.
- Bandit + detect-secrets + pip-audit wired into pre-commit / CI.
- Hardened response headers (CSP, XFO DENY, HSTS, Referrer-Policy,
  Permissions-Policy), strict CORS, optional API key, per-IP rate
  limiting.
- ZIP ingest enforces path-traversal / symlink / size caps with named
  domain errors mapped to specific HTTP statuses.

## Commit and style conventions

- English only across code, comments, commits, identifiers.
- Public functions document `@param` / `@returns` (JSDoc-style docstrings).
- SOLID + DI: dependencies are injected via FastAPI `Depends` and
  constructor arguments, never module globals.
- Functions stay around the 30-line ceiling; pylint statement / branch
  limits are enforced by ruff.
- Errors are translated at every external boundary into explicit domain
  exceptions (`EmbeddingError`, `ChatGenerationError`, `VectorStoreError`,
  `StorageError`, `UnsafeArchiveError`, `RepositoryError`,
  `EmptyDocumentError`, `UnsupportedFormatError`).
- Commits are atomic and pushed immediately; CI must stay green on `main`.
