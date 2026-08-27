"""
app/ai/inference/base.py

Abstract base class every inference provider must implement.
Callers import only this interface and the factory — never a concrete provider.

Contract
--------
  format_messages()
      Takes the neutral MemoryMessage list from memory.load_memory(), the
      system prompt, and the formatted RAG context string. Returns a
      provider-specific messages list ready to pass into the SDK. Called ONCE
      per request, before generation.

      Responsibilities:
        - Build the system message (persona + RAG context + formatting + guardrails)
        - Convert each MemoryMessage into the provider's wire format

  append_user_message()
      Append the current user turn to the formatted list, in place.

  stream()
      Yields normalised AIEvents. All SDK-specific streaming logic, delta
      handling, and usage extraction lives here. The caller never sees a raw
      SDK object.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, AsyncGenerator

from app.ai.inference.types import AIEvent, ContentDelta, MemoryMessage, UsageEvent


class InferenceProvider(ABC):

    FORMATTING_INSTRUCTIONS = """## Response Formatting
- Use markdown for all responses.
- Use bullet points (`-`) or numbered lists for any list of items or steps.
- Use `**bold**` for key terms or important values.
- Use a blank line between distinct points or paragraphs.
- Keep responses concise — avoid walls of text.
- Never wrap the entire response in a code block unless it literally is code."""

    # ------------------------------------------------------------------
    # Message transformation
    # ------------------------------------------------------------------

    @abstractmethod
    def format_messages(
        self,
        memory: list[MemoryMessage],
        system_prompt: str,
        rag_context: str,
    ) -> list[Any]:
        """
        Transform neutral memory + context into provider wire format.

        rag_context is "" on a retrieval miss — providers must omit the
        knowledge-base section entirely rather than emitting an empty heading,
        which reads to the model as "the knowledge base is empty".
        """

    @abstractmethod
    def append_user_message(self, messages: list[Any], content: str) -> None:
        """Append the current user turn in place."""

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    @abstractmethod
    def stream(self, messages: list[Any]) -> AsyncGenerator[AIEvent, None]:
        """
        Call the provider and yield normalised AIEvents.

        Yield order:
          - Zero or more ContentDelta (response tokens, in order)
          - Exactly one UsageEvent    (always last)
        """

    # ------------------------------------------------------------------
    # Shared helpers — concrete, so providers don't each reinvent them
    # ------------------------------------------------------------------

    async def complete(self, messages: list[Any]) -> tuple[str, UsageEvent | None]:
        """
        Collect a full response by draining stream().

        Provided here so the non-streaming path is defined once. The JSON
        /query endpoint uses this; an SSE endpoint would consume stream()
        directly. Providers should not override it.
        """
        parts: list[str] = []
        usage: UsageEvent | None = None

        async for event in self.stream(messages):
            if isinstance(event, ContentDelta):
                parts.append(event.content)
            elif isinstance(event, UsageEvent):
                usage = event

        return "".join(parts), usage

    def build_system_prompt(self, system_prompt: str, rag_context: str) -> str:
        """
        Compose the system message from four sections:
          1. Persona / instructions
          2. Knowledge base context (omitted on retrieval miss)
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
            "Answer from the knowledge base context when it is relevant, and cite "
            "the context numbers you used as [1], [2].\n"
            "If the context does not contain the answer, say so clearly — do not "
            "fabricate, and do not fall back on general knowledge.\n"
            "If the question is too vague to answer from the context, say what is "
            "ambiguous and ask one clarifying question.\n"
            "Never cite a context number that was not provided."
        )
