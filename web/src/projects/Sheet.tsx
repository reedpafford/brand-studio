import { useEffect, type ReactNode } from "react";
import { btnSecondary } from "../ui";

/** A bottom sheet: a scrim, a panel along the bottom, Escape or a tap outside closes it. */
export function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <>
      <button type="button" aria-label="Close" className="fixed inset-0 z-30 bg-[var(--scrim)]" onClick={onClose} />
      <div
        role="dialog"
        aria-label={title}
        className="fixed inset-x-0 bottom-0 z-30 max-h-[80vh] space-y-3 overflow-y-auto rounded-t-lg border border-border bg-surface p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] shadow-md sm:inset-x-auto sm:left-1/2 sm:w-[28rem] sm:-translate-x-1/2"
      >
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-[length:var(--text-md)] font-semibold">{title}</h3>
          <button type="button" className={`${btnSecondary} min-h-11 sm:min-h-8`} onClick={onClose}>
            Done
          </button>
        </div>
        {children}
      </div>
    </>
  );
}
