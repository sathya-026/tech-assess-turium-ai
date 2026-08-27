"""
app/ai/inference/factory.py

Single entry point for obtaining an InferenceProvider.
Callers import only this function — never a concrete provider class.

Adding a provider:
  1. Implement InferenceProvider in app/ai/inference/providers/<name>.py
  2. Add a branch below
  3. No other file changes
"""

from __future__ import annotations

from functools import lru_cache

from app.ai.inference.base import InferenceProvider
from app.common.constants import AIProviderType


@lru_cache
def get_inference_provider(provider: str, model: str) -> InferenceProvider:
    """
    Return the InferenceProvider for the given provider string.

    Cached per (provider, model) so the SDK client and its connection pool are
    reused across requests instead of rebuilt per call. Providers must stay
    stateless for this to be safe — all per-request state lives in the
    `messages` list the caller owns.
    """
    match provider.lower():
        case AIProviderType.OPENAI:
            from app.ai.inference.providers.openai import OpenAIInferenceProvider
            return OpenAIInferenceProvider(model=model)

        case AIProviderType.STUB:
            from app.ai.inference.providers.stub import StubInferenceProvider
            return StubInferenceProvider(model=model)

        case _:
            raise ValueError(
                f"Unknown inference provider '{provider}'. Supported: openai, stub"
            )
