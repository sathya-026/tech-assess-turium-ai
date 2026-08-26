"""
app/rag/store.py

The search structure: an in-memory numpy matrix + BM25 index.

SQLite is the source of truth; this is a derived cache rebuilt from it. There is
no index to migrate or repair — if it looks wrong, restart.

Brute-force cosine over ~50k chunks is about a millisecond, which is why there
is no HNSW here. Approximate search is a trade you make when exact search stops
fitting; at this scale it would only add an index to maintain. Budget roughly
6 KB per chunk in RAM at 1536 dimensions.

One process holds this. Multiple workers each keep their own copy — correct but
wasteful, and the point at which a real vector DB starts earning its keep.
"""

from __future__ import annotations

import asyncio
import logging
import re

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal, unpack
from app.db.chunks import fetch_all_for_store

logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Shared by BM25 at index and query time — must stay identical for both."""
    return TOKEN_RE.findall(text.lower())


class VectorStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.chunk_ids: list[int] = []
        self.item_ids: list[str] = []
        self.vectors: np.ndarray | None = None
        self.bm25: BM25Okapi | None = None
        self.embedding_model: str | None = None

    @property
    def size(self) -> int:
        return len(self.chunk_ids)

    async def reload(self, session: AsyncSession | None = None) -> int:
        """
        Rebuild from the database.

        Cheap enough to call after every ingest, and it has to be: BM25Okapi
        precomputes IDF across the whole corpus, so appending to it without a
        rebuild would leave the term statistics stale.
        """
        async with self._lock:
            if session is not None:
                rows = await fetch_all_for_store(session)
            else:
                async with SessionLocal() as own:
                    rows = await fetch_all_for_store(own)

            if not rows:
                self.chunk_ids, self.item_ids = [], []
                self.vectors, self.bm25, self.embedding_model = None, None, None
                return 0

            models = {row[4] for row in rows if row[4]}
            if len(models) > 1:
                # Vectors from two embedding spaces are not comparable, and the
                # failure mode is silently degraded ranking rather than an
                # error. Refuse to serve rather than return quiet nonsense.
                raise RuntimeError(
                    f"Index contains vectors from multiple embedding models: "
                    f"{sorted(models)}. Run rag.indexer.reindex_all() to rebuild."
                )

            self.chunk_ids = [row[0] for row in rows]
            self.item_ids = [row[1] for row in rows]
            self.vectors = np.vstack([unpack(row[3]) for row in rows]).astype(np.float32)
            self.bm25 = BM25Okapi([tokenize(row[2]) for row in rows])
            self.embedding_model = next(iter(models), None)

            logger.info(
                "Store loaded: %d chunks, dim %d, model %s",
                self.size, self.vectors.shape[1], self.embedding_model,
            )
            return self.size

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _mask(self, item_ids: list[str] | None) -> np.ndarray | None:
        if not item_ids:
            return None
        wanted = set(item_ids)
        return np.array([iid in wanted for iid in self.item_ids], dtype=bool)

    def search_dense(
        self, query_vector: np.ndarray, k: int, item_ids: list[str] | None = None
    ) -> list[int]:
        """Return positional indices into the matrix, best first."""
        if self.vectors is None:
            return []
        scores = self.vectors @ np.asarray(query_vector, dtype=np.float32)

        mask = self._mask(item_ids)
        if mask is not None:
            if not mask.any():
                return []
            scores = np.where(mask, scores, -np.inf)

        k = min(k, int(np.isfinite(scores).sum()))
        if k <= 0:
            return []
        top = np.argpartition(-scores, k - 1)[:k]
        return [int(i) for i in top[np.argsort(-scores[top])]]

    def search_bm25(
        self, query: str, k: int, item_ids: list[str] | None = None
    ) -> list[int]:
        if self.bm25 is None:
            return []
        scores = np.asarray(self.bm25.get_scores(tokenize(query)))

        mask = self._mask(item_ids)
        if mask is not None:
            scores = np.where(mask, scores, 0.0)

        k = min(k, len(scores))
        if k <= 0:
            return []
        top = np.argpartition(-scores, k - 1)[:k]
        ordered = [int(i) for i in top[np.argsort(-scores[top])]]
        # A zero BM25 score means no query term appears at all. Keeping those
        # would feed arbitrary chunks into the fusion ranking.
        return [i for i in ordered if scores[i] > 0]

    def cosine(self, index: int, query_vector: np.ndarray) -> float:
        """
        Raw cosine similarity for one row.

        Needed because RRF scores are rank artefacts with no absolute meaning —
        you cannot threshold on them. The hit/miss decision uses this instead.
        """
        if self.vectors is None:
            return 0.0
        return float(self.vectors[index] @ np.asarray(query_vector, dtype=np.float32))


store = VectorStore()
