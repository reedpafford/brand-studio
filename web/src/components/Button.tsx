import { useId, type ButtonHTMLAttributes, type ComponentType, type ReactNode } from "react";
import { LoaderCircle } from "lucide-react";
import { creditsLabel, wholeCredits } from "./credits";
import { useViewOnly } from "./ViewOnly";

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

/** The same look as a Button, for a link that downloads or goes somewhere (an <a>). */
export const buttonClass = (variant: Variant = "primary") => `${base} ${look[variant]} min-h-control px-4`;

export type ButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> & {
  variant?: Variant;
  /** Desktop-only secondary controls may be 36px; phones are always 44px. */
  dense?: boolean;
  /** Shows a spinner, disables the button and keeps its label. */
  busy?: boolean;
  /** A paid action says its price inside the button: "Make the takes · 8 credits". `null`: not known yet, so a grey
   *  placeholder holds its place (the label never changes length after it shows) and a press waits for it. */
  price?: number | null;
  /** The price can vary: the button shows the most it can cost ("up to 4 credits"), and `usually` says the usual price under it. */
  upTo?: boolean;
  usually?: number;
  /** An icon after the label, pushed to the far edge (a picker's chevron). */
  trailing?: Icon;
  /** Label left, trailing icon right, filling the width. */
  spread?: boolean;
  /** Why the button is disabled, in muted text on the line under it. */
  reason?: string | null;
  icon?: Icon;
  /** It only shows something, so it stays live on a view-only page. A Button that opens and closes a part of the page
   *  (aria-expanded, no price) counts as one unless this says false. */
  reads?: boolean;
  className?: string;
  children?: ReactNode;
};

export function Button({ variant = "primary", dense, busy, price, upTo, usually, reason, icon: Icon, trailing: Trailing, spread, reads, className = "", children, disabled, onClick, type = "button", ...rest }: ButtonProps) {
  const why = useId();
  const lookOnly = useViewOnly() && !(reads ?? (rest["aria-expanded"] !== undefined && price === undefined));
  // Busy is not disabled: it keeps its colour (amber stays amber) and its focus, and just ignores presses.
  const label = children;
  const size = dense && variant !== "primary" ? "min-h-control px-4 lg:min-h-control-dense lg:px-3" : "min-h-control px-4";
  const waiting = busy || price === null; // a press never goes before its price is shown
  const button = (
    <button
      type={type}
      disabled={disabled || lookOnly}
      aria-busy={waiting || undefined}
      aria-disabled={waiting || undefined}
      onClick={waiting ? (e) => e.preventDefault() : onClick}
      aria-describedby={reason ? why : undefined}
      className={`${base} ${look[variant]} ${size} ${spread ? "w-full justify-between text-left" : ""} ${busy ? "cursor-progress" : ""} ${className}`}
      {...rest}
    >
      {busy ? <LoaderCircle size={16} strokeWidth={1.75} aria-hidden className="animate-spin motion-reduce:animate-none" /> : Icon ? <Icon size={20} strokeWidth={1.75} aria-hidden /> : null}
      <span className={spread ? "min-w-0 flex-1" : undefined}>
        {label}
        {price === null && (
          <>
            {" "}
            <span className="inline-block h-[1em] w-16 animate-pulse rounded-sm bg-surface-3 align-middle motion-reduce:animate-none" aria-hidden />
            <span className="sr-only">· price loading</span>
          </>
        )}
        {price !== undefined && price !== null && (
          <>
            {" "}
            <span className="tabular-nums">· {upTo ? "up to " : ""}{creditsLabel(price)}</span>
          </>
        )}
      </span>
      {Trailing && <Trailing size={20} strokeWidth={1.75} aria-hidden className="shrink-0" />}
    </button>
  );
  const usual = upTo && usually !== undefined && price !== undefined && price !== null && !busy ? `Usually ${wholeCredits(usually)}. Anything not used comes back.` : null;
  if (!reason && !usual) return button;
  return (
    <span className="flex flex-col items-stretch gap-1">
      {button}
      {usual && <span className="text-sm text-muted">{usual}</span>}
      {reason && (
        <span id={why} className="text-sm text-muted">
          {reason}
        </span>
      )}
    </span>
  );
}
