"""
app/ai/types.py

Neutral, provider-agnostic types that flow between memory, the planner,
and every AI provider implementation.

Two categories:
  1. MemoryMessage  — the intermediate format memory.py produces.
                      Provider implementations consume this and convert it
                      to their own wire format inside format_messages().

  2. AIEvent        — the normalised stream of events that every provider
                      yields. The planner only ever sees these; it never
                      handles raw SDK chunks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any



@dataclass
class MemoryMessage:
    """
    One turn in conversation history, loaded from Postgres by memory.py.

    role is one of: "user" | "assistant"
    """
    sequence_number: int
    role: str                             # "user" | "assistant"
    content: str

# ---------------------------------------------------------------------------
# Normalised AI stream events
# ---------------------------------------------------------------------------

@dataclass
class ContentDelta:
    """
    A fragment of the final text response.
    Yielded during the last ReAct iteration only — the planner forwards
    these directly to the SSE stream.
    """
    content: str


@dataclass
class UsageEvent:
    """
    Token consumption for the completed LLM call.
    Yielded once, in the final chunk of a streaming response.
    prompt_tokens and completion_tokens are provided for granular logging;
    total_tokens is what update_conversation_stats() increments.
    """
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


# AIEvent is the union type the planner iterates over.
AIEvent = ContentDelta | UsageEvent