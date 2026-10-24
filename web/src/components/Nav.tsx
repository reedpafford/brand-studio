import { useState } from "react";
import { Check, ChevronDown, TriangleAlert } from "lucide-react";
import { useMedia } from "../useMedia";
import { Button } from "./Button";
import { Sheet } from "./Overlay";

export type StepState = "done" | "current" | "todo" | "stale";
export type Step = { id: string; label: string; state: StepState; /** why a "todo" step is locked: "Finish Shots first" */ reason?: string };

/** The mark in front of a step: ✓ done, an amber number when current, a warning when out of date. */
function Mark({ step, n }: { step: Step; n: number }) {
  if (step.state === "done") return <Check size={16} strokeWidth={1.75} aria-hidden className="text-success" />;
  if (step.state === "stale") return <TriangleAlert size={16} strokeWidth={1.75} aria-hidden className="text-warning" />;
  return (
    <span aria-hidden className="tabular-nums">
      {n}
    </span>
  );
}

const text = (s: Step) => (s.state === "stale" ? `${s.label} · out of date` : s.label);

/** Six steps. Desktop: a row joined by lines. Phone: one 44px button opening a sheet. */
export function StepPicker({ steps, onPick }: { steps: Step[]; onPick: (id: string) => void }) {
  const phone = useMedia("(max-width: 639px)");
  const [open, setOpen] = useState(false);
  const at = Math.max(0, steps.findIndex((s) => s.state === "current"));
  const pick = (s: Step) => {
    if (s.state === "todo") return;
    setOpen(false);
    onPick(s.id);
  };
  if (phone)
    return (
      <>
        <Button variant="secondary" spread trailing={ChevronDown} aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(true)}>
          <span className="tabular-nums">
            Step {at + 1} of {steps.length} · {steps[at]?.label}
          </span>
        </Button>
        {open && (
          <Sheet title="Steps" onClose={() => setOpen(false)}>
            <ol className="flex flex-col">
              {steps.map((s, i) => (
                <li key={s.id}>
                  <button type="button" aria-disabled={s.state === "todo"} aria-current={s.state === "current" ? "step" : undefined} onClick={() => pick(s)} className={`flex min-h-control w-full items-center gap-3 rounded-md px-2 text-left ${s.state === "todo" ? "text-muted" : "hover:bg-surface-2"}`}>
                    <span className="grid size-6 place-items-center">
                      <Mark step={s} n={i + 1} />
                    </span>
                    <span className="flex-1">
                      <span className={s.state === "current" ? "font-semibold text-accent-text" : ""}>{text(s)}</span>
                      {s.state === "todo" && s.reason && <span className="block text-sm text-muted">{s.reason}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </Sheet>
        )}
      </>
    );
  return (
    <ol aria-label="Steps" className="flex flex-wrap items-center gap-y-2">
      {steps.map((s, i) => (
        <li key={s.id} className="flex items-center">
          {i > 0 && <span aria-hidden className="mx-2 h-px w-4 bg-border-strong" />}
          <button
            type="button"
            aria-disabled={s.state === "todo"}
            aria-current={s.state === "current" ? "step" : undefined}
            title={s.state === "todo" ? s.reason : undefined}
            onClick={() => pick(s)}
            className={`inline-flex min-h-control items-center gap-2 rounded-full px-3 text-base transition-colors duration-(--dur-fast) ${
              s.state === "current" ? "bg-accent font-semibold text-on-accent" : s.state === "todo" ? "cursor-not-allowed text-muted" : "text-text hover:bg-surface-2"
            }`}
          >
            <Mark step={s} n={i + 1} />
            {text(s)}
          </button>
        </li>
      ))}
    </ol>
  );
}

export type Tab = { id: string; label: string; count?: number };

/** Underline tabs with counts: Characters 5 · Places 2 · Props 3. */
export function Tabs({ tabs, value, onChange, label }: { tabs: Tab[]; value: string; onChange: (id: string) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto border-b border-border">
      {tabs.map((t) => {
        const on = t.id === value;
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={on}
            onClick={() => onChange(t.id)}
            className={`-mb-px inline-flex min-h-control items-center gap-2 border-b-2 px-3 font-medium ${on ? "border-accent text-text" : "border-transparent text-muted hover:text-text"}`}
          >
            {t.label}
            {t.count !== undefined && (
              <>
                {" "}
                <span className="tabular-nums text-muted">{t.count}</span>
              </>
            )}
          </button>
        );
      })}
    </div>
  );
}
