"""GET /items — the frontend's list view, and what it polls for index status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.db.items import delete_item, get_item, list_items
from app.rag.store import store
from app.schemas import ItemDetail, ItemOut, ItemsResponse

router = APIRouter(tags=["items"])


@router.get("/items", response_model=ItemsResponse)
async def get_items(
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None, pattern="^(pending|indexing|indexed|failed)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ItemsResponse:
    items, total = await list_items(db, status=status, limit=limit, offset=offset)
    return ItemsResponse(
        items=[ItemOut.model_validate(item) for item in items],
        total=total,
        indexed_chunks=store.size,
    )


@router.get("/items/{item_id}", response_model=ItemDetail)
async def get_item_detail(
    item_id: str, db: AsyncSession = Depends(get_db)
) -> ItemDetail:
    """
    Full raw_text included so the UI can slice it with a source's
    char_start/char_end and highlight the passage in context.
    """
    item = await get_item(db, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    return ItemDetail.model_validate(item)


@router.delete("/items/{item_id}", status_code=204)
async def remove_item(item_id: str, db: AsyncSession = Depends(get_db)) -> None:
    if not await delete_item(db, item_id):
        raise HTTPException(404, "Item not found")
    await db.commit()
    await store.reload(db)
