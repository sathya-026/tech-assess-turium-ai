// Fetches and caches an item's full raw_text so a citation can be shown in
// context. Cached per item id rather than per citation — raw_text can be large
// and several sources routinely point into the same document.

import { useCallback, useRef, useState } from "react";
import { getItem } from "../api/endpoints";
import { ApiError } from "../api/client";

export function useDocumentCache() {
  const cache = useRef(new Map<string, string>());
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (itemId: string): Promise<string | null> => {
    const hit = cache.current.get(itemId);
    if (hit !== undefined) return hit;

    setLoadingId(itemId);
    setError(null);
    try {
      const detail = await getItem(itemId);
      cache.current.set(itemId, detail.raw_text);
      return detail.raw_text;
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 404
          ? "That source has been removed."
          : "Couldn't open that source.",
      );
      return null;
    } finally {
      setLoadingId(null);
    }
  }, []);

  const peek = useCallback((itemId: string) => cache.current.get(itemId), []);

  const evict = useCallback((itemId: string) => {
    cache.current.delete(itemId);
  }, []);

  return { load, peek, evict, loadingId, error };
}
