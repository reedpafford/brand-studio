import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { fileUrl } from "../api/upload";

/** A small grey tag beside a card's name ("Uploaded", "Real photo", "Archived"). */
export const Tag = ({ children }: { children: ReactNode }) => (
  <span className="inline-flex h-5 shrink-0 items-center rounded-sm bg-surface-2 px-1.5 text-[11px] font-semibold text-muted">{children}</span>
);

/** A picture filling its box, or an empty grey box. */
export function Picture({ id, alt, className = "" }: { id?: number | null; alt: string; className?: string }) {
  return id ? (
    <img src={fileUrl(id)} alt={alt} className={`rounded-md bg-surface-2 object-cover ${className}`} />
  ) : (
    <span aria-hidden className={`block rounded-md border border-dashed border-border-strong bg-surface-2 ${className}`} />
  );
}

/** One saved item as a card (S8-01, S8-04, S8-06, P-13): its picture, its name with a tag, and a quiet line. `size`
 *  sets the desktop picture; on a phone the cards are two to a row. */
export function LibraryCard({ to, picture, name, tag, line, faded, size, width = "", children }: { to?: string; picture: ReactNode; name: string; tag?: string; line?: ReactNode; faded?: boolean; size: string; /** The card's desktop width, so its words wrap under the picture. */ width?: string; children?: ReactNode }) {
  const body = (
    <>
      <span className={`block ${size}`}>{picture}</span>
      <span className="mt-2 flex items-center gap-2">
        <span className="min-w-0 truncate font-semibold">{name}</span>
        <span className="flex-1" />
        {tag && <Tag>{tag}</Tag>}
      </span>
    </>
  );
  return (
    <li className={`flex min-w-0 flex-col ${width} ${faded ? "opacity-60" : ""}`}>
      {to ? (
        <Link to={to} aria-label={name} className="block rounded-md focus-visible:outline-2">
          {body}
        </Link>
      ) : (
        body
      )}
      {line && <span className="mt-1 text-xs text-muted">{line}</span>}
      {children}
    </li>
  );
}
