# GenericRagGenerator

Local Retrieval-Augmented Generation (RAG) application. Upload PDF, TXT or Markdown
documents through a browser UI and chat with a local LLM that answers using only the
content of those documents.

## Stack

- **Backend:** Python 3.11 + FastAPI
- **LLM runtime:** [Ollama](https://ollama.com) (local, OSS)
- **Chat model:** `llama3.1:8b` (configurable)
- **Embedding model:** `nomic-embed-text`
- **Vector store:** ChromaDB (embedded, on-disk)
- **Frontend:** Plain HTML + CSS + ES6 (CSP-compliant, no inline scripts)

## Prerequisites

1. Python 3.11+
2. Ollama installed and running: `ollama serve`
3. Required models pulled once:
   ```
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

Then open <http://127.0.0.1:8000>.

## API

| Method | Path                  | Purpose                          |
|--------|-----------------------|----------------------------------|
| GET    | `/api/health`         | Service + Ollama reachability    |
| GET    | `/api/documents`      | List indexed documents           |
| POST   | `/api/documents`      | Upload a document (multipart)    |
| DELETE | `/api/documents/{id}` | Remove a document and its chunks |
| POST   | `/api/chat`           | Stream a chat answer (NDJSON)    |

## Project layout

```
backend/app/
  api/           HTTP routes
  services/      Business logic (loader, chunker, embedder, store, RAG chain)
  models/        Pydantic schemas
  config.py      Settings (env-driven)
  main.py        FastAPI entry, serves frontend as static
frontend/        Static UI
data/            Runtime (uploads + Chroma persistence) - gitignored
```
