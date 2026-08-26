"""
app/db/items.py

Repository for the items table.

Repository functions do NOT commit. The reference commits inside every db/
helper and swallows exceptions, which means a failed write returns None and the
caller carries on with a null it never checks. Here the caller owns the
transaction boundary and exceptions propagate — the router or the indexer
decides what a failure means.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import ItemStatus
from app.database import Item

logger = logging.getLogger(__name__)


async def create_items(db: AsyncSession, items: list[Item]) -> list[Item]:
    db.add_all(items)
    await db.flush()
    for item in items:
        await db.refresh(item)
    return items


async def get_item(db: AsyncSession, item_id: str) -> Item | None:
    return await db.get(Item, item_id)


async def list_items(
    db: AsyncSession,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Item], int]:
    statement = select(Item).order_by(Item.created_at.desc())
    count_statement = select(func.count()).select_from(Item)

    if status:
        statement = statement.where(Item.status == status)
        count_statement = count_statement.where(Item.status == status)

    total = await db.scalar(count_statement) or 0
    rows = list((await db.execute(statement.limit(limit).offset(offset))).scalars())
    return rows, total


async def set_status(
    db: AsyncSession,
    item_id: str,
    status: ItemStatus | str,
    chunk_count: int | None = None,
    error: str | None = None,
) -> None:
    """Stage marker written at each step of the indexing pipeline."""
    item = await db.get(Item, item_id)
    if item is None:
        logger.warning("set_status: item %s not found", item_id)
        return

    item.status = str(status)
    item.error = error
    if chunk_count is not None:
        item.chunk_count = chunk_count


async def delete_item(db: AsyncSession, item_id: str) -> bool:
    item = await db.get(Item, item_id)
    if item is None:
        return False
    # Chunks go with it via cascade="all, delete-orphan".
    await db.delete(item)
    return True
