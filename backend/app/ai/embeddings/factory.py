"""
app/ai/embeddings/factory.py

Single entry point for obtaining an EmbeddingProvider. Mirrors the inference
factory's pattern but is intentionally a separate function — see
app/ai/embeddings/base.py for why the two hierarchies are split.
"""

from __future__ import annotations

from functools import lru_cache

from app.ai.embeddings.base import EmbeddingProvider
from app.common.constants import EmbeddingProviderType


@lru_cache
def get_embedding_provider(provider: str, model: str) -> EmbeddingProvider:
    """
    Return the EmbeddingProvider for the given provider/model.

    Unlike the reference, model is threaded through rather than hardcoded in
    each provider — the model string is persisted per chunk, so it has to come
    from one place that config controls.
    """
    match provider.lower():
        case EmbeddingProviderType.OPENAI:
            from app.ai.embeddings.providers.openai import OpenAIEmbeddingProvider
            return OpenAIEmbeddingProvider(model=model)

        case EmbeddingProviderType.STUB:
            from app.ai.embeddings.providers.stub import StubEmbeddingProvider
            return StubEmbeddingProvider(model=model)

        case _:
            raise ValueError(
                f"Unknown embedding provider '{provider}'. Supported: openai, stub"
            )
