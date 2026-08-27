````markdown
## Setup

1. Install the dependencies.
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
````

3. Add your OpenAI API key to `.env`.
4. Start the API:

   ```bash
   uvicorn app.main:app --reload
   ```

The API will be available on **port 8000**. The database file is created automatically on first startup.

### Run Without an API Key

For frontend development or CI, use stub providers:

```env
INFERENCE_PROVIDER=stub
EMBEDDING_PROVIDER=stub
```

This runs fully offline, costs nothing, and works end-to-end. The responses are fake, but the API response shapes are real.



### IMPORTANT
If you change the embedding model later, delete data/rag.db and re-ingest, or call reindex_all(). Vectors from two different models can't be compared, and the app will refuse to start rather than quietly return bad results.

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
    file_helper.py              upload bytes -> text (format-aware)
    url_fetcher.py              URL validation + server-side fetch + HTML -> markdown
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
    indexer.py                  staged pipeline (fetch -> chunk -> embed), BackgroundTask
    retriever.py                dense + BM25 -> RRF -> format_context_for_prompt
  routers/
    ingest.py  items.py  query.py
```

## Endpoints

**`POST /ingest`** — multipart, any combination of `text`, `files[]`, `urls[]`,
plus optional `title`. Returns `202`; items start `pending` and the background
pipeline moves them `indexing → indexed | failed`. Unusable inputs land in
`skipped[]` rather than failing the request.


**`GET /items`** — list view, poll for status. Plus `GET /items/{id}` (includes
`raw_text`) and `DELETE /items/{id}`.

**`POST /query`** — `{question, session_id?, top_k?, item_ids?}`.

`session_id` is optional. Omit it for a stateless one-shot; supply it and the
turn is persisted and replayed as memory on subsequent calls.

  