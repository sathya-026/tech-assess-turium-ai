"""
app/ai/inference/providers/openai.py

OpenAI implementation of InferenceProvider.

Uses Chat Completions throughout — format_messages and stream speak the same
wire format. (The reference repo mixes Responses-API shapes in its append_*
methods with Chat-Completions shapes in its memory conversion; with no tool
calling here there is only one shape to get right, but the rule still holds:
one API per provider class.)

`stream_options={"include_usage": True}` is required to get a usage payload on
a streamed call — without it the final chunk carries usage=None and token
accounting silently records zero.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator

from openai import AsyncOpenAI

from app.ai.inference.base import InferenceProvider
from app.ai.inference.types import AIEvent, ContentDelta, MemoryMessage, UsageEvent
from app.config import settings


class OpenAIInferenceProvider(InferenceProvider):

    def __init__(self, model: str) -> None:
        self._model = model
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            max_retries=3,
            timeout=90.0,
        )

    # ------------------------------------------------------------------
    # Message transformation
    # ------------------------------------------------------------------

    def format_messages(
        self,
        memory: list[MemoryMessage],
        system_prompt: str,
        rag_context: str,
    ) -> list[dict[str, Any]]:
        """
        Layout:
          [0]   system  — persona + RAG context + formatting + guardrails
          [1..] history — one entry per MemoryMessage, oldest first
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.build_system_prompt(system_prompt, rag_context)}
        ]
        for mem in memory:
            if mem.content:
                messages.append({"role": mem.role, "content": mem.content})
        return messages

    def append_user_message(self, messages: list[dict[str, Any]], content: str) -> None:
        messages.append({"role": "user", "content": content})

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def stream(
        self, messages: list[dict[str, Any]]
    ) -> AsyncGenerator[AIEvent, None]:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=settings.temperature,
            max_tokens=settings.max_output_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )

        async for chunk in response:
            # The usage-bearing final chunk has an empty choices list, so this
            # ordering matters — indexing choices[0] first would raise.
            if chunk.usage is not None:
                yield UsageEvent(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                )
                continue

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield ContentDelta(content=delta.content)
