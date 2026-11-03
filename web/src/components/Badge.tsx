import type { ComponentType, ReactNode } from "react";

export type Tone = "success" | "warning" | "danger" | "neutral" | "accent" | "media";
const tones: Record<Tone, string> = {
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
  neutral: "bg-surface-3 text-muted",
  accent: "bg-accent-soft text-accent-text",
  /** Over a picture, in either mode: readable on any photo. */
  media: "bg-black/60 text-white",
};

/** Status is always in words; the colour is a second signal. */
export function Badge({ tone = "neutral", icon: Icon, children }: { tone?: Tone; icon?: ComponentType<{ size?: number; strokeWidth?: number; "aria-hidden"?: boolean }>; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-xs font-semibold ${tones[tone]}`}>
      {Icon && <Icon size={16} strokeWidth={1.75} aria-hidden />}
      {children}
    </span>
  );
}

const dots: Record<Tone, string> = { success: "bg-success", warning: "bg-warning", danger: "bg-danger", neutral: "bg-muted", accent: "bg-accent", media: "bg-white" };

/** A list's status: a small dot and the word. The word carries it; the dot's colour is the second signal. */
export function Dot({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap">
      <span aria-hidden className={`size-2 shrink-0 rounded-full ${dots[tone]}`} />
      {children}
    </span>
  );
}

/** Small bars for a run of steps: done ones green, the current one in the text colour, the rest dim. `at` is the current
 *  step's index, or steps.length when all are done. Read out as words. */
export function StepBars({ steps, at, attention }: { steps: readonly string[]; at: number; /** the current step waits on someone: amber */ attention?: boolean }) {
  const said = at >= steps.length ? `All ${steps.length} steps done` : `Step ${at + 1} of ${steps.length}: ${steps[at]}`;
  return (
    <span role="img" aria-label={said} title={said} className="inline-flex shrink-0 gap-1">
      {steps.map((s, i) => (
        <span key={s} className={`h-1 w-3 rounded-full ${i < at ? "bg-success" : i === at ? (attention ? "bg-warning" : "bg-text") : "bg-surface-3"}`} />
      ))}
    </span>
  );
}
