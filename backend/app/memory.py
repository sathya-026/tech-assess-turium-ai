"""
app/memory.py

Conversation memory.

Loads the last N turns for a conversation and hands back neutral
MemoryMessages. Providers convert those to wire format; nothing here knows what
an OpenAI message dict looks like.

Created fresh per request — stateless, so horizontal scaling needs no session
affinity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.inference.types import MemoryMessage
from app.config import settings
from app.db.messages import fetch_messages

logger = logging.getLogger(__name__)


@dataclass
class ConversationMemory:
    conversation_id: str
    messages: list[MemoryMessage] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.messages

    @property
    def turn_count(self) -> int:
        """Number of user turns loaded."""
        return sum(1 for m in self.messages if m.role == "user")

    def to_context_string(
        self, max_messages: int = 8, max_chars_per_message: int = 500
    ) -> str:
        """
        Compact text-only history.

        Used for retrieval query expansion — a follow-up like "what about the
        other one?" has almost no retrievable signal on its own, and this is the
        cheapest thing to prepend that gives it some.
        """
        lines: list[str] = []
        for message in self.messages[-max_messages:]:
            content = " ".join(str(message.content).split())
            if not content:
                continue
            if len(content) > max_chars_per_message:
                content = content[:max_chars_per_message].rstrip() + "..."
            label = "User" if message.role == "user" else "Assistant"
            lines.append(f"{label}: {content}")
        return "\n".join(lines)


async def load_memory(
    db: AsyncSession,
    conversation_id: str,
    max_messages: int | None = None,
) -> ConversationMemory:
    max_messages = max_messages or settings.memory_max_messages

    try:
        rows = await fetch_messages(db, conversation_id, max_messages)
    except Exception:
        # A history read failure degrades the answer but should not fail the
        # request — the model can still answer from retrieved context alone.
        logger.exception("Failed loading memory for conversation %s", conversation_id)
        rows = []

    messages = [
        MemoryMessage(
            sequence_number=row.sequence_number,
            role=row.role,
            content=row.content or "",
        )
        for row in rows
    ]

    logger.debug(
        "Loaded %d messages for conversation %s (window=%d)",
        len(messages), conversation_id, max_messages,
    )
    return ConversationMemory(conversation_id=conversation_id, messages=messages)