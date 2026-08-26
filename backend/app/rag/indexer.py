"""
app/rag/indexer.py

End-to-end indexing for one item, run as a FastAPI BackgroundTask.

  extract (already done at ingest) -> chunk -> embed -> insert -> reload store

Status is written at each stage so the frontend's item list can show live
progress, following the reference's staged approach. There is no S3 download
stage: bytes were extracted to items.raw_text at upload time.

BackgroundTask means in-process — a restart mid-index strands an item in
"indexing". That is exactly why status and error are persisted rather than held
in memory: you can see what stalled and re-ingest it. Move to a real queue when
ingest volume justifies the operational weight, not before.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.common.constants import ItemStatus
from app.database import Item, SessionLocal
from app.db.chunks import insert_chunks
from app.db.items import set_status
from app.rag.chunker import chunk_text
from app.rag.embedder import current_model, embed_chunks
from app.rag.store import store

logger = logging.getLogger(__name__)


async def run_indexing_pipeline(item_id: str) -> None:
    """
    Opens its own session: the request-scoped one is already closed by the time
    a BackgroundTask runs.
    """
    async with SessionLocal() as db:
        try:
            # ── Stage 1: mark as indexing ────────────────────────────────
            logger.info("Starting indexing: item_id=%s", item_id)
            item = await db.get(Item, item_id)
            if item is None:
                logger.error("Item %s vanished before indexing", item_id)
                return

            await set_status(db, item_id, ItemStatus.INDEXING)
            await db.commit()

            raw_text = item.raw_text
            if not raw_text.strip():
                raise RuntimeError("Item produced no extractable text")

            # ── Stage 2: chunk ───────────────────────────────────────────
            records = chunk_text(raw_text)
            logger.info("Produced %d chunks for %s", len(records), item_id)
            if not records:
                raise RuntimeError("Chunker produced no chunks from item text")

            # ── Stage 3: embed ───────────────────────────────────────────
            embeddings = await embed_chunks([r.text for r in records])

            # ── Stage 4: persist ─────────────────────────────────────────
            count = await insert_chunks(db, item_id, records, embeddings, current_model())

            # ── Stage 5: mark as indexed ─────────────────────────────────
            await set_status(db, item_id, ItemStatus.INDEXED, chunk_count=count)
            await db.commit()

            # ── Stage 6: refresh the search structure ────────────────────
            await store.reload(db)
            logger.info("Indexing complete for %s: %d chunks stored", item_id, count)

        except Exception as exc:
            logger.exception("Indexing failed for item %s", item_id)
            await db.rollback()
            try:
                await set_status(
                    db, item_id, ItemStatus.FAILED,
                    error=f"{type(exc).__name__}: {exc}"[:1000],
                )
                await db.commit()
            except Exception:
                logger.exception("Failed to record error status for %s", item_id)


async def reindex_all() -> int:
    """
    Re-embed every item.

    Required whenever the embedding model or chunk size changes — the store
    refuses to load a mixed-model index, so this is the migration path.
    """
    async with SessionLocal() as db:
        item_ids = list((await db.execute(select(Item.id))).scalars())

    for item_id in item_ids:
        await run_indexing_pipeline(item_id)
    return len(item_ids)
