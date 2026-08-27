"""
app/ai/embeddings/providers/openai.py

OpenAI implementation of EmbeddingProvider.

Preserves the reference's behaviour:
  - batch_size 100
  - tenacity retry on RateLimitError / APITimeoutError,
    exponential backoff 2s -> 4s -> 8s -> 16s, max 4 attempts
  - defensive sort by item.index even though OpenAI guarantees order

Added here: L2 normalization, required by the store's dot-product search path.
"""

from __future__ import annotations

import numpy as np
from openai import APITimeoutError, AsyncOpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.ai.embeddings.base import EmbeddingProvider
from app.config import settings

BATCH_SIZE = 100


def _normalize(vectors: list[list[float]]) -> list[list[float]]:
    array = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (array / norms).tolist()


class OpenAIEmbeddingProvider(EmbeddingProvider):

    def __init__(self, model: str) -> None:
        self._model = model
        self._dimensions = settings.embedding_dimensions
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            max_retries=0,   # tenacity owns retry policy; don't stack backoffs
            timeout=60.0,
        )

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model(self) -> str:
        return self._model

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self._embed_batch([text])
        return vectors[0]

    async def embed_chunks(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            all_vectors.extend(await self._embed_batch(texts[i:i + BATCH_SIZE]))
        return all_vectors

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
        wait=wait_exponential(multiplier=2, min=2, max=16),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
            dimensions=self._dimensions,
        )
        # Defensive sort by item.index — OpenAI guarantees order, but silent
        # misordering here would corrupt every chunk's content/vector pairing,
        # and the cost of asserting it is one sort.
        ordered = sorted(response.data, key=lambda item: item.index)
        return _normalize([item.embedding for item in ordered])
