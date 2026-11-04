import type { ReactNode } from "react";
import { Link } from "react-router-dom";

/** A page's top (v5 A_Shell): a flush 52 px bar with the title (15/600) on the left, a quiet line beside it (a count), and
 *  the page's one primary on the right, over one hairline. It sits flush with the page's edges (its page pads p-4 sm:p-6).
 *  `crumb` puts the page it came from first: "Scripts › Import a reel". On a phone the presses wrap under the title. */
export function PageTop({ title, line, crumb, children }: { title: ReactNode; line?: ReactNode; crumb?: { to: string; label: string }; children?: ReactNode }) {
  const heading = <h1 className="flex min-w-0 items-center gap-2 text-md font-semibold text-text">{title}</h1>;
  return (
    <header className="-mx-4 -mt-4 flex min-h-13 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-border px-4 py-2 sm:-mx-6 sm:-mt-6 sm:px-6">
      <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-0.5">
        {crumb ? (
          <nav aria-label="Breadcrumb" className="flex min-w-0 flex-wrap items-center gap-x-2 text-sm text-muted">
            <Link to={crumb.to} className="inline-flex min-h-control min-w-11 items-center hover:text-text hover:underline lg:min-h-0 lg:min-w-0">
              {crumb.label}
            </Link>
            <span aria-hidden>›</span>
            {heading}
          </nav>
        ) : (
          heading
        )}
        {line && <p className="text-sm tabular-nums text-muted">{line}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </header>
  );
}
