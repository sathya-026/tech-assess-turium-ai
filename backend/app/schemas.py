"""API contracts. These are what the frontend codes against."""

from datetime import datetime

from pydantic import BaseModel, Field


class ItemOut(BaseModel):
    id: str
    title: str
    source_type: str                  # text | file | url
    filename: str | None = None
    mime_type: str | None = None
    source_url: str | None = None
    status: str                       # pending | indexing | indexed | failed
    error: str | None = None
    char_count: int
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestResponse(BaseModel):
    items: list[ItemOut]
    skipped: list[str] = Field(
        default_factory=list, description="Inputs rejected at validation, with reason."
    )


class ItemsResponse(BaseModel):
    items: list[ItemOut]
    total: int
    indexed_chunks: int


class ItemDetail(ItemOut):
    raw_text: str


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(
        default=None,
        description="Client-supplied conversation key. Omit for a stateless "
                    "one-shot query with no history.",
    )
    end_user_id: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    item_ids: list[str] | None = Field(
        default=None, description="Restrict retrieval to these items."
    )


class Source(BaseModel):
    """
    One retrieved passage. rank matches the [Context N] label the model was
    shown, so a citation in the answer maps directly onto this entry.

    char_start/char_end index into the item's raw_text — fetch
    GET /items/{item_id} and slice to highlight in place.
    """

    rank: int
    chunk_id: int
    item_id: str
    item_title: str
    filename: str | None
    section_path: str
    snippet: str
    char_start: int
    char_end: int
    similarity: float
    score: float


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[Source]
    conversation_id: str | None
    model: str
    rag_hit: bool
    total_tokens: int
    latency_ms: int