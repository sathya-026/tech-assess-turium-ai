"""API contracts. These are what the frontend codes against."""

from datetime import datetime

from pydantic import BaseModel, Field


class ItemOut(BaseModel):
    id: str
    title: str
    source_type: str
    filename: str | None = None
    mime_type: str | None = None
    status: str                      # pending | processing | ready | failed
    error: str | None = None
    char_count: int
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestResponse(BaseModel):
    items: list[ItemOut]
    skipped: list[str] = Field(
        default_factory=list,
        description="Inputs rejected at validation, with the reason.",
    )


class ItemsResponse(BaseModel):
    items: list[ItemOut]
    total: int
    indexed_chunks: int


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    item_ids: list[str] | None = Field(
        default=None, description="Restrict retrieval to these items."
    )


class Source(BaseModel):
    """One retrieved passage. char_start/char_end index into the item's
    raw_text, so the UI can highlight the span inside the original document
    rather than showing a detached snippet."""

    rank: int
    chunk_id: int
    item_id: str
    item_title: str
    filename: str | None
    section_path: str
    snippet: str
    char_start: int
    char_end: int
    score: float


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[Source]
    model: str