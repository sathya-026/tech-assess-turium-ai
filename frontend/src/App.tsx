import { useState } from "react";
import { LibraryProvider } from "./context/LibraryContext";
import { ChatProvider } from "./context/ChatContext";
import { AddSource } from "./components/AddSource";
import { Library } from "./components/Library";
import { Ask } from "./components/Ask";
import { Header } from "./components/Header";
import { SourceDrawer } from "./components/SourceDrawer";
import type { Source } from "./types";

function Workspace() {
  const [openSource, setOpenSource] = useState<Source | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(false);

  return (
    <div className="flex h-dvh flex-col bg-paper">
      <Header onToggleLibrary={() => setLibraryOpen((v) => !v)} />

      <div className="flex min-h-0 flex-1">
        {/* Library rail — a drawer on small screens, a fixed column above lg. */}
        <aside
          className={`${
            libraryOpen ? "flex" : "hidden"
          } absolute inset-y-0 left-0 z-30 w-[320px] flex-col border-r border-rule bg-paper lg:relative lg:flex lg:w-[340px]`}
        >
          <AddSource />
          <Library />
        </aside>

        {libraryOpen && (
          <div
            onClick={() => setLibraryOpen(false)}
            className="absolute inset-0 z-20 bg-ink/20 lg:hidden"
            aria-hidden
          />
        )}

        <main className="flex min-w-0 flex-1 flex-col">
          <Ask onCite={setOpenSource} />
        </main>
      </div>

      <SourceDrawer source={openSource} onClose={() => setOpenSource(null)} />
    </div>
  );
}

export default function App() {
  // ChatProvider nests inside LibraryProvider — a query is scoped by whatever
  // is checked in the library, so chat reads from library, never the reverse.
  return (
    <LibraryProvider>
      <ChatProvider>
        <Workspace />
      </ChatProvider>
    </LibraryProvider>
  );
}
