import { Children, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Source } from "../types";

const CITATION = /\[(\d+)\]/g;

/**
 * Turns bare [1] markers in the model's prose into buttons that open the
 * matching source. Only strings are rewritten and only inside the block
 * elements this is wired into — code and pre are left untouched, so a literal
 * [0] inside a code sample stays a literal.
 */
function linkify(
  children: ReactNode,
  ranks: Set<number>,
  onCite: (rank: number) => void,
): ReactNode {
  return Children.map(children, (child) => {
    if (typeof child !== "string") return child;

    const parts: ReactNode[] = [];
    let cursor = 0;
    let match: RegExpExecArray | null;
    CITATION.lastIndex = 0;

    while ((match = CITATION.exec(child)) !== null) {
      const rank = Number(match[1]);
      if (!ranks.has(rank)) continue;

      if (match.index > cursor) parts.push(child.slice(cursor, match.index));
      parts.push(
        <button
          key={`${match.index}-${rank}`}
          onClick={() => onCite(rank)}
          title={`Open source ${rank}`}
          className="passage-mark mx-px rounded-[2px] font-mono text-[0.78em] font-medium text-ink hover:bg-mark-deep"
        >
          {rank}
        </button>,
      );
      cursor = match.index + match[0].length;
    }

    if (cursor === 0) return child;
    if (cursor < child.length) parts.push(child.slice(cursor));
    return parts;
  });
}

export function Answer({
  content,
  sources,
  onCite,
}: {
  content: string;
  sources: Source[];
  onCite: (source: Source) => void;
}) {
  const ranks = new Set(sources.map((s) => s.rank));
  const byRank = new Map(sources.map((s) => [s.rank, s]));

  const cite = (rank: number) => {
    const source = byRank.get(rank);
    if (source) onCite(source);
  };

  const wrap = (children: ReactNode) => linkify(children, ranks, cite);

  return (
    <div className="font-body text-[16px] leading-[1.65] text-ink">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="mb-3 last:mb-0">{wrap(children)}</p>,
          li: ({ children }) => <li className="mb-1">{wrap(children)}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold">{wrap(children)}</strong>
          ),
          em: ({ children }) => <em className="italic">{wrap(children)}</em>,
          td: ({ children }) => (
            <td className="border border-rule px-2 py-1 align-top">{wrap(children)}</td>
          ),
          th: ({ children }) => (
            <th className="border border-rule bg-card px-2 py-1 text-left font-display text-[12px] font-semibold">
              {children}
            </th>
          ),
          ul: ({ children }) => <ul className="mb-3 list-disc pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="mb-3 list-decimal pl-5">{children}</ol>,
          h1: ({ children }) => (
            <h3 className="mb-2 font-display text-[15px] font-semibold">{children}</h3>
          ),
          h2: ({ children }) => (
            <h3 className="mb-2 font-display text-[15px] font-semibold">{children}</h3>
          ),
          h3: ({ children }) => (
            <h4 className="mb-2 font-display text-[14px] font-semibold">{children}</h4>
          ),
          code: ({ children }) => (
            <code className="rounded-[3px] bg-card px-1 py-px font-mono text-[0.82em]">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="scroll-quiet mb-3 overflow-x-auto rounded-sm border border-rule bg-card p-3 font-mono text-[12px] leading-relaxed">
              {children}
            </pre>
          ),
          table: ({ children }) => (
            <div className="scroll-quiet mb-3 overflow-x-auto">
              <table className="w-full border-collapse text-[14px]">{children}</table>
            </div>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-2"
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
