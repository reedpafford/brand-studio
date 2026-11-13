import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { useOverlay } from "../components/Overlay";

/** The studio's one dialog, only where something needs typing or a yes. Enter confirms, Escape or a click outside
 *  cancels, Tab stays inside, and focus goes back to what opened it (the app's own overlay rules). Focus starts on the
 *  first thing marked `data-autofocus` (a field), else on the confirm button. Without `confirm` it is a bare box with
 *  no title or buttons (Search or jump), and Enter still confirms. */
export function Dialog({ title, confirm, onConfirm, onClose, children }: { title: string; confirm?: string; onConfirm: () => void; onClose: () => void; children: ReactNode }) {
  const panel = useOverlay(onClose);
  return createPortal(
    <div ref={panel} className="studio scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={confirm ? "dlg" : "cmd"}
        onSubmit={(e) => {
          e.preventDefault();
          onConfirm();
        }}
      >
        {confirm && <h3>{title}</h3>}
        {children}
        {confirm && (
          <div className="dlg-f">
            <button type="button" className="btn ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn go" data-autofocus>
              {confirm}
            </button>
          </div>
        )}
      </form>
    </div>,
    document.body,
  );
}
