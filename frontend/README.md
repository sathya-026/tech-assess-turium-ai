# AYS — RAG frontend

React 19 + TypeScript + Vite + Tailwind v4 client for the RAG API (v0.2.0).

## Run

```bash
npm install
cp .env.example .env      # point VITE_API_BASE_URL at your API
npm run dev               # http://localhost:5173
```

Port 5173 is already in the API's `cors_allowed_origins`. If you serve from
anywhere else, add that origin server-side first.

## Architecture

```
src/
  api/client.ts        fetch wrapper; flattens FastAPI's two error shapes into ApiError
  api/endpoints.ts     one function per route
  session.ts           pure localStorage helpers, no React
  hooks/               useLibraryStore, useChatStore, useDocumentCache
  context/             LibraryProvider → ChatProvider
  components/
```

### Gotchas handled

- `conversation_id` is output-only. There is no request field to send it back, so
  `session_id` is the only thing that drives multi-turn memory. "New conversation"
  rotates it and clears the transcript in one step.
- `item_ids` is omitted entirely when nothing is checked. Sending `[]` would scope
  the search to zero items rather than to everything.
- Polling has a 120s deadline. Indexing is in-process server-side, so a restart
  mid-index strands an item in `indexing` permanently; without the deadline the
  app would poll it forever.
- `Source.score` is never rendered. `Source.similarity` drives the percentage and
  the dimming of weak matches.
- `section_path` is checked for emptiness before rendering.
- A superseded request can't clear the loading flag for its successor, and an
  aborted question stays in the transcript rather than rolling back.
