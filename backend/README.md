# RAG API

FastAPI service wired to the `nexus-agent-core` architecture, using our SQLite
storage and `Item`/`Chunk` entities. No S3, no pgvector, no tool calling.

## Run

```bash
pip install -r requirements.txt
cp .env.example .env          # add OPENAI_API_KEY
uvicorn app.main:app --reload
```

Keyless local run (deterministic stub providers, no spend):

```bash
INFERENCE_PROVIDER=stub EMBEDDING_PROVIDER=stub uvicorn app.main:app --reload
python tests/test_api.py      # full ingest -> items -> query cycle, asserted
```

## Structure

```
app/
  main.py                       lifespan provider+db check, CORS, routers
  config.py                     pydantic-settings
  database.py                   ORM entities + engine + get_db
  schemas.py                    API contracts
  memory.py                     ConversationMemory, load_memory
  common/
    constants.py                StrEnums: providers, roles, statuses
    file_helper.py              bytes -> text (the only format-aware code)
  ai/
    inference/
      types.py                  MemoryMessage, ContentDelta, UsageEvent, AIEvent
      base.py                   InferenceProvider ABC + shared prompt assembly
      factory.py                get_inference_provider(provider, model)
      providers/openai.py|stub.py
    embeddings/
      base.py                   EmbeddingProvider ABC
      factory.py                get_embedding_provider(provider, model)
      providers/openai.py|stub.py
  db/
    items.py  chunks.py  conversations.py  messages.py
  rag/
    chunker.py                  offset-preserving structural chunking
    embedder.py                 thin facade over the embeddings provider
    store.py                    in-memory numpy matrix + BM25
    indexer.py                  staged pipeline, BackgroundTask
    retriever.py                dense + BM25 -> RRF -> format_context_for_prompt
  routers/
    ingest.py  items.py  query.py
```

## What was kept from the reference, and what changed

**Kept.** The `ai/` seam: neutral types in, normalised `AIEvent`s out, providers
own every byte of wire format, factories with lazy imports. Embeddings as a
*separate* hierarchy — the reasoning in `ai/embeddings/base.py` is correct and
worth preserving: inference providers swap freely, embedding providers are
persistence-constrained. The `db/` repository-per-table pattern. The staged
indexer with status written at each step. `format_context_for_prompt`'s
`[Context N]` labels. Denormalized `total_tokens`/`message_count` on
conversations.

**Changed.**

| Reference | Here | Why |
|---|---|---|
| Raw `text()` SQL | SQLAlchemy ORM | NestJS owns migrations there; this service owns its own schema |
| pgvector + HNSW | float32 BLOB + numpy matrix | Exact search, ~1ms at this scale, nothing to migrate |
| S3 download stage | Upload bytes → `items.raw_text` | No object store; raw_text is also what the UI slices for highlighting |
| `tool_calls` table, `role="tool"` handling | Removed | No tool calling |
| Postgres BEFORE INSERT trigger for `sequence_number` | Repository-assigned + `UNIQUE(conversation_id, sequence_number)` | SQLite has no trigger equivalent; the constraint keeps it honest |
| `db/` helpers commit + swallow exceptions | Callers own the transaction, exceptions propagate | A swallowed write returns `None` the caller never checks |
| `update_conversation_stats(... )` increments `message_count` by 1 | by 2 | One exchange persists two rows; the reference undercounts by half |
| `agents.system_prompt` | `settings.system_prompt` | No agents table here |
| `(str, Enum)` | `StrEnum` | `str((str,Enum) member)` returns `"ItemStatus.INDEXED"`, not `"indexed"` |

**Reference bug worth fixing upstream.** `ai/providers/openai.py` mixes wire
formats: `stream()` calls `responses.create(input=messages)` and the `append_*`
methods emit Responses shapes, but `_memory_message_to_openai()` emits Chat
Completions shapes (`{"role": "assistant", "tool_calls": [...]}` +
`{"role": "tool", ...}`). Turn 1 works; turn 2 breaks as soon as history
contains a tool call. This service uses Chat Completions throughout.

## Endpoints

**`POST /ingest`** — multipart, `text` and/or `files[]`, optional `title`.
Returns `202`; items start `pending`, background pipeline moves them
`indexing → indexed | failed`. Unusable files land in `skipped[]` rather than
failing the request.

**`GET /items`** — list view, poll for status. Plus `GET /items/{id}` (includes
`raw_text`) and `DELETE /items/{id}`.

**`POST /query`** — `{question, session_id?, top_k?, item_ids?}`.

`session_id` is optional. Omit it for a stateless one-shot; supply it and the
turn is persisted and replayed as memory on subsequent calls.

```json
{
  "answer": "The refund window is 30 days [1].",
  "conversation_id": "…",
  "rag_hit": true,
  "total_tokens": 673,
  "sources": [{
    "rank": 1, "item_id": "…", "filename": "policy.md",
    "section_path": "Billing > Refunds",
    "snippet": "Our refund window is 30 days…",
    "char_start": 1204, "char_end": 1698,
    "similarity": 0.612, "score": 0.0325
  }]
}
```

## Frontend notes

`source.rank` matches the `[Context N]` label the model was shown, so a `[1]` in
the answer maps directly onto `sources[0]`.

`char_start`/`char_end` index into that item's `raw_text`, verified exact:
`raw_text.slice(char_start, char_end) === snippet`. Fetch `GET /items/{item_id}`
once and slice client-side to highlight the passage in place.

`similarity` is raw cosine and is comparable across queries — use it to grey out
weak sources. `score` is the RRF fusion value; it only orders results and has no
absolute meaning, so don't display it as a confidence.

## Known limits

- Single process. Multiple workers each hold their own copy of the matrix.
- Changing `EMBEDDING_MODEL` requires `rag.indexer.reindex_all()`. The store
  refuses to load a mixed-model index rather than silently degrading ranking.
- No reranker. The seam is marked in `rag/retriever.py`.
- `BackgroundTask` is in-process: a restart mid-index strands an item in
  `indexing`. That's why `status`/`error` are persisted — you can see it and
  re-ingest.