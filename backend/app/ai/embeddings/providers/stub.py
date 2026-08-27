"""
app/ai/embeddings/providers/stub.py

Deterministic, keyless embedding provider — hashed bag-of-words.

Semantically similar text does land nearby, which is enough to smoke-test
ranking wiring end to end. It is not a substitute for real embeddings: with no
semantics, near-ties across unrelated chunks are expected, and BM25 carries
most of the signal in the hybrid fusion.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

from app.ai.embeddings.base import EmbeddingProvider
from app.config import settings


def _hash_vector(text: str, dims: int) -> list[float]:
    vector = np.zeros(dims, dtype=np.float32)
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dims
        vector[index] += 1.0 if digest[4] % 2 else -1.0
    norm = float(np.linalg.norm(vector))
    return (vector / norm).tolist() if norm else vector.tolist()


class StubEmbeddingProvider(EmbeddingProvider):

    def __init__(self, model: str = "stub-hash") -> None:
        self._model = model
        self._dimensions = settings.embedding_dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model(self) -> str:
        return self._model

    async def embed_query(self, text: str) -> list[float]:
        return _hash_vector(text, self._dimensions)

    async def embed_chunks(self, texts: list[str]) -> list[list[float]]:
        return [_hash_vector(t, self._dimensions) for t in texts]
