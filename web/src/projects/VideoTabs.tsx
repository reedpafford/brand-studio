import { useId, type ReactNode } from "react";
import { Check, TriangleAlert } from "lucide-react";
import { StepPicker, type Step } from "../components";
import { useMedia } from "../useMedia";

/** The video's one row of tabs (v4): Director · Plan · Cast · Clips · Final cut. A locked tab says why and doesn't open.
 *  On a phone the steps stay one button with a sheet. `end` sits at the row's right (the script, say). */
export function VideoTabs({ steps, onPick, end }: { steps: Step[]; onPick: (id: string) => void; end?: ReactNode }) {
  const phone = useMedia("(max-width: 1023px)"); // the step picker's own breakpoint
  const uid = useId();
  if (phone)
    return (
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <StepPicker steps={steps} onPick={onPick} />
        </div>
        {end}
      </div>
    );
  return (
    <div className="flex items-center gap-3 border-b border-border">
      <div role="tablist" aria-label="Steps" className="flex min-w-0 flex-1 gap-1 overflow-x-auto">
        {steps.map((s) => {
          const on = s.state === "current";
          const locked = s.state === "todo";
          return (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={on}
              aria-disabled={locked || undefined}
              aria-describedby={locked && s.reason ? `${uid}-${s.id}` : undefined}
              title={locked ? s.reason : undefined}
              onClick={() => !locked && !on && onPick(s.id)}
              className={`-mb-px inline-flex min-h-control-dense items-center gap-1.5 border-b-2 px-3 font-medium ${on ? "border-accent text-text" : locked ? "cursor-not-allowed border-transparent text-muted opacity-70" : "border-transparent text-muted hover:text-text"}`}
            >
              {s.state === "done" && <Check size={14} strokeWidth={1.75} aria-hidden className="text-success" />}
              {s.state === "stale" && <TriangleAlert size={14} strokeWidth={1.75} aria-hidden className="text-warning" />}
              {s.state === "stale" ? `${s.label} · out of date` : s.label}
            </button>
          );
        })}
      </div>
      {steps.map((s) => s.state === "todo" && s.reason && (
        <span key={s.id} id={`${uid}-${s.id}`} className="sr-only">
          {s.reason}
        </span>
      ))}
      {end}
    </div>
  );
}
