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
from sqlalchemy import ForeignKey, Index, LargeBinary, String, Text, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .config import settings


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Item(Base):
    """One ingested source: a pasted text blob or an uploaded file."""

    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    source_type: Mapped[str] = mapped_column(String(16))       # text | file
    filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Kept so the frontend can render a snippet in its surrounding context
    # using the char offsets returned by /query.
    raw_text: Mapped[str] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(16), default="pending")
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

    # Offsets into Item.raw_text — this is what lets the UI highlight the
    # exact span inside the original document rather than showing a detached
    # snippet the user has to go hunting for.
    char_start: Mapped[int] = mapped_column(default=0)
    char_end: Mapped[int] = mapped_column(default=0)

    embedding: Mapped[bytes] = mapped_column(LargeBinary)

    item: Mapped[Item] = relationship(back_populates="chunks")


Index("ix_chunks_item_position", Chunk.item_id, Chunk.position)


def pack(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def unpack(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_url.split("///")[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency."""
    async with SessionLocal() as session:
        yield session