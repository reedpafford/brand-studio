import { useId, type ButtonHTMLAttributes, type ComponentType, type ReactNode } from "react";
import { LoaderCircle } from "lucide-react";
import { creditsLabel } from "./credits";

type Icon = ComponentType<{ size?: number; strokeWidth?: number; className?: string; "aria-hidden"?: boolean }>;
export type Variant = "primary" | "secondary" | "ghost" | "danger";

const base =
  "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-[transform,opacity,background-color] duration-(--dur-fast) active:scale-[0.98] disabled:cursor-not-allowed disabled:active:scale-100";
const look: Record<Variant, string> = {
  primary: "border border-accent-border bg-accent text-on-accent hover:bg-accent-hover active:bg-accent-pressed disabled:border-transparent disabled:bg-disabled disabled:text-disabled-text",
  secondary: "border border-border bg-surface-2 text-text hover:bg-surface-3 disabled:bg-disabled disabled:text-disabled-text",
  ghost: "text-text hover:bg-surface-2 disabled:text-disabled-text",
  danger: "border border-danger bg-danger-soft text-danger hover:bg-surface-2 disabled:border-transparent disabled:bg-disabled disabled:text-disabled-text",
};

export type ButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> & {
  variant?: Variant;
  /** Desktop-only secondary controls may be 36px; phones are always 44px. */
  dense?: boolean;
  /** Shows a spinner, disables the button and keeps its label. */
  busy?: boolean;
  /** A paid action says its price inside the button: "Make the takes · 8 credits". */
  price?: number;
  /** The spend needs Reed: the label becomes "Ask Reed to approve · N credits". */
  ask?: boolean;
  /** Why the button is disabled, in muted text on the line under it. */
  reason?: string | null;
  icon?: Icon;
  className?: string;
  children?: ReactNode;
};

export function Button({ variant = "primary", dense, busy, price, ask, reason, icon: Icon, className = "", children, disabled, type = "button", ...rest }: ButtonProps) {
  const why = useId();
  const off = !!disabled || !!busy;
  const label = ask ? "Ask Reed to approve" : children;
  const size = dense && variant !== "primary" ? "min-h-control px-4 sm:min-h-control-dense sm:px-3" : "min-h-control px-4";
  const button = (
    <button
      type={type}
      disabled={off}
      aria-busy={busy || undefined}
      aria-describedby={reason ? why : undefined}
      className={`${base} ${look[variant]} ${size} ${className}`}
      {...rest}
    >
      {busy ? <LoaderCircle size={16} strokeWidth={1.75} aria-hidden className="animate-spin motion-reduce:animate-none" /> : Icon ? <Icon size={20} strokeWidth={1.75} aria-hidden /> : null}
      <span>
        {label}
        {price !== undefined && (
          <>
            {" "}
            <span className="tabular-nums">· {creditsLabel(price)}</span>
          </>
        )}
      </span>
    </button>
  );
  if (!reason) return button;
  return (
    <span className="flex flex-col items-stretch gap-1">
      {button}
      <span id={why} className="text-sm text-muted">
        {reason}
      </span>
    </span>
  );
}
