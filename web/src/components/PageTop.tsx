import type { ReactNode } from "react";

/** A library page's top (v4 boards: Brand, Cast & places, Media): the title, a quiet line beside it, and the page's
 *  presses on the right, over one hairline. On a phone the line goes under the title and the presses wrap. */
export function PageTop({ title, line, eyebrow, children }: { title: string; line?: ReactNode; eyebrow?: ReactNode; children?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3 border-b border-border pb-3">
      <div className="min-w-0">
        {eyebrow && <p className="type-eyebrow text-muted">{eyebrow}</p>}
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="type-page">{title}</h1>
          {line && <p className="text-sm text-muted">{line}</p>}
        </div>
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </header>
  );
}
