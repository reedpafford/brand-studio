import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode, type Ref } from "react";
import { createPortal } from "react-dom";
import { Check } from "lucide-react";

type ButtonProps = { ref: Ref<HTMLButtonElement>; onClick: () => void; "aria-haspopup": "menu"; "aria-expanded": boolean };

/** The studio's one menu. It opens from its button, under it (above when there is no room below); Escape closes it and
 *  puts focus back on the button, a click outside closes it, the arrow keys move through it. On a phone it comes up
 *  from the bottom as a sheet (studio.css). `children` gets `close`, for a choice that closes the menu. */
export function Popover({ label, button, children }: { label: string; button: (p: ButtonProps) => ReactNode; children: (close: () => void) => ReactNode }) {
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<HTMLButtonElement | null>(null);
  const menu = useRef<HTMLDivElement>(null);
  const close = useCallback(() => {
    setOpen(false);
    anchor?.focus();
  }, [anchor]);

  useLayoutEffect(() => {
    const m = menu.current;
    if (!open || !m || !anchor) return;
    const r = anchor.getBoundingClientRect();
    const below = r.bottom + 6 + m.offsetHeight < innerHeight - 8 || r.top < m.offsetHeight + 14;
    m.style.left = `${Math.max(8, Math.min(innerWidth - m.offsetWidth - 8, r.left))}px`;
    m.style.top = `${below ? r.bottom + 6 : r.top - m.offsetHeight - 6}px`;
    m.classList.toggle("above", !below);
    (m.querySelector<HTMLElement>("[aria-checked='true']") ?? m.querySelector<HTMLElement>("button, a, input"))?.focus({ preventScroll: true });
  }, [open, anchor]);

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => !menu.current?.contains(e.target as Node) && !anchor?.contains(e.target as Node) && setOpen(false);
    const shut = () => setOpen(false);
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation(); // caught on the way down: a dialog the menu sits in stays open
        close();
      } else if (e.key === "Tab") {
        close(); // Tab then carries on from the button
      } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const items = [...(menu.current?.querySelectorAll<HTMLElement>("button:not(:disabled), a, input") ?? [])];
        const at = items.indexOf(document.activeElement as HTMLElement);
        items[(at + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length]?.focus();
      }
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", key, true);
    window.addEventListener("resize", shut);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", key, true);
      window.removeEventListener("resize", shut);
    };
  }, [open, anchor, close]);

  return (
    <>
      {button({ ref: setAnchor, onClick: () => setOpen(!open), "aria-haspopup": "menu", "aria-expanded": open })}
      {open &&
        createPortal(
          <div ref={menu} role="menu" aria-label={label} className="studio popv">
            {children(close)}
          </div>,
          document.body,
        )}
    </>
  );
}

/** One choice in a menu: what leads it (a colour, a picture), its name, a line under it, and a tick when it is the one picked. */
export function Choice({ checked, lead, note, onPick, children }: { checked: boolean; lead?: ReactNode; note?: string; onPick: () => void; children: ReactNode }) {
  return (
    <button type="button" role="menuitemradio" aria-checked={checked} onClick={onPick}>
      {lead}
      <span className="ol">
        <b>{children}</b>
        {note && <small>{note}</small>}
      </span>
      <Check size={14} strokeWidth={1.75} aria-hidden className="tick" />
    </button>
  );
}
