import type { ReactNode } from "react";

/** Before there's anything to show: the empty frames and what will fill them (S3-01). `busy`: it is being made right
 *  now, so the frames catch the light one after another (never a still page while the director works). */
export function Empty({ title, children, action, busy }: { title: string; children: string; action?: ReactNode; busy?: boolean }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 py-16 text-center">
      <div aria-hidden className="flex gap-2">
        {[0, 1, 2].map((i) => (
          <span key={i} style={busy ? { animationDelay: `${i * 220}ms` } : undefined} className={`h-[114px] w-16 rounded-md border border-dashed border-border-strong ${busy ? "shimmer" : "bg-surface-2"}`} />
        ))}
      </div>
      <p className="text-lg font-semibold">{title}</p>
      <p className="max-w-[340px] text-sm text-muted">{children}</p>
      {action}
    </div>
  );
}
export const SOON = "The director writes a treatment, then the scenes fill in with stills and clips as they’re made. The cut plays here when it’s ready.";
