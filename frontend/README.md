# Grounded — RAG frontend

React 19 + TypeScript + Vite + Tailwind v4 client for the RAG API (v0.2.0).

## Run

```bash
npm install
cp .env.example .env      # point VITE_API_BASE_URL at your API
npm run dev               # http://localhost:5173
```

Port 5173 is already in the API's `cors_allowed_origins`. If you serve from
anywhere else, add that origin server-side first.

## URL ingestion

`POST /ingest` takes `text` once, `files` repeated per file, and `urls` repeated
per URL — all in one multipart request. The form submits whatever is filled in
across its three panels together, so a note, two files and a link are one call.

A link item behaves differently from the others on its way through the pipeline,
and the list accounts for it:

- It arrives with `char_count 0` and its title set to the raw URL. The row shows
  "fetching page" rather than "0 chars", which would read as an empty document.
- Once indexed, the title is replaced by the page's own `<title>` and
  `source_url` holds the post-redirect address. Rows are re-rendered from the
  poll response rather than the optimistic insert, so both land.
- `source_url` renders as a subtitle and an outbound link, since the title
  changes underneath the user partway through.
- Bad schemes are rejected synchronously into `skipped` and never create an item;
  fetch failures surface later as `status: "failed"` with a readable error.

Bare domains like `example.com/docs` are accepted — the server normalizes them —
so the field is a plain text input rather than `type="url"`, which would reject
them in the browser first.

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

Two contexts. `LibraryProvider` owns ingest, the poll loop, deletion, and which
items are checked. `ChatProvider` nests inside it and reads `selectedIds` to
populate `item_ids` on a query — chat depends on library, never the reverse, and
that wiring sits in one visible place rather than inside either hook.

Each hook returns a `useMemo`'d object, so context consumers don't re-render on
every parent render.

### Notes on the adaptation

Ported the structural patterns from `nexus-frontend/packages/widget`: one concern
per hook, `useCallback` on every action, `AbortController` in a ref, optimistic
insert with rollback in `catch`, pure storage helpers outside React.

Three things from the widget had no counterpart here:

- **No SSE.** `POST /query` blocks until the answer is ready, so `send` is a
  plain awaited fetch. Same external shape as the widget's `useChat`
  (`messages`, `isLoading`, `error`, `send`, `cancel`), no stream parser. The
  spinner is sized for a few seconds, not a token cursor.
- **No history endpoint.** The widget hydrated from `/chat/history`. This API has
  no way to read messages back, so the transcript is persisted to localStorage
  alongside the session id. Both are written together and cleared together —
  restoring the session id alone would leave the server remembering turns the
  user can no longer see.
- **No auth.** `useWidgetIdentity` collapses to nothing; the API takes no
  credentials.

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

## Design

The API guarantees `raw_text.slice(char_start, char_end) === snippet`, so
provenance is the thesis: chrome in Archivo stays quiet, anything a document or
the model actually said is set in Newsreader, and coordinates are in JetBrains
Mono. One loud colour — a highlighter chartreuse — spent only on citations and
the passage they point at. Clicking `[1]` opens the source drawer with that exact
span marked inside the real document, addressed by character offset.