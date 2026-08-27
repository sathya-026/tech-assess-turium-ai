"""
app/rag/indexer.py

End-to-end indexing for one item, run as a FastAPI BackgroundTask.

  fetch (URL items only) -> chunk -> embed -> insert -> reload store

Status is written at each stage so the frontend's item list can show live
progress, following the reference's staged approach.

Text and file items already have their raw_text populated by /ingest — file
bytes are extracted synchronously so an unsupported format is rejected with a
clear reason. URL items arrive with raw_text empty and are fetched here, in the
slot the reference used for its S3 download.

BackgroundTask means in-process — a restart mid-index strands an item in
"indexing". That is exactly why status and error are persisted rather than held
in memory: you can see what stalled and re-ingest it. Move to a real queue when
ingest volume justifies the operational weight, not before.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.common.constants import ItemSourceType, ItemStatus
from app.common.url_fetcher import fetch_url
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

            # ── Stage 2: fetch, for URL items ────────────────────────────
            # Deferred to here rather than done in the request so a slow or
            # hanging site cannot hold the /ingest connection open. Occupies
            # the same slot as the reference pipeline's S3 download stage.
            if item.source_type == ItemSourceType.URL and not item.raw_text.strip():
                page = await fetch_url(item.source_url or "")
                item.raw_text = page.text
                item.char_count = len(page.text)
                item.mime_type = page.content_type
                # Record the post-redirect URL, and adopt the page's own title
                # unless the user supplied one at ingest time.
                item.source_url = page.url
                if item.title == item.source_url or not item.title.strip():
                    item.title = page.title
                await db.commit()
                logger.info("Fetched %s: %d chars", page.url, len(page.text))

            raw_text = item.raw_text
            if not raw_text.strip():
                raise RuntimeError("Item produced no extractable text")

            # ── Stage 3: chunk ───────────────────────────────────────────
            records = chunk_text(raw_text)
            logger.info("Produced %d chunks for %s", len(records), item_id)
            if not records:
                raise RuntimeError("Chunker produced no chunks from item text")

            # ── Stage 4: embed ───────────────────────────────────────────
            embeddings = await embed_chunks([r.text for r in records])

            # ── Stage 5: persist ─────────────────────────────────────────
            count = await insert_chunks(db, item_id, records, embeddings, current_model())

            # ── Stage 6: mark as indexed ─────────────────────────────────
            await set_status(db, item_id, ItemStatus.INDEXED, chunk_count=count)
            await db.commit()

            # ── Stage 7: refresh the search structure ────────────────────
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