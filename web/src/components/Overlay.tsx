import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { Button } from "./Button";

const FOCUSABLE = 'a[href], button:not([disabled]), textarea, input:not([disabled]), select, [tabindex]:not([tabindex="-1"])';

/** Traps Tab inside the panel, closes on Escape, and returns focus to whatever opened it. */
function useOverlay(onClose: () => void) {
  const panel = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  });
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const el = panel.current;
    (el?.querySelector<HTMLElement>(FOCUSABLE) ?? el)?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") return close.current();
      if (e.key !== "Tab" || !el) return;
      const items = [...el.querySelectorAll<HTMLElement>(FOCUSABLE)];
      if (items.length === 0) return e.preventDefault();
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      opener?.focus?.();
    };
  }, []);
  return panel;
}

function Frame({ title, onClose, className, grabber, children }: { title: string; onClose: () => void; className: string; grabber?: boolean; children: ReactNode }) {
  const heading = useId();
  const panel = useOverlay(onClose);
  // Rendered into the page body, so a sticky bar or tab bar can never sit on top of it.
  return createPortal(
    <>
      <div aria-hidden onClick={onClose} className="fixed inset-0 z-50 bg-scrim" />
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={heading} tabIndex={-1} className={`fixed z-50 flex flex-col bg-surface shadow-overlay ${className}`}>
        {grabber && <span aria-hidden className="mx-auto mt-2 h-1 w-10 rounded-full bg-border-strong" />}
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <h2 id={heading} className="font-display text-md font-bold">
            {title}
          </h2>
          <button type="button" aria-label="Close" onClick={onClose} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2">
            <X size={20} strokeWidth={1.75} aria-hidden />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-[calc(1rem+env(safe-area-inset-bottom))]">{children}</div>
      </div>
    </>,
    document.body,
  );
}

/** A bottom sheet (phones): up to 90dvh, scrolls inside, radius 20 on top. */
export function Sheet(props: { title: string; onClose: () => void; children: ReactNode }) {
  return <Frame {...props} grabber className="inset-x-0 bottom-0 max-h-[90dvh] rounded-t-xl" />;
}

/** A side panel (desktop): 380px from the right, full height below the top bar. */
export function SidePanel(props: { title: string; onClose: () => void; children: ReactNode }) {
  return <Frame {...props} className="bottom-0 right-0 top-topbar w-[380px] max-w-full border-l border-border" />;
}

/** For confirmations only. A destructive action says what is lost and uses the danger button. */
export function Dialog({
  title,
  children,
  cancelLabel = "Keep it",
  actionLabel,
  danger,
  busy,
  onCancel,
  onConfirm,
}: {
  title: string;
  children?: ReactNode;
  cancelLabel?: string;
  actionLabel: string;
  danger?: boolean;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const heading = useId();
  const panel = useOverlay(onCancel);
  return createPortal(
    <>
      <div aria-hidden onClick={onCancel} className="fixed inset-0 z-50 bg-scrim" />
      <div ref={panel} role="alertdialog" aria-modal="true" aria-labelledby={heading} tabIndex={-1} className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-xl bg-surface p-5 shadow-overlay">
        <h2 id={heading} className="font-display text-xl font-bold">
          {title}
        </h2>
        {children && <div className="mt-2 text-sm text-muted">{children}</div>}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant={danger ? "danger" : "primary"} busy={busy} onClick={onConfirm}>
            {actionLabel}
          </Button>
        </div>
      </div>
    </>,
    document.body,
  );
}
