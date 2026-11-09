import type { ReactNode } from "react";

/** The grey track and its picked segment (site polish): Paste / Saved script / Reel, Chat / Preview, a phone's tabs.
 *  The picked one lifts onto white; the change is a short fade, never a jump. */
export const segTrack = "inline-flex gap-0.5 rounded-lg bg-surface-2 p-0.5";
export const segItem = (on: boolean) =>
  `inline-flex h-control lg:h-7 shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-3 text-sm font-medium transition-[background-color,color,box-shadow] duration-(--dur-fast) ease-out ${on ? "bg-surface text-text shadow-soft" : "text-muted hover:text-text"}`;

/** Tabs as a segmented control. `fill`: the segments share the width (a phone). */
export function Segmented<T extends string>({ label, items, value, onChange, fill, className = "" }: { label: string; items: { id: T; name: ReactNode }[]; value: T; onChange: (id: T) => void; fill?: boolean; className?: string }) {
  return (
    <div role="tablist" aria-label={label} className={`${segTrack} ${fill ? "flex w-full" : ""} ${className}`}>
      {items.map((t) => (
        <button key={t.id} type="button" role="tab" aria-selected={t.id === value} onClick={() => onChange(t.id)} className={`${segItem(t.id === value)} ${fill ? "flex-1" : ""}`}>
          {t.name}
        </button>
      ))}
    </div>
  );
}

/** A setting shown as a chip, "Style House" (New video's box, the video's header): its name muted, its value in the text colour. */
export const chipClass =
  "inline-flex h-control lg:h-7 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md border border-border-button bg-surface px-2.5 text-xs font-medium text-text transition-[background-color,border-color] duration-(--dur-fast) ease-out";
/** …and one that opens a menu. */
export const chipPress = `${chipClass} hover:border-border-strong/50 hover:bg-surface-2 aria-expanded:border-accent-line aria-expanded:bg-accent-soft aria-expanded:text-accent-text`;
