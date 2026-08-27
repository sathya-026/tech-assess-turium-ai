import { useMemo, useRef, useState } from "react";
import { useLibrary } from "../context/LibraryContext";
import { Button, Field, inputClass } from "./primitives";

type Panel = "note" | "links" | "files";

const PANELS: { id: Panel; label: string }[] = [
  { id: "note", label: "Note" },
  { id: "links", label: "Links" },
  { id: "files", label: "Files" },
];

/** One per line or comma separated. Bare domains are fine — the server
 *  normalizes them to https. */
function parseUrls(raw: string): string[] {
  return raw
    .split(/[\n,]/)
    .map((u) => u.trim())
    .filter(Boolean);
}

export function AddSource() {
  const { addSources, isIngesting, warnings, dismissWarnings, error } = useLibrary();

  const [panel, setPanel] = useState<Panel>("note");
  const [text, setText] = useState("");
  const [urlText, setUrlText] = useState("");
  const [title, setTitle] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const urls = useMemo(() => parseUrls(urlText), [urlText]);
  const hasText = text.trim().length > 0;

  // Everything filled in goes up in one request, whichever panel is showing.
  // The button spells out what that is, so switching tabs never hides
  // something that is about to be submitted.
  const pending = [
    hasText ? "1 note" : null,
    files.length ? `${files.length} ${files.length === 1 ? "file" : "files"}` : null,
    urls.length ? `${urls.length} ${urls.length === 1 ? "link" : "links"}` : null,
  ].filter(Boolean) as string[];

  const canSubmit = !isIngesting && pending.length > 0;

  async function submit() {
    if (!canSubmit) return;
    const ok = await addSources({
      ...(hasText ? { text } : {}),
      ...(files.length ? { files } : {}),
      ...(urls.length ? { urls } : {}),
      ...(title.trim() ? { title } : {}),
    });

    if (ok) {
      setText("");
      setUrlText("");
      setTitle("");
      setFiles([]);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  return (
    <section className="border-b border-rule px-5 py-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="eyebrow">Add a source</h2>
        <div className="flex gap-px rounded-sm border border-rule bg-card p-px">
          {PANELS.map((p) => (
            <button
              key={p.id}
              onClick={() => setPanel(p.id)}
              aria-pressed={panel === p.id}
              className={`px-2.5 py-1 text-[11px] font-medium transition-colors ${
                panel === p.id ? "bg-ink text-paper" : "text-slate hover:text-ink"
              } cursor-pointer`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        {panel === "note" && (
          <Field label="Text">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={5}
              placeholder="Paste anything you want to be able to ask about."
              className={`${inputClass} resize-y font-body text-[15px] leading-relaxed`}
            />
          </Field>
        )}

        {panel === "links" && (
          <Field
            label="Addresses"
            hint="One per line. Pages are fetched and read on the server."
          >
            <textarea
              value={urlText}
              onChange={(e) => setUrlText(e.target.value)}
              rows={4}
              spellCheck={false}
              placeholder={"example.com/docs\nhttps://another.site/post"}
              className={`${inputClass} resize-y font-mono text-[12px] leading-relaxed`}
            />
          </Field>
        )}

        {panel === "files" && (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              setFiles(Array.from(e.dataTransfer.files));
            }}
            className={`rounded-sm border border-dashed px-4 py-6 text-center transition-colors ${
              dragging ? "border-mark-deep bg-mark/15" : "border-rule bg-card"
            }`}
          >
            <input
              ref={fileInput}
              type="file"
              multiple
              onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
              className="hidden"
              id="file-input"
            />
            {files.length === 0 ? (
              <>
                <p className="text-[13px] text-slate">
                  Drop files here, or{" "}
                  <label
                    htmlFor="file-input"
                    className="cursor-pointer font-medium text-ink underline underline-offset-2"
                  >
                    browse
                  </label>
                </p>
                <p className="mt-1.5 font-mono text-[10px] text-slate/80">
                  txt md rst csv json log html pdf docx · 10 MB each
                </p>
              </>
            ) : (
              <ul className="space-y-1 text-left">
                {files.map((f) => (
                  <li key={f.name} className="truncate font-mono text-[11px] text-ink">
                    {f.name}
                  </li>
                ))}
                <li>
                  <button
                    onClick={() => {
                      setFiles([]);
                      if (fileInput.current) fileInput.current.value = "";
                    }}
                    className="mt-1 text-[11px] text-slate underline underline-offset-2 hover:text-ink"
                  >
                    Clear
                  </button>
                </li>
              </ul>
            )}
          </div>
        )}

        <Field label="Title" hint="Optional. Named from the content if left blank.">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={inputClass}
            placeholder="—"
          />
        </Field>

        <Button onClick={submit} disabled={!canSubmit} className="w-full">
          {isIngesting
            ? "Adding…"
            : pending.length
              ? `Add ${pending.join(" + ")}`
              : "Add to library"}
        </Button>

        {error && <p className="text-[12px] text-flag">{error}</p>}

        {warnings.length > 0 && (
          <div className="rounded-sm border border-rule bg-card p-2.5">
            <div className="mb-1.5 flex items-start justify-between gap-2">
              <span className="eyebrow">
                {warnings.length === 1
                  ? "1 source skipped"
                  : `${warnings.length} sources skipped`}
              </span>
              <button
                onClick={dismissWarnings}
                className="text-[11px] text-slate hover:text-ink"
              >
                Dismiss
              </button>
            </div>
            <ul className="space-y-1">
              {warnings.map((w) => (
                <li key={w} className="font-mono text-[11px] leading-snug text-slate">
                  {w}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}