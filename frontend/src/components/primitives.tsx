import type { ItemStatus } from "../types";

export function Button({
  children,
  variant = "solid",
  className = "",
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "solid" | "quiet" | "ghost" }) {
  const base =
    "inline-flex items-center justify-center gap-1.5 rounded-sm px-3 py-2 text-[13px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40";
  const variants = {
    solid: "bg-ink text-paper hover:bg-ink/85",
    quiet: "border border-rule bg-card text-ink hover:border-ink/40",
    ghost: "text-slate hover:text-ink",
  };
  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...rest}>
      {children}
    </button>
  );
}

export function StatusDot({ status }: { status: ItemStatus }) {
  const map: Record<ItemStatus, string> = {
    pending: "bg-slate/40",
    indexing: "bg-mark-deep animate-pulse",
    indexed: "bg-mark-deep",
    failed: "bg-flag",
  };
  return (
    <span
      aria-hidden
      className={`inline-block size-1.5 shrink-0 rounded-full ${map[status]}`}
    />
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="eyebrow mb-1.5 block">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-slate">{hint}</span>}
    </label>
  );
}

export const inputClass =
  "w-full rounded-sm border border-rule bg-card px-2.5 py-2 text-[13px] text-ink placeholder:text-slate/60 focus:border-ink/40 focus:outline-none";

export function formatBytes(chars: number) {
  if (chars < 1000) return `${chars} chars`;
  return `${(chars / 1000).toFixed(chars < 10_000 ? 1 : 0)}k chars`;
}

export function formatWhen(iso: string) {
  const then = new Date(iso).getTime();
  const mins = Math.round((Date.now() - then) / 60_000);
  if (Number.isNaN(mins)) return "";
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.round(mins / 60)}h ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
