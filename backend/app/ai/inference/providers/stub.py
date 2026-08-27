"""
app/ai/inference/providers/stub.py

Keyless, deterministic inference provider.

Not a toy — this is how the full ingest → retrieve → answer path runs in CI and
local development without spend or network. It echoes back which context blocks
it was given, which makes retrieval wiring failures visible in test output
instead of hidden behind a plausible-sounding generated answer.
"""

from __future__ import annotations

import re
from typing import Any, AsyncGenerator

from app.ai.inference.base import InferenceProvider
from app.ai.inference.types import AIEvent, ContentDelta, MemoryMessage, UsageEvent


class StubInferenceProvider(InferenceProvider):

    def __init__(self, model: str = "stub-echo") -> None:
        self._model = model

    def format_messages(
        self,
        memory: list[MemoryMessage],
        system_prompt: str,
        rag_context: str,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.build_system_prompt(system_prompt, rag_context)}
        ]
        for mem in memory:
            if mem.content:
                messages.append({"role": mem.role, "content": mem.content})
        return messages

    def append_user_message(self, messages: list[dict[str, Any]], content: str) -> None:
        messages.append({"role": "user", "content": content})

    async def stream(
        self, messages: list[dict[str, Any]]
    ) -> AsyncGenerator[AIEvent, None]:
        system = messages[0]["content"] if messages else ""
        question = messages[-1]["content"] if messages else ""
        turns = sum(1 for m in messages if m["role"] in ("user", "assistant"))
        citations = sorted(set(re.findall(r"\[Context (\d+)\]", system)), key=int)

        cited = ", ".join(f"[{c}]" for c in citations) if citations else "no context"
        for fragment in [
            f"[stub] Q: {question} | ",
            f"history_turns={turns} | ",
            f"grounded in {cited}",
        ]:
            yield ContentDelta(content=fragment)

        approx = sum(len(m["content"]) for m in messages) // 4
        yield UsageEvent(
            prompt_tokens=approx, completion_tokens=12, total_tokens=approx + 12
        )
