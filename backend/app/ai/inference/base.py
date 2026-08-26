"""
app/ai/base.py

Abstract base class that every AI provider must implement.
The planner imports only this interface and the factory — never a concrete provider.

Contract
--------
  format_messages()
      Takes the neutral MemoryMessage list produced by memory.load_memory(),
      the agent's system prompt string, and the formatted RAG context string.
      Returns a provider-specific messages list ready to pass straight into
      the SDK. This is called ONCE before the ReAct loop begins.

      Responsibilities inside this method:
        - Build the system message (persona + RAG context + guardrails)
        - Convert each MemoryMessage into the provider's wire format

  stream()
      Accepts the already-formatted messages list (from format_messages),
      Yields normalised AIEvents — ContentDelta | UsageEvent.

      Responsibilities inside this method:
        - All provider-specific streaming logic
        - Usage extraction and emission as UsageEvent
        - The planner must never see raw SDK objects
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator

from app.ai.types import AIEvent, MemoryMessage


class AIProvider(ABC):

    FORMATTING_INSTRUCTIONS = """
    ## Response Formatting
    - Use markdown for all responses.
    - Use bullet points (`-`) or numbered lists for any list of items or steps.
    - Use `**bold**` for key terms or important values.
    - Use a blank line between distinct points or paragraphs.
    - Keep responses concise — avoid walls of text.
    - Never wrap the entire response in a code block unless it literally is code.
    """

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

        Parameters
        ----------
        memory:
            Ordered list of past turns from memory.load_memory().
            Empty list on first message in a conversation.
        system_prompt:
            The agent's configured persona/instructions (agents.system_prompt).
        rag_context:
            Pre-formatted RAG string from retriever.format_context_for_prompt().
            Empty string when retrieval returned no chunks (RAG miss).

        Returns
        -------
        A list in whatever shape the provider's SDK expects for its
        `messages` parameter. The planner treats this as opaque —
        it only appends to it using append_user_message().
        """

    @abstractmethod
    def append_user_message(
        self,
        messages: list[Any],
        content: str,
    ) -> None:
        """
        Append a user turn to an already-formatted messages list in-place.
        Called by the planner once, right before the ReAct loop starts.
        """

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    @abstractmethod
    def stream(
        self,
        messages: list[Any],
    ) -> AsyncGenerator[AIEvent, None]:
        """
        Call the provider and yield normalised AIEvents.

        The planner calls this at the start of each ReAct iteration,
        passing the full messages list accumulated so far.

        Yield order within one call:
          - OR one or more ContentDelta    (final answer tokens)
          - Exactly one UsageEvent         (always last)

        The provider must never yield ContentDelta
        in the same call — they represent mutually exclusive turn types.
        """