"""
POST /query — the full wired path.

  get_or_create_conversation
    -> load_memory
    -> retrieve  -> format_context_for_prompt
    -> provider.format_messages(memory, system_prompt, rag_context)
    -> provider.append_user_message
    -> provider.complete  (drains provider.stream())
    -> save_message x2 -> update_conversation_stats

This is the reference's chat flow with the tool-calling loop removed: without
tools there is no ReAct iteration, so a single provider call replaces the loop.

session_id is optional. Omit it for a stateless one-shot query — memory is
skipped and nothing is persisted, which is what the "just ask a question" path
in the frontend wants.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory import load_memory
from app.ai.inference.factory import get_inference_provider
from app.common.constants import MessageRole
from app.config import settings
from app.database import get_db
from app.db.conversations import get_or_create_conversation, update_conversation_stats
from app.db.messages import save_message
from app.rag.retriever import format_context_for_prompt, retrieve
from app.schemas import QueryRequest, QueryResponse, Source

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])

NO_CONTEXT = (
    "I don't have any indexed documents to answer from yet. Add some text or "
    "upload a file first."
)


@router.post("/query", response_model=QueryResponse)
async def query(
    payload: QueryRequest, db: AsyncSession = Depends(get_db)
) -> QueryResponse:
    started = time.perf_counter()
    provider = get_inference_provider(
        settings.inference_provider, settings.generation_model
    )

    # ── Conversation + memory ────────────────────────────────────────────
    conversation_id: str | None = None
    memory_messages = []
    if payload.session_id:
        conversation_id = await get_or_create_conversation(
            db, payload.session_id, payload.end_user_id
        )
        await db.commit()
        memory = await load_memory(db, conversation_id)
        memory_messages = memory.messages

    # ── Retrieval ────────────────────────────────────────────────────────
    # History is prepended to the retrieval query only — never to the question
    # the model answers. A follow-up like "what about the other one?" has almost
    # no retrievable signal alone; this is the cheapest thing that gives it some,
    # and it is the seam where a proper history-aware rewriter would go.
    retrieval_query = payload.question
    if memory_messages:
        history = memory.to_context_string(max_messages=4, max_chars_per_message=200)
        if history:
            retrieval_query = f"{history}\nUser: {payload.question}"

    chunks = await retrieve(
        db, retrieval_query, top_k=payload.top_k, item_ids=payload.item_ids
    )
    rag_context = format_context_for_prompt(chunks)

    # ── Generation ───────────────────────────────────────────────────────
    messages = provider.format_messages(
        memory=memory_messages,
        system_prompt=settings.system_prompt,
        rag_context=rag_context,
    )
    provider.append_user_message(messages, payload.question)

    if not chunks and not memory_messages:
        # Nothing indexed and no history: answering would be pure fabrication.
        answer, usage = NO_CONTEXT, None
    else:
        answer, usage = await provider.complete(messages)

    latency_ms = int((time.perf_counter() - started) * 1000)
    total_tokens = usage.total_tokens if usage else 0

    # ── Persistence ──────────────────────────────────────────────────────
    if conversation_id:
        await save_message(db, conversation_id, MessageRole.USER, payload.question)
        await save_message(
            db, conversation_id, MessageRole.ASSISTANT, answer,
            tokens_used=total_tokens, latency_ms=latency_ms,
        )
        await update_conversation_stats(db, conversation_id, total_tokens)
        await db.commit()

    logger.info(
        "query: rag_hit=%s chunks=%d tokens=%d latency=%dms",
        bool(chunks), len(chunks), total_tokens, latency_ms,
    )

    return QueryResponse(
        question=payload.question,
        answer=answer,
        conversation_id=conversation_id,
        model=settings.generation_model,
        rag_hit=bool(chunks),
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        sources=[
            Source(
                rank=chunk.rank,
                chunk_id=chunk.chunk_id,
                item_id=chunk.item_id,
                item_title=chunk.item_title,
                filename=chunk.filename,
                section_path=chunk.section_path,
                snippet=chunk.content,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                similarity=chunk.similarity,
                score=chunk.score,
            )
            for chunk in chunks
        ],
    )