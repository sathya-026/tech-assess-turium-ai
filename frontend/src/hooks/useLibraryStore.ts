// Owns everything about *what has been ingested*: the item list, the indexing
// poll loop, and which items are checked for query scoping. Knows nothing about
// questions or answers — that's useChatStore's job.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { deleteItem, ingest, listItems } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { ItemOut } from "../types";

const POLL_INTERVAL_MS = 1000;
const POLL_TIMEOUT_MS = 120_000;

function isInFlight(item: ItemOut) {
  return item.status === "pending" || item.status === "indexing";
}

export function useLibraryStore() {
  const [items, setItems] = useState<ItemOut[]>([]);
  const [indexedChunks, setIndexedChunks] = useState(0);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isIngesting, setIsIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [pollTimedOut, setPollTimedOut] = useState(false);

  const deadlineRef = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await listItems({ limit: 500 });
      setItems(data.items);
      setTotal(data.total);
      setIndexedChunks(data.indexed_chunks);
      setError(null);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError(err instanceof ApiError ? err.message : "Couldn't load your sources.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // ─── Poll loop ────────────────────────────────────────────────────────────
  // Indexing runs in the background and the only way to observe it finishing is
  // to re-read the list. One request covers every in-flight item, so this polls
  // the collection rather than each item.
  //
  // The deadline exists because indexing is in-process server-side: a restart
  // mid-index strands an item in 'indexing' permanently. Without a timeout the
  // app would poll that item until the tab closed.

  const inFlightCount = items.filter(isInFlight).length;

  useEffect(() => {
    if (inFlightCount === 0) {
      deadlineRef.current = null;
      return;
    }
    if (deadlineRef.current === null) {
      deadlineRef.current = Date.now() + POLL_TIMEOUT_MS;
      setPollTimedOut(false);
    }

    const id = window.setInterval(() => {
      if (deadlineRef.current !== null && Date.now() > deadlineRef.current) {
        window.clearInterval(id);
        deadlineRef.current = null;
        setPollTimedOut(true);
        return;
      }
      refresh();
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(id);
  }, [inFlightCount, refresh]);

  // ─── Ingest ───────────────────────────────────────────────────────────────
  // Both entry points share a tail: splice the accepted items in optimistically
  // so they appear as in-progress immediately, and surface `skipped` as warnings
  // rather than errors. Partial success is the normal case — several files can
  // land while one is rejected, and the request still returns 202.

  const applyIngestResult = useCallback(
    (accepted: ItemOut[], skipped: string[]) => {
      setItems((prev) => [...accepted, ...prev]);
      setWarnings(skipped);
      setTotal((prev) => prev + accepted.length);
    },
    [],
  );

  const runIngest = useCallback(
    async (call: () => Promise<{ items: ItemOut[]; skipped: string[] }>) => {
      setIsIngesting(true);
      setError(null);
      setWarnings([]);
      try {
        const data = await call();
        applyIngestResult(data.items, data.skipped);
        return true;
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
          // A 422 means nothing was ingestable, but it still itemizes why.
          if (err.skipped.length) setWarnings(err.skipped);
        } else {
          setError("Couldn't add that. Try again.");
        }
        return false;
      } finally {
        setIsIngesting(false);
      }
    },
    [applyIngestResult],
  );

  // One entry point, because the API now takes text, files and urls in a single
  // multipart request. Whatever the form has filled in goes up together.
  const addSources = useCallback(
    (input: { text?: string; title?: string; files?: File[]; urls?: string[] }) =>
      runIngest(() => ingest(input)),
    [runIngest],
  );

  // ─── Mutations ────────────────────────────────────────────────────────────

  const remove = useCallback(async (itemId: string) => {
    // Drop it locally first — the server rebuilds the index synchronously
    // before responding, so the refresh that follows reports a settled count.
    setItems((prev) => prev.filter((i) => i.id !== itemId));
    setSelectedIds((prev) => prev.filter((id) => id !== itemId));
    try {
      await deleteItem(itemId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't remove that source.");
    } finally {
      refresh();
    }
  }, [refresh]);

  const toggleSelected = useCallback((itemId: string) => {
    setSelectedIds((prev) =>
      prev.includes(itemId) ? prev.filter((id) => id !== itemId) : [...prev, itemId],
    );
  }, []);

  const clearSelection = useCallback(() => setSelectedIds([]), []);
  const dismissWarnings = useCallback(() => setWarnings([]), []);

  return useMemo(
    () => ({
      items,
      total,
      indexedChunks,
      isLoading,
      isIngesting,
      error,
      warnings,
      selectedIds,
      pollTimedOut,
      isIndexing: inFlightCount > 0,
      isEmpty: !isLoading && items.length === 0,
      refresh,
      addSources,
      remove,
      toggleSelected,
      clearSelection,
      dismissWarnings,
    }),
    [
      items, total, indexedChunks, isLoading, isIngesting, error, warnings,
      selectedIds, pollTimedOut, inFlightCount, refresh, addSources,
      remove, toggleSelected, clearSelection, dismissWarnings,
    ],
  );
}

export type LibraryStore = ReturnType<typeof useLibraryStore>;