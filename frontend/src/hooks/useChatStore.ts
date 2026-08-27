// isLoading, error, send, cancel — but POST /query blocks until the full
// answer is ready, so there's no SSE reader and no token-by-token append.
// The assistant message arrives complete, with its sources attached.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { askQuestion } from "../api/endpoints";
import { ApiError } from "../api/client";
import {
  getOrCreateSessionId,
  readTranscript,
  rotateSessionId,
  storeTranscript,
} from "../session";
import type { ChatMessage } from "../types";

interface UseChatStoreOptions {
  /** Checked items from the library. Empty means search everything. */
  itemIds: string[];
}

export function useChatStore({ itemIds }: UseChatStoreOptions) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [topK, setTopK] = useState(5);

  const abortRef = useRef<AbortController | null>(null);

  // Session id and transcript resolve together on mount. Restoring one without
  // the other would desync what the server remembers from what the user sees.
  useEffect(() => {
    const sid = getOrCreateSessionId();
    setSessionId(sid);
    setMessages(readTranscript(sid));
  }, []);

  useEffect(() => {
    if (sessionId) storeTranscript(sessionId, messages);
  }, [sessionId, messages]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsLoading(false);
  }, []);

  const send = useCallback(
    async (text: string) => {
      const question = text.trim();
      if (!question || isLoading || !sessionId) return;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setError(null);

      const userMsgId = `u_${Date.now()}`;
      setMessages((prev) => [...prev, { id: userMsgId, role: "user", content: question }]);
      setIsLoading(true);

      try {
        const data = await askQuestion(
          {
            question,
            session_id: sessionId,
            top_k: topK,
            // Omit entirely when nothing is checked — an empty array would be a
            // request to search zero items rather than to search all of them.
            ...(itemIds.length ? { item_ids: itemIds } : {}),
          },
          controller.signal,
        );

        setMessages((prev) => [
          ...prev,
          {
            id: `a_${Date.now()}`,
            role: "assistant",
            content: data.answer,
            sources: data.sources,
            ragHit: data.rag_hit,
            model: data.model,
            totalTokens: data.total_tokens,
            latencyMs: data.latency_ms,
          },
        ]);
        setConversationId(data.conversation_id);
      } catch (err) {
        // A newer send aborted this one. The older question still belongs in
        // the transcript, so leave it standing rather than rolling it back.
        if ((err as Error).name === "AbortError") return;

        setError(
          err instanceof ApiError ? err.message : "Something went wrong. Try again.",
        );
        setMessages((prev) => prev.filter((m) => m.id !== userMsgId));
      } finally {
        // Only the request that still owns the ref may clear the flag —
        // otherwise a superseded request turns off the spinner for its successor.
        if (abortRef.current === controller) setIsLoading(false);
      }
    },
    [isLoading, sessionId, topK, itemIds],
  );

  /** Start over: new session id server-side, cleared transcript client-side. */
  const resetConversation = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    const fresh = rotateSessionId(sessionId);
    setSessionId(fresh);
    setMessages([]);
    setConversationId(null);
    setError(null);
    setIsLoading(false);
  }, [sessionId]);

  return useMemo(
    () => ({
      sessionId,
      messages,
      isLoading,
      error,
      conversationId,
      topK,
      setTopK,
      send,
      cancel,
      resetConversation,
    }),
    [sessionId, messages, isLoading, error, conversationId, topK, send, cancel, resetConversation],
  );
}

export type ChatStore = ReturnType<typeof useChatStore>;
