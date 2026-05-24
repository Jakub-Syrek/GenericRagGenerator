# GenericRagGenerator

[![CI](https://github.com/Jakub-Syrek/GenericRagGenerator/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Jakub-Syrek/GenericRagGenerator/actions/workflows/ci.yml)

Local Retrieval-Augmented Generation (RAG) application. Upload PDF, TXT or
Markdown documents through a browser UI and chat with a local LLM that answers
strictly from the content of those documents.

## Stack

| Layer            | Choice                                                   |
|------------------|----------------------------------------------------------|
| Backend          | Python 3.11 + FastAPI                                    |
| LLM runtime      | [Ollama](https://ollama.com) (local, OSS)                |
| Chat model       | `llama3.1:8b` (configurable via `CHAT_MODEL`)            |
| Embedding model  | `nomic-embed-text` (configurable via `EMBEDDING_MODEL`)  |
| RAG orchestration| [LlamaIndex](https://docs.llamaindex.ai)                 |
| Vector store     | [ChromaDB](https://www.trychroma.com) (embedded, on-disk)|
| Frontend         | Plain HTML + CSS + ES6 (CSP-compliant, no inline scripts)|
| CI               | GitHub Actions (ruff + mypy + pytest)                    |

## Prerequisites

1. Python 3.11+
2. Ollama running locally: `ollama serve`
3. Required models pulled once:
   ```powershell
   ollama pull llama3.1:8b
   ollama pull nomic-embed-text
   ```

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Run

```powershell
.\run.ps1
```

Then open <http://127.0.0.1:8000>. Upload one or more documents from the
sidebar, then ask questions in the chat pane. The assistant streams an answer
token-by-token and shows citation chips for every chunk it pulled from the
vector store.

## API

| Method | Path                  | Purpose                          |
|--------|-----------------------|----------------------------------|
| GET    | `/api/health`         | Service + Ollama reachability    |
| GET    | `/api/documents`      | List indexed documents           |
| POST   | `/api/documents`      | Upload a document (multipart)    |
| DELETE | `/api/documents/{id}` | Remove a document and its chunks |
| POST   | `/api/chat`           | Stream a chat answer (NDJSON)    |

The chat stream emits one JSON event per line:
- `{"type": "sources", "sources": [...]}` once at the top
- `{"type": "delta", "content": "..."}` per generated token batch
- `{"type": "done"}` on success, or `{"type": "error", "message": "..."}`
  if Ollama or Chroma fail mid-stream.

## Project layout

```
backend/app/
  api/           HTTP routes (documents, chat, health)
  services/      RagService (LlamaIndex + Chroma + Ollama) + DocumentLoader
  models/        Pydantic schemas
  config.py      Settings (env-driven)
  dependencies.py FastAPI DI providers
  main.py        FastAPI entry, serves frontend as static
frontend/        Static UI
eval/            RAG quality eval (corpus + runner + sample report)
tests/           Pytest suite (unit + API integration with TestClient)
data/            Runtime (uploads + Chroma persistence) - gitignored
```

## Quality eval

```powershell
.\.venv\Scripts\python.exe -m eval.run_eval
```

Downloads two Wikipedia article intros (RAG, Vector database), ingests them
through the live API, runs canned questions over `/api/chat`, and scores each
answer by checking that any of a set of expected substrings appears in it.
Results land under `eval/results/` (timestamped JSON + Markdown).

A checked-in baseline lives at [`eval/sample-result.md`](eval/sample-result.md).
Latest local run on `llama3.1:8b` + `nomic-embed-text`:

- 6/6 questions passed
- Average latency: 3.78 s per turn cold, ~0.5 s warm

## Development workflow

```powershell
# One-time setup
pip install -r requirements.txt
pre-commit install

# Per change
pre-commit run --all-files   # ruff lint+format, mypy, basic hygiene
pytest                       # unit + API tests (no Ollama needed)
```

Integration-style end-to-end checks against a live Ollama are kept out of CI
and live in `smoke_test.py` plus the `eval/` package.

## Commit and style conventions

- English only across code, comments, commits, identifiers.
- Public functions document `@param` / `@returns` (JSDoc-style docstrings).
- SOLID + DI: dependencies are injected via FastAPI `Depends` and constructor
  arguments, never module globals.
- Functions stay around the 30-line ceiling; pylint statement limits are
  enforced by ruff.
- Errors are translated at every external boundary into explicit domain
  exceptions (`EmbeddingError`, `ChatGenerationError`, `VectorStoreError`,
  `StorageError`, `UnsupportedFormatError`, `EmptyDocumentError`).
- Commits are atomic and pushed immediately; CI must stay green on `main`.
