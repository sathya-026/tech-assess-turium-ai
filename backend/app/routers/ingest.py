"""
POST /ingest — raw text and/or file uploads.

Both in one multipart request because the frontend has one textarea and one
drop zone feeding the same list. Validation is synchronous so bad input fails
with a clear per-file reason; chunking and embedding are backgrounded so a large
upload doesn't hold the connection.
"""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import ItemStatus
from app.common.file_helper import extract_text
from app.config import settings
from app.database import Item, get_db
from app.db.items import create_items
from app.rag.indexer import run_indexing_pipeline
from app.schemas import IngestResponse, ItemOut

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest(
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    text: str | None = Form(None),
    title: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
) -> IngestResponse:
    if not text and not files:
        raise HTTPException(400, "Provide `text`, one or more `files`, or both.")

    pending: list[Item] = []
    skipped: list[str] = []

    if text and text.strip():
        pending.append(Item(
            id=str(uuid.uuid4()),
            title=title or (text.strip()[:60] + ("…" if len(text) > 60 else "")),
            source_type="text",
            raw_text=text,
            char_count=len(text),
            status=ItemStatus.PENDING,
        ))

    for upload in files:
        content = await upload.read()
        name = upload.filename or "upload"

        if len(content) > settings.max_file_bytes:
            skipped.append(f"{name}: exceeds {settings.max_file_bytes // 1024 // 1024}MB")
            continue
        try:
            extracted = extract_text(content, name, upload.content_type)
        except ValueError as exc:
            skipped.append(f"{name}: {exc}")
            continue
        if not extracted.strip():
            skipped.append(f"{name}: no text content")
            continue

        pending.append(Item(
            id=str(uuid.uuid4()),
            title=title or name,
            source_type="file",
            filename=name,
            mime_type=upload.content_type,
            raw_text=extracted,
            char_count=len(extracted),
            status=ItemStatus.PENDING,
        ))

    if not pending:
        raise HTTPException(422, {"message": "Nothing ingestable.", "skipped": skipped})

    created = await create_items(db, pending)
    await db.commit()

    for item in created:
        # Runs after the response is flushed; the frontend polls /items for the
        # pending -> indexing -> indexed transition.
        background.add_task(run_indexing_pipeline, item.id)

    return IngestResponse(
        items=[ItemOut.model_validate(item) for item in created], skipped=skipped
    )
