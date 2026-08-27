import { createContext, useContext } from "react";
import { useLibraryStore, type LibraryStore } from "../hooks/useLibraryStore";

const LibraryContext = createContext<LibraryStore | null>(null);

export function LibraryProvider({ children }: { children: React.ReactNode }) {
  const store = useLibraryStore();
  return <LibraryContext.Provider value={store}>{children}</LibraryContext.Provider>;
}

export function useLibrary(): LibraryStore {
  const ctx = useContext(LibraryContext);
  if (!ctx) throw new Error("useLibrary must be used inside <LibraryProvider>");
  return ctx;
}
