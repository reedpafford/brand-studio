import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode, type Ref } from "react";
import { createPortal } from "react-dom";
import { Check } from "lucide-react";

export type ButtonProps = { ref: Ref<HTMLButtonElement>; onClick: () => void; "aria-haspopup": "menu" | "dialog"; "aria-expanded": boolean };

/** The studio's one menu. It opens from its button, under it (above when there is no room below); Escape closes it and
 *  puts focus back on the button, a click outside closes it, the arrow keys move through it. On a phone it comes up
 *  from the bottom as a sheet (studio.css). `children` gets `close`, for a choice that closes the menu. `end`: its right
 *  edge under the button's, for a button at the right of the page. `facts`: it holds something to read, not choices. */
export function Popover({ label, end, facts, button, children }: { label: string; end?: boolean; facts?: boolean; button: (p: ButtonProps) => ReactNode; children: (close: () => void) => ReactNode }) {
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
    m.style.left = `${Math.max(8, Math.min(innerWidth - m.offsetWidth - 8, end ? r.right - m.offsetWidth : r.left))}px`;
    const top = below ? r.bottom + 6 : r.top - m.offsetHeight - 6;
    m.style.top = `${top}px`;
    // A menu that grows once open (a role opened in Cast) grows down from where it is, so the row just pressed stays
    // under the pointer; it stops at the window's edge and scrolls inside itself from there.
    m.style.setProperty("--room", `${innerHeight - top - 8}px`);
    m.classList.toggle("above", !below);
    (m.querySelector<HTMLElement>("[aria-checked='true']") ?? m.querySelector<HTMLElement>("button, a, input"))?.focus({ preventScroll: true });
  }, [open, anchor, end]);

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
      {button({ ref: setAnchor, onClick: () => setOpen(!open), "aria-haspopup": facts ? "dialog" : "menu", "aria-expanded": open })}
      {open &&
        createPortal(
          <div ref={menu} role={facts ? "dialog" : "menu"} aria-label={label} className="studio popv">
            {children(close)}
          </div>,
          document.body,
        )}
    </>
  );
}

/** One choice in a menu: what leads it (a colour, a picture), its name, a line under it, and a tick when it is the one
 *  picked. `disabled`: one that can't be picked here, its line saying why. */
export function Choice({ checked, disabled, lead, note, onPick, children }: { checked: boolean; disabled?: boolean; lead?: ReactNode; note?: string; onPick: () => void; children: ReactNode }) {
  return (
    <button type="button" role="menuitemradio" aria-checked={checked} disabled={disabled} onClick={onPick}>
      {lead}
      <span className="ol">
        <b>{children}</b>
        {note && <small>{note}</small>}
      </span>
      <Check size={14} strokeWidth={1.75} aria-hidden className="tick" />
    </button>
  );
}
