"""Application settings loaded from environment / .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration for the RAG service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_host: str = "http://localhost:11434"
    chat_model: str = "llama3.1:8b"
    embedding_model: str = "nomic-embed-text"

    chroma_dir: Path = Path("./data/chroma")
    upload_dir: Path = Path("./data/uploads")

    chunk_size: int = 800
    chunk_overlap: int = 120
    # top_k = 8 is the sane production default. The eval ran at 60 only to
    # show ranking holds on a tiny corpus; on a real index (thousands of
    # chunks) 60 stuffs the prompt and explodes latency.
    top_k: int = 8

    embedding_query_prefix: str = "search_query: "
    embedding_document_prefix: str = "search_document: "

    # "vector" (default) = dense embeddings only.
    # "hybrid"           = dense + BM25 lexical, fused via Reciprocal Rank
    #                      Fusion. Helps with rare-token queries (function
    #                      names, error codes); costs an in-memory BM25
    #                      corpus rebuild on first query after writes.
    retrieval_mode: Literal["vector", "hybrid"] = "vector"

    app_host: str = "127.0.0.1"
    app_port: int = 8000

    api_key: SecretStr | None = None
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:8000", "http://127.0.0.1:8000"]
    )
    rate_limit_chat: str = "30/minute"
    rate_limit_uploads: str = "10/minute"

    auth_username: str = "admin"
    auth_password: SecretStr | None = None
    jwt_secret: SecretStr | None = None
    jwt_expires_minutes: int = 60
    docs_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    @returns Settings singleton built from environment variables.
    """
    settings = Settings()
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings
