"""
app/ai/inference/types.py

Neutral, provider-agnostic types that flow between memory and every inference
provider implementation.

Two categories:
  1. MemoryMessage  — the intermediate format memory.py produces. Providers
                      consume this and convert it to their own wire format
                      inside format_messages().

  2. AIEvent        — the normalised stream every provider yields. Callers only
                      ever see these; they never handle raw SDK chunks.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MemoryMessage:
    """
    One turn of conversation history, loaded by memory.load_memory().

    role is "user" or "assistant" — those are the only roles persisted. With no
    tool calling in this service, a messages row maps 1:1 onto a MemoryMessage;
    no JOIN or grouping is needed to reconstruct a turn.
    """

    sequence_number: int
    role: str
    content: str


@dataclass
class ContentDelta:
    """A fragment of the response text, as it streams."""

    content: str


@dataclass
class UsageEvent:
    """
    Token consumption for the completed call. Yielded exactly once, last.
    total_tokens is what update_conversation_stats() increments.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


# The union callers iterate over.
AIEvent = ContentDelta | UsageEvent
