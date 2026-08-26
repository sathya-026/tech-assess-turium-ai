"""
app/retrieval/retriever.py

Hybrid retriever — dense + BM25 over the in-memory store, fused with Reciprocal
Rank Fusion, plus the prompt context formatter.

Called before generation; the result is injected into the system prompt as
Knowledge Base Context.

Design notes:
  - RRF fuses by rank, not score. Cosine similarity and BM25 scores are on
    incomparable scales, so any weighted blend tuned for one corpus is wrong for
    the next. Ranks are scale-free — nothing to retune per document type.
  - The hit/miss threshold is applied to raw cosine similarity, NOT the RRF
    score. RRF values are rank artefacts (~1/60) with no absolute meaning;
    thresholding on them would be meaningless.
  - item_ids scopes retrieval before search, not after, so a filtered query
    still returns a full top_k.
  - Returns [] on a miss. Never raises on an empty result — the caller decides
    what to do with no context.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.chunks import fetch_chunks_by_ids
from app.rag.embedder import embed_query
from app.rag.store import store

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """
    One retrieved passage.

    char_start/char_end index into the owning item's raw_text, so the frontend
    can highlight the span inside the original document rather than showing a
    detached quote. Verified exact: raw_text[char_start:char_end] == content.
    """

    chunk_id: int
    item_id: str
    item_title: str
    filename: str | None
    content: str
    section_path: str
    char_start: int
    char_end: int
    similarity: float   # raw cosine, 0.0 -> 1.0
    score: float        # RRF fusion score, ordering only
    rank: int


def reciprocal_rank_fusion(
    rankings: dict[str, list[int]], weights: dict[str, float]
) -> list[tuple[int, float]]:
    fused: dict[int, float] = defaultdict(float)
    for name, ranked in rankings.items():
        weight = weights.get(name, 1.0)
        for position, index in enumerate(ranked):
            fused[index] += weight / (settings.rrf_k + position + 1)
    return sorted(fused.items(), key=lambda kv: -kv[1])


async def retrieve(
    db: AsyncSession,
    query: str,
    top_k: int | None = None,
    item_ids: list[str] | None = None,
    min_similarity: float | None = None,
) -> list[RetrievedChunk]:
    top_k = top_k or settings.default_top_k
    min_similarity = (
        settings.rag_min_similarity if min_similarity is None else min_similarity
    )

    if store.size == 0:
        logger.debug("Retrieval skipped: store is empty")
        return []

    n = settings.candidates_per_retriever
    query_vector = np.asarray(await embed_query(query), dtype=np.float32)

    rankings = {
        "dense": store.search_dense(query_vector, n, item_ids),
        "bm25": store.search_bm25(query, n, item_ids),
    }
    fused = reciprocal_rank_fusion(
        rankings, {"dense": settings.dense_weight, "bm25": settings.bm25_weight}
    )

    # --- reranker seam -------------------------------------------------
    # Take fused[:n] here, score (query, chunk_text) pairs with a cross-encoder,
    # and re-sort before truncating. A cross-encoder reads query and passage
    # together instead of embedding them separately, so it judges whether a
    # passage answers the question rather than whether it looks similar.
    # -------------------------------------------------------------------

    selected = fused[:top_k]
    if not selected:
        return []

    chunk_ids = [store.chunk_ids[index] for index, _ in selected]
    rows = await fetch_chunks_by_ids(db, chunk_ids)
    by_id = {row[0].id: row for row in rows}

    results: list[RetrievedChunk] = []
    for index, fusion_score in selected:
        row = by_id.get(store.chunk_ids[index])
        if row is None:
            continue
        similarity = store.cosine(index, query_vector)
        if similarity < min_similarity:
            continue

        chunk, title, filename = row
        results.append(RetrievedChunk(
            chunk_id=chunk.id,
            item_id=chunk.item_id,
            item_title=title,
            filename=filename,
            content=chunk.text,
            section_path=chunk.section_path,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            similarity=round(similarity, 6),
            score=round(float(fusion_score), 6),
            rank=0,
        ))

    for rank, chunk in enumerate(results, 1):
        chunk.rank = rank

    logger.debug(
        "Retrieved %d/%d chunks (top_k=%d, min_similarity=%.2f)",
        len(results), store.size, top_k, min_similarity,
    )
    return results


def format_context_for_prompt(chunks: list[RetrievedChunk]) -> str:
    """
    Serialise retrieved chunks into the string injected into the system prompt.

        [Context 1]
        chunk text...

    Numbered labels give the model a stable way to cite, and give the frontend a
    key to map a citation back to a highlightable span. Returns "" on a miss so
    the provider omits the knowledge-base section entirely rather than emitting
    an empty heading.
    """
    return "\n\n".join(
        f"[Context {chunk.rank}]\n{chunk.content}" for chunk in chunks
    )
