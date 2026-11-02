import type { ReactNode } from "react";

/** A page's top (v5 A_Shell, item 7): a 52 px bar across the page with the title left, a quiet line beside it, and the
 *  page's presses on the right, over one hairline. It sits flush with the page's edges (its page pads p-4 sm:p-6).
 *  On a phone the line goes under the title and the presses wrap. */
export function PageTop({ title, line, eyebrow, children }: { title: string; line?: ReactNode; eyebrow?: ReactNode; children?: ReactNode }) {
  return (
    <header className="-mx-4 -mt-4 flex min-h-13 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-border px-4 py-2 sm:-mx-6 sm:-mt-6 sm:px-6">
      <div className="min-w-0">
        {eyebrow && <p className="type-eyebrow text-muted">{eyebrow}</p>}
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <h1 className="font-display text-xl font-semibold tracking-tight">{title}</h1>
          {line && <p className="text-sm tabular-nums text-muted">{line}</p>}
        </div>
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </header>
  );
}
