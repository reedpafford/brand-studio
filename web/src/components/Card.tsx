import { Play } from "lucide-react";
import type { ComponentType, ReactNode } from "react";

/** A panel: 16 padding on phones, 20 from sm, a hairline edge in dark mode. */
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-lg border border-border bg-surface p-4 shadow-card sm:p-5 ${className}`}>{children}</div>;
}

/** Media first: the picture leads, the title sits on it over the shade, the status badge is top left. */
export function MediaCard({
  title,
  meta,
  badge,
  image,
  video,
  playable,
  aspect = "9 / 16",
  icon: Icon,
  onOpen,
  children,
}: {
  title: string;
  meta?: ReactNode;
  badge?: ReactNode;
  /** The picture's address; without one a placeholder panel shows. */
  image?: string | null;
  /** Or a video file: its first frame is the picture. */
  video?: string | null;
  /** A play button shows only on things that play. */
  playable?: boolean;
  aspect?: string;
  /** What kind of thing this is: shown in the middle when there is no picture. */
  icon?: ComponentType<{ size?: number; strokeWidth?: number; "aria-hidden"?: boolean; className?: string }>;
  onOpen?: () => void;
  children?: ReactNode;
}) {
  const media = (
    <>
      {video ? (
        <>
          <video src={`${video}#t=0.1`} muted playsInline preload="metadata" aria-hidden className="absolute inset-0 size-full object-cover" />
          <span className="absolute inset-0 bg-(image:--media-shade)" aria-hidden />
        </>
      ) : image ? (
        <>
          <img src={image} alt="" className="absolute inset-0 size-full object-cover" />
          <span className="absolute inset-0 bg-(image:--media-shade)" aria-hidden />
        </>
      ) : (
        <span className="absolute inset-0 grid place-items-center bg-surface-2 text-muted" aria-hidden>
          {Icon && <Icon size={24} strokeWidth={1.75} aria-hidden />}
        </span>
      )}
      {badge && <span className="absolute left-3 top-3">{badge}</span>}
      {playable && (
        <span className="absolute left-1/2 top-1/2 grid size-12 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-scrim text-on-media">
          <Play size={20} strokeWidth={1.75} aria-hidden />
        </span>
      )}
      <span className={`absolute inset-x-3 bottom-3 text-left ${image || video ? "text-on-media" : "text-text"}`}>
        <span className="block font-display text-md font-bold">{title}</span>
        {meta && <span className={`block text-sm ${image || video ? "" : "text-muted"}`}>{meta}</span>}
      </span>
    </>
  );
  return (
    <div className="flex flex-col gap-3">
      {onOpen ? (
        <button type="button" onClick={onOpen} aria-label={title} className="relative block w-full overflow-hidden rounded-lg border border-border bg-surface-2 shadow-card" style={{ aspectRatio: aspect }}>
          {media}
        </button>
      ) : (
        <div className="relative w-full overflow-hidden rounded-lg border border-border bg-surface-2 shadow-card" style={{ aspectRatio: aspect }}>
          {media}
        </div>
      )}
      {children}
    </div>
  );
}
