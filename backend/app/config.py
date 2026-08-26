"""Typed settings, read from environment / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- providers ---
    # "openai" | "stub". The stub returns deterministic hash-based vectors so
    # tests and local runs need no API key and cost nothing.
    embedding_provider: str = "openai"
    llm_provider: str = "openai"

    openai_api_key: str = ""
    openai_base_url: str | None = None          # set for Azure / proxies
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    generation_model: str = "gpt-4o-mini"

    # --- storage ---
    database_url: str = f"sqlite+aiosqlite:///{ROOT / 'data' / 'rag.db'}"

    # --- chunking ---
    chunk_size: int = 2000                      # chars; ~500 tokens
    chunk_overlap: int = 200
    min_chunk_chars: int = 60

    # --- retrieval ---
    candidates_per_retriever: int = 50
    rrf_k: int = 60
    default_top_k: int = 5
    dense_weight: float = 1.0
    bm25_weight: float = 1.0

    # --- ingest limits ---
    max_file_bytes: int = 10 * 1024 * 1024
    embed_batch_size: int = 128

    # --- api ---
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()