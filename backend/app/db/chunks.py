"""
app/db/chunks.py

Repository for the chunks table.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Chunk, pack
from app.rag.chunker import ChunkRecord

logger = logging.getLogger(__name__)


async def insert_chunks(
    db: AsyncSession,
    item_id: str,
    records: list[ChunkRecord],
    embeddings: list[list[float]],
    embedding_model: str,
) -> int:
    """
    Replace all chunks for an item in one bulk insert.

    Deleting first makes re-indexing idempotent — calling the pipeline again
    after editing a document cannot leave duplicate chunks behind.
    """
    await db.execute(delete(Chunk).where(Chunk.item_id == item_id))

    if not records:
        return 0

    if len(records) != len(embeddings):
        raise ValueError(
            f"Embedding count mismatch: {len(embeddings)} vectors for {len(records)} chunks"
        )

    db.add_all([
        Chunk(
            item_id=item_id,
            position=record.position,
            text=record.text,
            section_path=record.section_path,
            char_start=record.char_start,
            char_end=record.char_end,
            embedding=pack(vector),
            embedding_model=embedding_model,
        )
        for record, vector in zip(records, embeddings)
    ])
    return len(records)


async def fetch_all_for_store(db: AsyncSession) -> list[tuple]:
    """
    Every chunk needed to rebuild the in-memory index, ordered by id so the
    matrix row order is stable across reloads.
    """
    return (await db.execute(
        select(
            Chunk.id, Chunk.item_id, Chunk.text, Chunk.embedding, Chunk.embedding_model
        ).order_by(Chunk.id)
    )).all()


async def fetch_chunks_by_ids(db: AsyncSession, chunk_ids: list[int]) -> list[tuple]:
    """Hydrate the final selected chunks with their item metadata."""
    from app.database import Item

    if not chunk_ids:
        return []
    return (await db.execute(
        select(Chunk, Item.title, Item.filename)
        .join(Item, Chunk.item_id == Item.id)
        .where(Chunk.id.in_(chunk_ids))
    )).all()
