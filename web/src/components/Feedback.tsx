import type { ComponentType, ReactNode } from "react";
import { CircleAlert, Info, TriangleAlert } from "lucide-react";

type Icon = ComponentType<{ size?: number; strokeWidth?: number; "aria-hidden"?: boolean; className?: string }>;
const tones = {
  danger: { box: "bg-danger-soft", icon: CircleAlert, text: "text-danger" },
  warning: { box: "bg-warning-soft", icon: TriangleAlert, text: "text-warning" },
  info: { box: "bg-surface-2", icon: Info, text: "text-muted" },
};

/** What happened, what was charged (usually nothing), and what to do, with the button on the right. A soft tint with
 *  no outline: the icon carries the colour, so a problem reads as a note, not an alarm. */
export function Banner({ tone = "danger", title, children, action }: { tone?: keyof typeof tones; title: string; children?: ReactNode; action?: ReactNode }) {
  const t = tones[tone];
  const Icon: Icon = t.icon;
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={`flex flex-wrap items-center gap-3 rounded-lg p-4 ${t.box}`}>
      <Icon size={20} strokeWidth={1.75} aria-hidden className={`shrink-0 ${t.text}`} />
      <div className="min-w-0 flex-1 basis-48">
        <p className="font-semibold">{title}</p>
        {children && <p className="text-sm text-muted">{children}</p>}
      </div>
      {action}
    </div>
  );
}

/** A grey block in the final layout, catching the light while it loads (still when motion is reduced). */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`shimmer rounded-md ${className}`} />;
}

/** What this is, plus one button. */
export function EmptyState({ icon: Icon, title, children, action }: { icon?: Icon; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-border bg-surface p-8 text-center shadow-card">
      {Icon && <Icon size={24} strokeWidth={1.75} aria-hidden className="text-muted" />}
      <h2 className="type-headline">{title}</h2>
      {children && <p className="max-w-prose text-sm text-muted">{children}</p>}
      {action}
    </div>
  );
}
