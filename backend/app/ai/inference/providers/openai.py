"""
app/ai/openai.py

OpenAI implementation of AIProvider.

Responsibilities absorbed from the old planner.py:
  - Building the system prompt (persona + RAG context + guardrails)
  - Converting MemoryMessages to OpenAI message dicts
  - Streaming from the OpenAI SDK
  - Extracting usage from the final chunk and emitting UsageEvent

The planner never imports openai directly.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI


from app.ai.base import AIProvider
from app.ai.types import (
    AIEvent,
    ContentDelta,
    MemoryMessage,
    UsageEvent,
)
from app.config import settings


class OpenAIProvider(AIProvider):

    def __init__(self, model: str) -> None:
        self._model = model
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

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
        Build the full OpenAI messages list from neutral inputs.

        Layout:
          [0]  system   — persona + RAG context + guardrails
          [1…] history  — converted from MemoryMessage list                         
        """
        messages: list[dict[str, Any]] = []
        messages.append(
            {
                "role": "system",
                "content": self._build_system_prompt(system_prompt, rag_context),
            }
        )

        for mem in memory:
            messages.extend(self._memory_message_to_openai(mem))

        return messages

    def append_user_message(
        self,
        messages: list[dict[str, Any]],
        content: str,
    ) -> None:
        messages.append({"role": "user", "content": content})

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def stream(
        self,
        messages: list[Any],
    ) -> AsyncGenerator[AIEvent, None]:

        call_kwargs: dict[str, Any] = {
            "model": self._model,
            "input": messages,
            "stream": True,
        }

        response_stream = await self._client.responses.create(**call_kwargs)

        async for event in response_stream:
            event_type = event.type

            # -- Text delta --
            if event_type == "response.output_text.delta":
                yield ContentDelta(content=event.delta)

            # -- Usage + completion --
            elif event_type == "response.completed":
                if event.response.usage:
                    u = event.response.usage
                    yield UsageEvent(
                        prompt_tokens=u.input_tokens,
                        completion_tokens=u.output_tokens,
                        total_tokens=u.total_tokens,
                    )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_system_prompt(self, system_prompt: str, rag_context: str) -> str:
        """
        Compose the full system message from four sections:
          1. Agent persona / instructions
          2. RAG knowledge base context (omitted on RAG miss)
          3. Formatting instructions
          4. Behavioural guardrails
        """
        sections: list[str] = [system_prompt.strip()]
        if rag_context:
            sections.append(f"## Knowledge Base Context\n{rag_context}")
        sections.append(self.FORMATTING_INSTRUCTIONS)
        sections.append(self._guardrails())

        return "\n\n".join(sections)

    def _guardrails(self) -> str:
        return (
            "## Instructions\n"
            f"Today's date is {date.today().isoformat()}.\n"
            "Answer only from the knowledge base context when it is relevant. "
            "If relevant information is present, provide a complete answer without citing the context. "
            "If the context does not contain the answer, say so clearly — do not fabricate. "
            "Be concise and helpful."
        )

    def _memory_message_to_openai(self, mem: MemoryMessage) -> list[dict[str, Any]]:
        if mem.role == "user":
            return [{"role": "user", "content": mem.content}]

        if mem.role == "assistant":
            return [{"role": "assistant", "content": mem.content}]

        return []
