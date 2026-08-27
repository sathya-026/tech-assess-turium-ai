import { useLibrary } from "../context/LibraryContext";
import { formatBytes, formatWhen, StatusDot } from "./primitives";
import type { ItemOut } from "../types";

function kindLabel(item: ItemOut) {
  if (item.source_type === "url") return "link";
  if (item.source_type === "file") return item.filename?.split(".").pop() ?? "file";
  return "note";
}

function ItemRow({ item }: { item: ItemOut }) {
  const { selectedIds, toggleSelected, remove } = useLibrary();
  const checked = selectedIds.includes(item.id);
  const busy = item.status === "pending" || item.status === "indexing";

  return (
    <li
      className={`group relative px-5 py-3 transition-colors ${
        checked ? "bg-mark/20" : "hover:bg-card"
      }`}
    >
      <div className="flex items-start gap-2.5">
        <input
          type="checkbox"
          checked={checked}
          disabled={item.status !== "indexed"}
          onChange={() => toggleSelected(item.id)}
          aria-label={`Search only ${item.title}`}
          className="mt-1 size-3.5 shrink-0 accent-mark-deep disabled:opacity-25"
        />

        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-medium leading-snug">{item.title}</p>

          {/* A link item is titled with its raw URL until the fetch completes,
              at which point the page's own <title> replaces it. Showing the
              address underneath keeps the row identifiable either way. */}
          {item.source_url && (
            <a
              href={item.source_url}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="mt-0.5 block truncate font-mono text-[10px] text-slate underline underline-offset-2 hover:text-ink"
            >
              {item.source_url.replace(/^https?:\/\//, "")}
            </a>
          )}

          <p className="mt-1 flex items-center gap-1.5 font-mono text-[10px] text-slate">
            <StatusDot status={item.status} />
            <span>{kindLabel(item)}</span>
            {/* char_count is 0 on a link until the page has been fetched —
                reporting "0 chars" there would read as an empty document. */}
            {item.char_count > 0 && (
              <>
                <span aria-hidden>·</span>
                <span>{formatBytes(item.char_count)}</span>
              </>
            )}
            {item.status === "indexed" && (
              <>
                <span aria-hidden>·</span>
                <span>{item.chunk_count} chunks</span>
              </>
            )}
            {busy && (
              <>
                <span aria-hidden>·</span>
                <span>
                  {item.source_type === "url" && item.char_count === 0
                    ? "fetching page"
                    : item.status}
                </span>
              </>
            )}
            <span aria-hidden>·</span>
            <span>{formatWhen(item.created_at)}</span>
          </p>

          {item.status === "failed" && item.error && (
            <p className="mt-1.5 border-l-2 border-flag pl-2 text-[11px] leading-snug text-flag">
              {item.error} Remove it and add it again.
            </p>
          )}
        </div>

        <button
          onClick={() => remove(item.id)}
          aria-label={`Remove ${item.title}`}
          className="shrink-0 px-1 text-[16px] leading-none text-slate opacity-0 transition-opacity hover:text-flag focus-visible:opacity-100 group-hover:opacity-100"
        >
          ×
        </button>
      </div>
    </li>
  );
}

export function Library() {
  const {
    items,
    isLoading,
    isEmpty,
    selectedIds,
    clearSelection,
    pollTimedOut,
    refresh,
  } = useLibrary();

  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-baseline justify-between px-5 pb-2 pt-4">
        <h2 className="eyebrow">
          Library{items.length > 0 && ` · ${items.length}`}
        </h2>
        {selectedIds.length > 0 && (
          <button
            onClick={clearSelection}
            className="font-mono text-[10px] text-slate underline underline-offset-2 hover:text-ink"
          >
            searching {selectedIds.length} of {items.length} — clear
          </button>
        )}
      </div>

      {pollTimedOut && (
        <div className="mx-5 mb-2 rounded-sm border border-rule bg-card p-2.5">
          <p className="text-[11px] leading-snug text-slate">
            Stopped checking for progress after two minutes. The server may have
            restarted mid-index.{" "}
            <button
              onClick={refresh}
              className="font-medium text-ink underline underline-offset-2"
            >
              Check again
            </button>
          </p>
        </div>
      )}

      <div className="scroll-quiet min-h-0 flex-1 overflow-y-auto">
        {isLoading && (
          <p className="px-5 py-3 font-mono text-[11px] text-slate">Loading…</p>
        )}

        {isEmpty && (
          <div className="px-5 py-8">
            <p className="font-body text-[17px] leading-snug text-ink">
              Nothing to search yet.
            </p>
            <p className="mt-1.5 text-[12px] leading-relaxed text-slate">
              Paste a note, drop a file, or point at a link. Questions start
              working as soon as the first source finishes indexing.
            </p>
          </div>
        )}

        <ul className="divide-y divide-rule">
          {items.map((item) => (
            <ItemRow key={item.id} item={item} />
          ))}
        </ul>
      </div>
    </section>
  );
}