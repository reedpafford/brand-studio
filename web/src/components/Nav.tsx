import { useId, useState } from "react";
import { Check, ChevronDown, TriangleAlert } from "lucide-react";
import { useMedia } from "../useMedia";
import { Button } from "./Button";
import { Sheet } from "./Overlay";

/** done ✓, current (amber), open (can be opened, not finished), todo (locked), stale (out of date). */
export type StepState = "done" | "current" | "open" | "todo" | "stale";
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

/** v5's step mark: a small ring with the number, green with a tick when done, indigo when current. */
function Ring({ step, n }: { step: Step; n: number }) {
  const look = step.state === "done" ? "border-success bg-success text-bg" : step.state === "current" ? "border-accent-text text-accent-text" : "border-border";
  return (
    <span aria-hidden className={`grid size-[18px] place-items-center rounded-full border text-xs tabular-nums ${look}`}>
      {step.state === "done" ? <Check size={12} strokeWidth={2.5} /> : step.state === "stale" ? <TriangleAlert size={12} strokeWidth={2} className="text-warning" /> : n}
    </span>
  );
}

/** Six steps. Desktop: a row joined by lines, or (flat, the v5 script steps) a quiet row of rings. Phone: one 44px button opening a sheet. */
export function StepPicker({ steps, onPick, flat }: { steps: Step[]; onPick: (id: string) => void; flat?: boolean }) {
  const phone = useMedia("(max-width: 1023px)"); // the row of six does not fit below the rail breakpoint
  const uid = useId();
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
  if (flat)
    return (
      <ol aria-label="Steps" className="flex items-center gap-0.5">
        {steps.map((s, i) => (
          <li key={s.id}>
            <button
              type="button"
              aria-disabled={s.state === "todo"}
              aria-current={s.state === "current" ? "step" : undefined}
              aria-describedby={s.state === "todo" && s.reason ? `${uid}-${s.id}` : undefined}
              title={s.state === "todo" ? s.reason : undefined}
              onClick={() => pick(s)}
              className={`inline-flex min-h-control-dense items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 text-sm font-medium transition-colors duration-(--dur-fast) ${
                s.state === "current" ? "bg-surface-2 text-text" : s.state === "todo" ? "cursor-not-allowed text-disabled-text" : "text-muted hover:text-text"
              }`}
            >
              <Ring step={s} n={i + 1} />
              {text(s)}
            </button>
            {s.state === "todo" && s.reason && (
              <span id={`${uid}-${s.id}`} className="sr-only">
                {s.reason}
              </span>
            )}
          </li>
        ))}
      </ol>
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
            aria-describedby={s.state === "todo" && s.reason ? `${uid}-${s.id}` : undefined}
            title={s.state === "todo" ? s.reason : undefined}
            onClick={() => pick(s)}
            className={`inline-flex min-h-control items-center gap-2 rounded-full px-3 text-base transition-colors duration-(--dur-fast) ${
              s.state === "current" ? "bg-accent font-semibold text-on-accent" : s.state === "todo" ? "cursor-not-allowed text-muted" : "text-text hover:bg-surface-2"
            }`}
          >
            <Mark step={s} n={i + 1} />
            {text(s)}
          </button>
          {s.state === "todo" && s.reason && (
            <span id={`${uid}-${s.id}`} className="sr-only">
              {s.reason}
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}

export type Tab = { id: string; label: string; count?: number };

/** A pill tab (v4 boards). The chosen one has a 3:1 edge and semibold words, not just a faint fill; hover only brightens the
 *  words (QA-3 on #1164). */
export const pillClass = (on: boolean) =>
  `inline-flex min-h-control shrink-0 items-center gap-2 whitespace-nowrap rounded-md px-3 ${on ? "bg-surface-2 font-semibold text-text ring-1 ring-inset ring-border-strong" : "font-medium text-muted hover:text-text"}`;
/** A strip of pills that scrolls sideways; its padding keeps the focus ring from being cut off. */
export const pillStrip = "-m-1 flex gap-1 overflow-x-auto p-1";

/** Pill tabs with counts (v4 boards): Characters 5 · Places 2 · Props 3. */
export function Tabs({ tabs, value, onChange, label }: { tabs: Tab[]; value: string; onChange: (id: string) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className={pillStrip}>
      {tabs.map((t) => {
        const on = t.id === value;
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={on}
            onClick={() => onChange(t.id)}
            className={pillClass(on)}
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
