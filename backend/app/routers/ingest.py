"""
POST /ingest — pasted text, uploaded files, and/or URLs.

All three in one multipart request because the frontend has one textarea, one
drop zone, and one URL box feeding the same list.

Validation is synchronous, so bad input fails immediately with a per-input
reason. Work is backgrounded:
  - file bytes are extracted here (an unsupported format must be rejected now,
    not minutes later)
  - URL content is fetched in the pipeline (a hanging site must not hold this
    connection open)
"""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import ItemSourceType, ItemStatus
from app.common.file_helper import extract_text
from app.common.url_fetcher import validate_url
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
    urls: list[str] = Form(default=[]),
    files: list[UploadFile] = File(default=[]),
) -> IngestResponse:
    if not text and not files and not urls:
        raise HTTPException(400, "Provide `text`, `urls`, and/or `files`.")

    pending: list[Item] = []
    skipped: list[str] = []

    if text and text.strip():
        pending.append(Item(
            id=str(uuid.uuid4()),
            title=title or (text.strip()[:60] + ("…" if len(text) > 60 else "")),
            source_type=ItemSourceType.TEXT,
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
            source_type=ItemSourceType.FILE,
            filename=name,
            mime_type=upload.content_type,
            raw_text=extracted,
            char_count=len(extracted),
            status=ItemStatus.PENDING,
        ))

    for raw_url in urls:
        if not raw_url or not raw_url.strip():
            continue
        try:
            clean_url = validate_url(raw_url)
        except ValueError as exc:
            skipped.append(f"{raw_url.strip()[:80]}: {exc}")
            continue

        # raw_text stays empty and char_count 0 until the pipeline fetches the
        # page. The title falls back to the URL and is replaced with the page's
        # own <title> once known, unless the caller supplied one.
        pending.append(Item(
            id=str(uuid.uuid4()),
            title=title or clean_url,
            source_type=ItemSourceType.URL,
            source_url=clean_url,
            raw_text="",
            char_count=0,
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