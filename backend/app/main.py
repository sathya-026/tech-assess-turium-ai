"""FastAPI app: lifespan startup check, CORS, router registration."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .providers.registry import check_providers
from .rag.store import store
from .routers import ingest, items, query

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail at boot rather than on the first user request.
    check_providers()
    await init_db()
    loaded = await store.reload()
    log.info(
        "Ready — %d chunks in memory | embeddings=%s llm=%s",
        loaded, settings.embedding_provider, settings.llm_provider,
    )
    yield


app = FastAPI(
    title="RAG API",
    version="0.1.0",
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
        "embedding_provider": settings.embedding_provider,
        "llm_provider": settings.llm_provider,
    }