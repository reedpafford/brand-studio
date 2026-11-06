import type { ReactNode } from "react";

/** Before there's anything to show: the empty frames and what will fill them (S3-01). */
export function Empty({ title, children, action }: { title: string; children: string; action?: ReactNode }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 py-16 text-center">
      <div aria-hidden className="flex gap-2">
        {[0, 1, 2].map((i) => (
          <span key={i} className="h-[114px] w-16 rounded-md border border-dashed border-border-strong bg-surface-2" />
        ))}
      </div>
      <p className="text-lg font-semibold">{title}</p>
      <p className="max-w-[340px] text-sm text-muted">{children}</p>
      {action}
    </div>
  );
}
export const SOON = "The director writes a treatment, then the scenes fill in with stills and clips as they’re made. The cut plays here when it’s ready.";
