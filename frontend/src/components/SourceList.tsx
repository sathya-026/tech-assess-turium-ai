import type { Source } from "../types";

function SourceCard({ source, onOpen }: { source: Source; onOpen: () => void }) {
  const pct = Math.round(source.similarity * 100);
  // Similarity is comparable across queries, so it can safely drive emphasis.
  // A weak match is dimmed rather than hidden — the user still needs to see
  // what the model was handed.
  const faded = source.similarity < 0.35;

  return (
    <li className={faded ? "opacity-60" : undefined}>
      <button
        onClick={onOpen}
        className="group block w-full rounded-sm border border-rule bg-card p-3 text-left transition-colors hover:border-ink/35"
      >
        <div className="flex items-baseline gap-2">
          <span className="passage-mark rounded-[2px] px-1 font-mono text-[10px] font-medium">
            {source.rank}
          </span>
          <span className="min-w-0 flex-1 truncate text-[12px] font-medium">
            {source.item_title}
          </span>
          <span className="shrink-0 font-mono text-[10px] text-slate">{pct}%</span>
        </div>

        {source.section_path && (
          <p className="mt-1.5 truncate font-mono text-[10px] text-slate">
            {source.section_path}
          </p>
        )}

        <p className="mt-2 line-clamp-3 font-body text-[13px] leading-snug text-ink/85">
          {source.snippet}
        </p>

        <p className="mt-2 flex items-center gap-2 font-mono text-[10px] text-slate">
          <span>
            {source.char_start}–{source.char_end}
          </span>
          <span className="opacity-0 transition-opacity group-hover:opacity-100">
            open in document →
          </span>
        </p>
      </button>
    </li>
  );
}

export function SourceList({
  sources,
  onOpen,
}: {
  sources: Source[];
  onOpen: (source: Source) => void;
}) {
  if (sources.length === 0) return null;

  return (
    <div className="mt-4">
      <h4 className="eyebrow mb-2">
        Built from {sources.length} {sources.length === 1 ? "passage" : "passages"}
      </h4>
      <ul className="grid gap-2 sm:grid-cols-2">
        {sources.map((s) => (
          <SourceCard key={s.chunk_id} source={s} onOpen={() => onOpen(s)} />
        ))}
      </ul>
    </div>
  );
}
