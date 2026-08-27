import { useEffect, useState } from "react";
import { getHealth } from "../api/endpoints";
import { useLibrary } from "../context/LibraryContext";
import type { Health } from "../types";

export function Header({ onToggleLibrary }: { onToggleLibrary: () => void }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [reachable, setReachable] = useState(true);
  const { isIndexing, indexedChunks } = useLibrary();

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then((h) => !cancelled && setHealth(h))
      .catch(() => !cancelled && setReachable(false));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <header className="flex items-center justify-between border-b border-rule px-5 py-3 lg:px-6">
      <div className="flex items-baseline gap-3">
        <h1 className="text-[15px] font-semibold tracking-[-0.02em]">Grounded</h1>
        <span className="hidden font-mono text-[10px] text-slate sm:inline">
          ask your sources, see the receipts
        </span>
      </div>

      <div className="flex items-center gap-4">
        <p className="hidden items-center gap-2 font-mono text-[10px] text-slate md:flex">
          {!reachable ? (
            <span className="text-flag">API unreachable</span>
          ) : (
            <>
              <span
                className={`inline-block size-1.5 rounded-full ${
                  isIndexing ? "animate-pulse bg-mark-deep" : "bg-mark-deep"
                }`}
                aria-hidden
              />
              <span>{indexedChunks} chunks indexed</span>
              {health?.embedding_model && <span>{health.embedding_model}</span>}
            </>
          )}
        </p>

        <button
          onClick={onToggleLibrary}
          className="rounded-sm border border-rule px-2.5 py-1 text-[11px] font-medium lg:hidden"
        >
          Library
        </button>
      </div>
    </header>
  );
}
