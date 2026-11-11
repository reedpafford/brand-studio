import { useEffect, useRef, useState, type ReactNode } from "react";
import { useMedia } from "../useMedia";
import { Sheet } from "./Overlay";
import { useViewOnly } from "./ViewOnly";

/**
 * A menu opened from a button: a popover on desktop, a bottom sheet on a phone.
 * Escape and a tap outside close it; focus goes back to the button. Escape closes the menu alone: a dialog it sits in
 * stays open. `up` opens it above the button (the rail's account row).
 */
export function Menu({ title, trigger, align = "left", up = false, popover = false, children }: { title: string; trigger: (p: { open: boolean; onClick: () => void; "aria-haspopup": "menu"; "aria-expanded": boolean }) => ReactNode; align?: "left" | "right"; up?: boolean; /** a popover on a phone too, not a sheet */ popover?: boolean; children: (close: () => void) => ReactNode }) {
  const phone = useMedia("(max-width: 767px)") && !popover;
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open || phone) return;
    const away = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false);
    const key = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.stopPropagation(); // caught on the way down, before the dialog's own Escape
      setOpen(false);
      root.current?.querySelector<HTMLElement>("[aria-haspopup]")?.focus();
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", key, true);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", key, true);
    };
  }, [open, phone]);
  const close = () => setOpen(false);
  return (
    <div ref={root} className="relative">
      {trigger({ open, onClick: () => setOpen(!open), "aria-haspopup": "menu", "aria-expanded": open })}
      {open && phone && (
        <Sheet title={title} onClose={close}>
          {children(close)}
        </Sheet>
      )}
      {open && !phone && (
        // A long list (many brands) scrolls inside the menu, so its last item (New brand) is always reachable.
        <div role="menu" aria-label={title} className={`animate-pop absolute ${up ? "bottom-full mb-2" : "top-full mt-2"} z-30 max-h-[min(70vh,36rem)] min-w-64 overflow-y-auto overscroll-contain rounded-lg border border-border bg-surface p-1.5 shadow-raised ${align === "right" ? "right-0" : "left-0"}`}>
          {children(close)}
        </div>
      )}
    </div>
  );
}

/** One row in a menu: 44px, icon optional, a check when it is the current choice. */
export function MenuItem({ children, checked, danger, disabled: off, onClick }: { children: ReactNode; checked?: boolean; danger?: boolean; disabled?: boolean; onClick?: () => void }) {
  const viewOnly = useViewOnly(); // a view-only video's menus change things
  const disabled = off || viewOnly;
  return (
    <button
      type="button"
      role={checked === undefined ? "menuitem" : "menuitemradio"}
      aria-checked={checked}
      onClick={disabled ? undefined : onClick}
      aria-disabled={disabled || undefined}
      className={`flex min-h-control w-full items-center gap-3 rounded-md px-3 text-left transition-colors duration-(--dur-fast) ${disabled ? "cursor-not-allowed text-faint" : `hover:bg-surface-2 ${danger ? "text-danger" : "text-text"}`}`}
    >
      {children}
    </button>
  );
}
