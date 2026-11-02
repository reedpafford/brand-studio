import { useId, type ReactNode } from "react";
import { Button } from "../components";

/** The page top a tab draws first, with its own Save on the right (or none), then the tabs. */
export type SettingsTop = (save?: ReactNode) => ReactNode;

/** One hairline settings row (v5 D_Settings): the label and its helper on the left, the field on the right. */
export function SettingRow({ label, help, htmlFor, children }: { label: string; help: string; htmlFor?: string; children: ReactNode }) {
  return (
    <div className="grid gap-2 border-b border-border py-[18px] sm:grid-cols-[280px_minmax(0,1fr)] sm:gap-6">
      <div>
        {htmlFor ? <label htmlFor={htmlFor} className="text-sm font-medium">{label}</label> : <p className="text-sm font-medium">{label}</p>}
        <p className="text-xs text-muted">{help}</p>
      </div>
      <div className="sm:pt-0.5">{children}</div>
    </div>
  );
}

/** The page top's Save. Why it can't save yet sits beside it on the same row, so the 52 px top keeps one line. */
export function SaveButton({ reason, busy, onClick }: { reason: string | null; busy: boolean; onClick: () => void }) {
  const why = useId();
  return (
    <>
      {reason && (
        <span id={why} className="text-sm text-muted">
          {reason}
        </span>
      )}
      <Button busy={busy} disabled={reason !== null} aria-describedby={reason ? why : undefined} onClick={onClick}>
        Save
      </Button>
    </>
  );
}
