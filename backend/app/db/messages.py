"""
app/db/messages.py

Repository for the messages table.

With no tool calling, fetch_messages needs no LEFT JOIN and no grouping — a
messages row maps 1:1 onto a MemoryMessage. (The reference joins tool_calls and
regroups by sequence_number in Python because an assistant turn there can own N
tool calls; that whole path is unnecessary here.)
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import MessageRole
from app.database import Message

logger = logging.getLogger(__name__)


async def next_sequence_number(db: AsyncSession, conversation_id: str) -> int:
    current = await db.scalar(
        select(func.coalesce(func.max(Message.sequence_number), 0))
        .where(Message.conversation_id == conversation_id)
    )
    return int(current or 0) + 1


async def save_message(
    db: AsyncSession,
    conversation_id: str,
    role: MessageRole | str,
    content: str,
    tokens_used: int | None = None,
    latency_ms: int | None = None,
) -> Message:
    """
    Persist one message, assigning the next sequence_number.

    SQLite has no BEFORE INSERT trigger equivalent to the reference's, so the
    number is computed here. The UNIQUE(conversation_id, sequence_number)
    constraint is what keeps that honest under concurrency: a racing writer
    fails loudly rather than producing two turns with the same position.
    """
    message = Message(
        conversation_id=conversation_id,
        sequence_number=await next_sequence_number(db, conversation_id),
        role=str(role),
        content=content,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    )
    db.add(message)
    await db.flush()
    return message


async def fetch_messages(
    db: AsyncSession, conversation_id: str, max_messages: int = 20
) -> list[Message]:
    """
    Return the last `max_messages` turns in chronological order.

    Selected DESC to take the most recent window, then reversed so the caller
    gets oldest-first — which is the order a provider needs them in.
    """
    rows = list((await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence_number.desc())
        .limit(max_messages)
    )).scalars())
    return list(reversed(rows))
