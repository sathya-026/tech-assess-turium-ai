"""
app/ai/embeddings/base.py

Abstract base class every embedding provider must implement.

This is a SEPARATE abstraction from app.ai.inference.base.InferenceProvider,
deliberately. The two are selected on different axes:

  - Inference provider is a free choice. Swapping it changes response style and
    cost; nothing persisted depends on it.

  - Embedding provider is persistence-constrained. Vectors live in
    chunks.embedding, and cosine distance between two different embedding
    spaces is meaningless — not merely lower quality. Changing the embedding
    model requires a re-index (see rag.indexer.reindex_all), not a config flip.

Conflating them would force every future inference provider to also implement
embeddings, which is not true in general.

Providers must L2-normalize their output so cosine similarity reduces to a dot
product in the store. Normalizing here rather than at search time keeps the hot
path a single matrix multiply.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Embed a single text. Used at retrieval time."""

    @abstractmethod
    async def embed_chunks(self, texts: list[str]) -> list[list[float]]:
        """
        Batch-embed, preserving input order across batches.
        Used at index time. Empty input returns [] without a network call.
        """

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """
        Output vector width for this provider/model.

        Callers need this ahead of time — the store asserts every loaded vector
        matches it, which is what turns "someone changed the model without
        re-indexing" from silently degraded ranking into a loud startup error.
        """

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier, recorded on each chunk so a stale-vector check is possible."""
