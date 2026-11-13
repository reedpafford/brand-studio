import { useRef, useState, type CSSProperties, type ReactNode } from "react";

const KEY = "bs.split";
const CHAT = 320; // the least the chat keeps
const FILM = 440; // the least the film keeps
const BAR = 9;

/** A video's two sides, the chat and the film, with a divider between them. Drag it, move it with the arrow keys,
 *  double-click to put it back; where it is left is remembered on this computer, and each side keeps a least width.
 *  A phone stacks the two, the film first unless `first` says the chat (video.css). */
export function Split({ first, chat, film }: { first: "chat" | "film"; chat: ReactNode; film: ReactNode }) {
  const wrap = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const [width, setWidth] = useState<number | null>(() => {
    try {
      return Number(localStorage.getItem(KEY)) || null;
    } catch {
      return null; // private mode: where the design puts it
    }
  });
  const move = (px: number | null) => {
    const to = px == null ? null : Math.round(Math.max(CHAT, Math.min((wrap.current?.clientWidth ?? 0) - FILM - BAR, px)));
    setWidth(to);
    try {
      if (to == null) localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, String(to));
    } catch {
      /* private mode: nothing to remember */
    }
  };
  /** While it is dragged, nothing under the pointer is selected or played (video.css). */
  const drag = (on: boolean) => {
    dragging.current = on;
    wrap.current?.toggleAttribute("data-resizing", on);
  };
  const left = () => wrap.current?.getBoundingClientRect().left ?? 0;
  return (
    <div className="stage-wrap" ref={wrap} style={width ? ({ "--thread": `${width}px` } as CSSProperties) : undefined} data-first={first}>
      {chat}
      <div
        className="split"
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize the chat and the film"
        aria-valuenow={width ?? undefined}
        aria-valuemin={CHAT}
        tabIndex={0}
        title="Drag to resize. Double-click to reset."
        onPointerDown={(e) => {
          e.preventDefault();
          e.currentTarget.setPointerCapture?.(e.pointerId);
          drag(true);
        }}
        onPointerMove={(e) => dragging.current && move(e.clientX - left())}
        onPointerUp={() => drag(false)}
        onPointerCancel={() => drag(false)}
        onDoubleClick={() => move(null)}
        onKeyDown={(e) => {
          if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
          e.preventDefault();
          move(e.currentTarget.getBoundingClientRect().left - left() + (e.key === "ArrowRight" ? 24 : -24));
        }}
      >
        <i />
      </div>
      {film}
    </div>
  );
}
