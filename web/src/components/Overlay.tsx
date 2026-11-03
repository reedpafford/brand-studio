import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { useRail } from "../useMedia";
import { Button } from "./Button";

const FOCUSABLE = 'a[href], button:not([disabled]), textarea, input:not([disabled]), select, [tabindex]:not([tabindex="-1"])';

/** The overlays open now, the newest last: only the top one answers Escape and Tab, so a list opened over a panel
 *  closes alone and the panel (and what was picked in it) stays (QA-3 on #985). */
const open: object[] = [];

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
    const me = {};
    open.push(me);
    (el?.querySelector<HTMLElement>("[data-autofocus]") ?? el?.querySelector<HTMLElement>(FOCUSABLE) ?? el)?.focus(); // a marked first field, else the first control
    const onKey = (e: KeyboardEvent) => {
      if (open.at(-1) !== me) return;
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
      open.splice(open.indexOf(me), 1);
      opener?.focus?.();
    };
  }, []);
  return panel;
}

type Props = { title: string; onClose: () => void; children: ReactNode; /** Pinned under the scrolling body: the panel's one press. */ footer?: ReactNode };

function Frame({ title, onClose, className, grabber, footer, children }: Props & { className: string; grabber?: boolean }) {
  const heading = useId();
  const panel = useOverlay(onClose);
  // Rendered into the page body, so a sticky bar or tab bar can never sit on top of it.
  return createPortal(
    <>
      <div aria-hidden onClick={onClose} className="fixed inset-0 z-50 bg-scrim" />
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={heading} tabIndex={-1} className={`fixed z-50 flex flex-col bg-surface shadow-overlay ${className}`}>
        {grabber && <span aria-hidden className="mx-auto mt-2 h-1 w-10 rounded-full bg-border-strong" />}
        <div className={`flex items-center justify-between gap-3 px-4 py-3 ${footer ? "mb-4 border-b border-border" : ""}`}>
          <h2 id={heading} className="font-display text-md font-bold">
            {title}
          </h2>
          <button type="button" aria-label="Close" onClick={onClose} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2">
            <X size={20} strokeWidth={1.75} aria-hidden />
          </button>
        </div>
        <div className={`min-h-0 flex-1 overflow-y-auto px-4 ${footer ? "pb-4" : "pb-[calc(1rem+env(safe-area-inset-bottom))]"}`}>{children}</div>
        {footer && <div className="space-y-3 border-t border-border px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-4">{footer}</div>}
      </div>
    </>,
    document.body,
  );
}

/** A bottom sheet (phones): up to 90dvh, scrolls inside, radius 20 on top. */
export function Sheet(props: Props) {
  return <Frame {...props} grabber className="inset-x-0 bottom-0 max-h-[90dvh] rounded-t-xl" />;
}

/** A side panel (desktop): 380px from the right (`wide`: 480, E_ScriptMakeVideo), full height below the top bar. */
export function SidePanel({ wide, ...props }: Props & { wide?: boolean }) {
  return <Frame {...props} className={`bottom-0 right-0 top-topbar ${wide ? "w-[480px]" : "w-[380px]"} max-w-full border-l border-border`} />;
}

/** For confirmations only. A destructive action says what is lost and uses the danger button. */
export function Dialog({
  title,
  children,
  cancelLabel = "Keep it",
  actionLabel,
  danger,
  busy,
  holdReason,
  onCancel,
  onConfirm,
}: {
  title: string;
  children?: ReactNode;
  cancelLabel?: string;
  actionLabel: string;
  danger?: boolean;
  busy?: boolean;
  /** Why the action can't be pressed yet ("Say why"); it disables the button and shows under it. */
  holdReason?: string | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const heading = useId();
  const panel = useOverlay(onCancel);
  return createPortal(
    <>
      <div aria-hidden onClick={onCancel} className="fixed inset-0 z-50 bg-scrim" />
      <div ref={panel} role="alertdialog" aria-modal="true" aria-labelledby={heading} tabIndex={-1} className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-[440px] -translate-x-1/2 -translate-y-1/2 rounded-xl bg-surface p-5 shadow-overlay">
        <h2 id={heading} className="text-md font-semibold">
          {title}
        </h2>
        {children && <div className="mt-2 text-sm text-muted">{children}</div>}
        {/* Centred, so the outlined way back keeps its own 32 px beside a 36 px action (F_BrandEdit). */}
        <div className="mt-5 flex items-center justify-end gap-2">
          {/* v5 F_BrandEdit: the way back is outlined; a danger action is filled red. */}
          <Button variant="secondary" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant={danger ? "danger" : "primary"} busy={busy} disabled={!!holdReason} reason={holdReason} className={danger ? "enabled:border-transparent! enabled:bg-danger! enabled:text-bg! enabled:hover:opacity-90" : ""} onClick={onConfirm}>
            {actionLabel}
          </Button>
        </div>
      </div>
    </>,
    document.body,
  );
}

/** A side panel on desktop (from 1024), a bottom sheet on a phone. For forms that belong beside the page. */
export function Panel(props: Props & { wide?: boolean }) {
  const { wide, ...rest } = props;
  return useRail() ? <SidePanel wide={wide} {...rest} /> : <Sheet {...rest} />;
}
