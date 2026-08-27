import { useEffect, useRef, useState } from "react";
import { useChat } from "../context/ChatContext";
import { useLibrary } from "../context/LibraryContext";
import { Answer } from "./Answer";
import { SourceList } from "./SourceList";
import { Button } from "./primitives";
import type { ChatMessage, Source } from "../types";

function Turn({
  message,
  onCite,
}: {
  message: ChatMessage;
  onCite: (s: Source) => void;
}) {
  if (message.role === "user") {
    return (
      <div className="border-l-2 border-ink pl-4">
        <p className="font-body text-[18px] leading-snug">{message.content}</p>
      </div>
    );
  }

  const missed = message.ragHit === false;

  return (
    <div className="pl-4">
      {missed ? (
        <div className="rounded-sm border border-dashed border-rule bg-card px-4 py-3">
          <p className="eyebrow mb-1.5">No matching passages</p>
          <p className="font-body text-[15px] leading-relaxed text-slate">
            {message.content}
          </p>
          <p className="mt-2 text-[12px] text-slate">
            Try different wording, widen the search by unchecking sources, or add
            a source that covers this.
          </p>
        </div>
      ) : (
        <Answer
          content={message.content}
          sources={message.sources ?? []}
          onCite={onCite}
        />
      )}

      <SourceList sources={message.sources ?? []} onOpen={onCite} />

      <p className="mt-3 flex flex-wrap gap-x-3 font-mono text-[10px] text-slate">
        {message.model && <span>{message.model}</span>}
        {message.latencyMs != null && <span>{message.latencyMs} ms</span>}
        {!!message.totalTokens && <span>{message.totalTokens} tokens</span>}
      </p>
    </div>
  );
}

export function Ask({ onCite }: { onCite: (s: Source) => void }) {
  const { messages, isLoading, error, send, cancel, topK, setTopK, resetConversation } =
    useChat();
  const { indexedChunks, selectedIds, items, isLoading: libraryLoading } = useLibrary();

  const [draft, setDraft] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isLoading]);

  const knowledgeBaseEmpty = !libraryLoading && indexedChunks === 0;
  const canSend = draft.trim().length > 0 && !isLoading && !knowledgeBaseEmpty;

  function submit() {
    if (!canSend) return;
    send(draft);
    setDraft("");
  }

  const scopeLabel =
    selectedIds.length > 0
      ? `${selectedIds.length} of ${items.length} sources`
      : `all ${indexedChunks} chunks`;

  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <div className="scroll-quiet min-h-0 flex-1 overflow-y-auto px-6 py-6 lg:px-10">
        {messages.length === 0 && (
          <div className="mx-auto max-w-[46ch] pt-12">
            <p className="eyebrow mb-3">Ask</p>
            <h2 className="font-body text-[28px] leading-[1.25] text-ink">
              Every answer here comes back with the exact passages it was built
              from.
            </h2>
            <p className="mt-3 text-[13px] leading-relaxed text-slate">
              {knowledgeBaseEmpty
                ? "Add a source first — there's nothing indexed to answer from yet."
                : "Click any citation to see it highlighted in the original document."}
            </p>
          </div>
        )}

        <div className="mx-auto max-w-[68ch] space-y-8">
          {messages.map((m) => (
            <Turn key={m.id} message={m} onCite={onCite} />
          ))}

          {isLoading && (
            <div className="pl-4">
              <p className="eyebrow animate-pulse">Retrieving and answering…</p>
            </div>
          )}

          {error && (
            <div className="pl-4">
              <p className="text-[13px] text-flag">{error}</p>
            </div>
          )}
        </div>

        <div ref={bottom} />
      </div>

      <div className="border-t border-rule bg-card px-6 py-4 lg:px-10">
        <div className="mx-auto max-w-[68ch]">
          <div className="flex items-end gap-2">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              rows={2}
              maxLength={4000}
              disabled={knowledgeBaseEmpty}
              placeholder={
                knowledgeBaseEmpty
                  ? "Add a source to start asking"
                  : "Ask about your sources…"
              }
              className="scroll-quiet w-full resize-none rounded-sm border border-rule bg-paper px-3 py-2.5 font-body text-[15px] leading-snug text-ink placeholder:text-slate/70 focus:border-ink/40 focus:outline-none disabled:opacity-50"
            />
            {isLoading ? (
              <Button variant="quiet" onClick={cancel}>
                Stop
              </Button>
            ) : (
              <Button onClick={submit} disabled={!canSend}>
                Ask
              </Button>
            )}
          </div>

          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 font-mono text-[10px] text-slate">
            <span>searching {scopeLabel}</span>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5">
                <span>passages</span>
                <select
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  className="rounded-[2px] border border-rule bg-paper px-1 py-0.5 font-mono text-[10px]"
                >
                  {[3, 5, 8, 12, 20].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              {messages.length > 0 && (
                <button
                  onClick={resetConversation}
                  className="underline underline-offset-2 hover:text-ink"
                >
                  new conversation
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
