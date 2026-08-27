"""FastAPI app: lifespan startup check, CORS, router registration."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.embeddings.factory import get_embedding_provider
from app.ai.inference.factory import get_inference_provider
from app.config import settings
from app.database import check_db_connection, init_db
from app.rag.store import store
from app.routers import ingest, items, query

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def _check_providers() -> None:
    """
    Resolve both providers at boot so a missing key or bad provider name fails
    at startup rather than on a user's first request.
    """
    needs_key = "openai" in (settings.inference_provider, settings.embedding_provider)
    if needs_key and not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Set it, or run with "
            "INFERENCE_PROVIDER=stub EMBEDDING_PROVIDER=stub for a keyless run."
        )
    get_inference_provider(settings.inference_provider, settings.generation_model)
    get_embedding_provider(settings.embedding_provider, settings.embedding_model)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_providers()
    await init_db()
    if not await check_db_connection():
        raise RuntimeError(f"Cannot reach database at {settings.database_url}")

    loaded = await store.reload()
    logger.info(
        "Ready — %d chunks in memory | inference=%s embeddings=%s",
        loaded, settings.inference_provider, settings.embedding_provider,
    )
    yield


app = FastAPI(
    title="RAG API",
    version="0.2.0",
    description="Ingest text and files, list them, ask grounded questions.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(items.router)
app.include_router(query.router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {
        "status": "ok",
        "indexed_chunks": store.size,
        "embedding_model": store.embedding_model,
        "inference_provider": settings.inference_provider,
        "embedding_provider": settings.embedding_provider,
    }