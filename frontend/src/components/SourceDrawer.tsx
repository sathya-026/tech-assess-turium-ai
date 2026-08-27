import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useDocumentCache } from "../hooks/useDocumentCache";
import type { Source } from "../types";
import { Button } from "./primitives";

// How much surrounding document to render either side of the passage. The full
// text can be very large, so the default is a window; expanding renders all of it.
const WINDOW = 1400;

export function SourceDrawer({
  source,
  onClose,
}: {
  source: Source | null;
  onClose: () => void;
}) {
  const { load, loadingId, error } = useDocumentCache();
  const [raw, setRaw] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const markRef = useRef<HTMLElement>(null);

  useEffect(() => {
    setExpanded(false);
    if (!source) {
      setRaw(null);
      return;
    }
    let cancelled = false;
    load(source.item_id).then((text) => {
      if (!cancelled) setRaw(text);
    });
    return () => {
      cancelled = true;
    };
  }, [source, load]);

  useEffect(() => {
    if (!source) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [source, onClose]);

  useLayoutEffect(() => {
    if (raw && markRef.current) {
      markRef.current.scrollIntoView({ block: "center", behavior: "auto" });
    }
  }, [raw, expanded]);

  if (!source) return null;

  // Window bounds are computed unconditionally so the expand control knows
  // there is more to show even while it's showing everything — otherwise the
  // control vanishes on expand and there's no way back to the passage view.
  const windowStart = Math.max(0, source.char_start - WINDOW);
  const windowEnd = raw ? Math.min(raw.length, source.char_end + WINDOW) : 0;
  const truncatable = raw ? windowStart > 0 || windowEnd < raw.length : false;

  const start = expanded ? 0 : windowStart;
  const end = raw ? (expanded ? raw.length : windowEnd) : 0;

  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 bg-ink/25 backdrop-blur-[1px]"
        aria-hidden
      />

      <aside
        role="dialog"
        aria-label={`Source ${source.rank} in ${source.item_title}`}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[560px] flex-col border-l border-rule bg-paper shadow-2xl"
      >
        <header className="border-b border-rule px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="eyebrow mb-1">Source {source.rank}</p>
              <h3 className="truncate text-[15px] font-semibold leading-snug">
                {source.item_title}
              </h3>
              {source.section_path && (
                <p className="mt-1 truncate font-mono text-[10px] text-slate">
                  {source.section_path}
                </p>
              )}
            </div>
            <button
              onClick={onClose}
              aria-label="Close"
              className="shrink-0 px-1 text-[20px] leading-none text-slate hover:text-ink"
            >
              ×
            </button>
          </div>

          <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] text-slate">
            <span>
              chars {source.char_start}–{source.char_end}
            </span>
            <span>similarity {source.similarity.toFixed(3)}</span>
            <span>chunk {source.chunk_id}</span>
            {source.filename && <span className="truncate">{source.filename}</span>}
          </p>
        </header>

        <div className="scroll-quiet min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {loadingId === source.item_id && (
            <p className="font-mono text-[11px] text-slate">Opening document…</p>
          )}

          {error && <p className="text-[13px] text-flag">{error}</p>}

          {raw && (
            <>
              {start > 0 && (
                <p className="mb-3 font-mono text-[10px] text-slate">
                  … {start.toLocaleString()} characters above
                </p>
              )}

              <pre className="whitespace-pre-wrap break-words font-body text-[15px] leading-[1.7] text-ink/70">
                {raw.slice(start, source.char_start)}
                <mark ref={markRef} className="passage-mark bg-transparent text-ink">
                  {raw.slice(source.char_start, source.char_end)}
                </mark>
                {raw.slice(source.char_end, end)}
              </pre>

              {end < raw.length && (
                <p className="mt-3 font-mono text-[10px] text-slate">
                  … {(raw.length - end).toLocaleString()} characters below
                </p>
              )}
            </>
          )}
        </div>

        {raw && truncatable && (
          <footer className="border-t border-rule px-5 py-3">
            <Button variant="quiet" onClick={() => setExpanded((v) => !v)} className="w-full">
              {expanded ? "Show just the surrounding passage" : "Show the whole document"}
            </Button>
          </footer>
        )}
      </aside>
    </>
  );
}
