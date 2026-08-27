import { createContext, useContext } from "react";
import { useChatStore, type ChatStore } from "../hooks/useChatStore";
import { useLibrary } from "./LibraryContext";

const ChatContext = createContext<ChatStore | null>(null);

/**
 * Must be nested inside <LibraryProvider>. The checked items in the library are
 * what scope a query, so this is the one place the two stores are deliberately
 * wired together — kept visible here rather than hidden inside either hook.
 */
export function ChatProvider({ children }: { children: React.ReactNode }) {
  const { selectedIds } = useLibrary();
  const store = useChatStore({ itemIds: selectedIds });
  return <ChatContext.Provider value={store}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatStore {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used inside <ChatProvider>");
  return ctx;
}
