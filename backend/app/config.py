"""Typed settings, read from environment / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SYSTEM_PROMPT = (
    "You are a knowledge base assistant. You answer questions using the "
    "context passages retrieved from documents the user has ingested."
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- providers ---
    # "openai" | "stub". Selected independently: see app/ai/embeddings/base.py
    # for why embeddings are not swappable as freely as inference.
    inference_provider: str = "openai"
    embedding_provider: str = "openai"

    openai_api_key: str = ""
    openai_base_url: str | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    generation_model: str = "gpt-4o-mini"

    temperature: float = 0.0          # grounded extraction, not creative writing
    max_output_tokens: int = 1024
    system_prompt: str = DEFAULT_SYSTEM_PROMPT

    # --- storage ---
    database_url: str = f"sqlite+aiosqlite:///{ROOT / 'data' / 'rag.db'}"

    # --- chunking ---
    chunk_size: int = 2000            # chars; ~500 tokens
    chunk_overlap: int = 200
    min_chunk_chars: int = 60

    # --- retrieval ---
    candidates_per_retriever: int = 50
    rrf_k: int = 60
    default_top_k: int = 5
    dense_weight: float = 1.0
    bm25_weight: float = 1.0
    # Cosine floor for the hit/miss decision. Applied to dense similarity, not
    # the RRF score — RRF values are rank artefacts with no absolute meaning.
    rag_min_similarity: float = 0.20

    # --- conversation ---
    memory_max_messages: int = 20

    # --- ingest ---
    max_file_bytes: int = 10 * 1024 * 1024
    embed_batch_size: int = 100

    # --- api ---
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
