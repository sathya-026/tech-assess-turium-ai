"""Async SQLAlchemy over SQLite.

No pgvector. Embeddings are stored as raw float32 bytes in a BLOB column and
loaded into a numpy matrix at startup (see rag/store.py). SQLite is the
durable record; the matrix is the search structure. That split is what keeps
storage boring — there is no index to migrate, reindex, or keep in sync
beyond "rebuild the matrix".

Swap `database_url` to postgres+asyncpg and this file barely changes; only the
embedding column type and the store would need real work.
"""

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sqlalchemy import (
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.common.constants import ConversationStatus, ItemStatus
from app.config import settings


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

class Item(Base):
    """One ingested source: pasted text or an uploaded file."""

    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    source_type: Mapped[str] = mapped_column(String(16))       # text | file | url
    filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Set only for source_type == "url". Holds the URL after redirects, so it
    # is the address the content actually came from, not what was pasted.
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Kept so the frontend can render a retrieved snippet inside its original
    # context using the char offsets on Chunk.
    raw_text: Mapped[str] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(16), default=ItemStatus.PENDING)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_count: Mapped[int] = mapped_column(default=0)
    chunk_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", lazy="selectin"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[str] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column()
    text: Mapped[str] = mapped_column(Text)
    section_path: Mapped[str] = mapped_column(Text, default="")

    # Offsets into Item.raw_text. Verified exact — raw_text[start:end] == text.
    char_start: Mapped[int] = mapped_column(default=0)
    char_end: Mapped[int] = mapped_column(default=0)

    embedding: Mapped[bytes] = mapped_column(LargeBinary)
    # Recorded per chunk so a model change is detectable rather than silently
    # degrading ranking. The store refuses to load a mixed-model index.
    embedding_model: Mapped[str] = mapped_column(String(128), default="")

    item: Mapped[Item] = relationship(back_populates="chunks")


Index("ix_chunks_item_position", Chunk.item_id, Chunk.position)


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

class Conversation(Base):
    """
    One chat session. session_id is the client-supplied key (a browser session,
    a widget instance) and is unique — get_or_create keys off it.

    total_tokens and message_count are denormalized on purpose, as in the
    reference: it makes dashboard reads O(1) instead of an aggregate over
    messages.
    """

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    end_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=ConversationStatus.ACTIVE)

    total_tokens: Mapped[int] = mapped_column(default=0)
    message_count: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime] = mapped_column(default=_now)
    last_message_at: Mapped[datetime] = mapped_column(default=_now)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    """
    One turn. role is "user" or "assistant" only.

    sequence_number is per-conversation and assigned by the repository, not a DB
    trigger (SQLite has no equivalent to the reference's Postgres trigger). The
    UNIQUE constraint below is what makes that safe: a concurrent double-write
    to the same conversation fails loudly instead of silently interleaving.
    """

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence_number", name="uq_conv_seq"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    sequence_number: Mapped[int] = mapped_column()
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)

    tokens_used: Mapped[int | None] = mapped_column(nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


# ---------------------------------------------------------------------------
# Vector packing
# ---------------------------------------------------------------------------

def pack(vector: list[float] | np.ndarray) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def unpack(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


# ---------------------------------------------------------------------------
# Engine / session
# ---------------------------------------------------------------------------

engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    if settings.database_url.startswith("sqlite"):
        Path(settings.database_url.split("///")[-1]).parent.mkdir(
            parents=True, exist_ok=True
        )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def check_db_connection() -> bool:
    from sqlalchemy import text as sql_text
    try:
        async with SessionLocal() as session:
            await session.execute(sql_text("SELECT 1"))
        return True
    except Exception:
        return False


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise