"""
app/rag/embedder.py

Thin facade over the configured EmbeddingProvider.

Kept as a module (rather than having the indexer and retriever call the factory
directly) for the reason the reference gives: call sites stay stable when the
provider layer changes underneath. It also gives one place to expose the
model/dimensions the store needs for its consistency check.
"""

from __future__ import annotations

import logging

from app.ai.embeddings.base import EmbeddingProvider
from app.ai.embeddings.factory import get_embedding_provider
from app.config import settings

logger = logging.getLogger(__name__)


def provider() -> EmbeddingProvider:
    return get_embedding_provider(settings.embedding_provider, settings.embedding_model)


def current_model() -> str:
    return provider().model


def current_dimensions() -> int:
    return provider().dimensions


async def embed_chunks(texts: list[str]) -> list[list[float]]:
    """Index-time. Batching and retry live in the provider."""
    if not texts:
        return []
    vectors = await provider().embed_chunks(texts)
    if len(vectors) != len(texts):
        raise RuntimeError(
            f"Embedding count mismatch: {len(vectors)} vectors for {len(texts)} texts"
        )
    logger.info("Embedded %d chunks with %s", len(vectors), current_model())
    return vectors


async def embed_query(text: str) -> list[float]:
    """Retrieval-time."""
    return await provider().embed_query(text)
