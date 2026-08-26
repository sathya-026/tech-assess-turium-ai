"""
app/db/conversations.py

Repository for the conversations table.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Conversation

logger = logging.getLogger(__name__)


async def get_or_create_conversation(
    db: AsyncSession,
    session_id: str,
    end_user_id: str | None = None,
) -> str:
    """
    Return the conversation id for session_id, creating the row on first use.

    The IntegrityError branch handles the duplicated-tab race: two simultaneous
    first messages both try to insert, one wins, the loser re-selects the
    winner. Equivalent to the reference's ON CONFLICT DO NOTHING, expressed in a
    way that works on SQLite and Postgres alike.
    """
    existing = await db.scalar(
        select(Conversation).where(Conversation.session_id == session_id)
    )
    if existing is not None:
        return existing.id

    conversation = Conversation(id=str(uuid.uuid4()), session_id=session_id,
                                end_user_id=end_user_id)
    db.add(conversation)
    try:
        await db.flush()
        return conversation.id
    except IntegrityError:
        await db.rollback()
        winner = await db.scalar(
            select(Conversation).where(Conversation.session_id == session_id)
        )
        if winner is None:
            raise
        return winner.id


async def update_conversation_stats(
    db: AsyncSession,
    conversation_id: str,
    tokens_delta: int,
    messages_delta: int = 2,
) -> None:
    """
    Increment token and message counters and refresh last_message_at.

    messages_delta defaults to 2 because one exchange persists both the user
    turn and the assistant turn. The reference increments by 1 per call and is
    called once per turn, which undercounts by half.
    """
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        logger.warning("update_conversation_stats: %s not found", conversation_id)
        return

    conversation.total_tokens += tokens_delta
    conversation.message_count += messages_delta
    conversation.last_message_at = datetime.now(timezone.utc)
