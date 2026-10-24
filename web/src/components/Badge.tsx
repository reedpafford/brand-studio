import type { ComponentType, ReactNode } from "react";

export type Tone = "success" | "warning" | "danger" | "neutral" | "accent";
const tones: Record<Tone, string> = {
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
  neutral: "bg-surface-3 text-muted",
  accent: "bg-accent-soft text-accent-text",
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
