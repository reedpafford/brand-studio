import { useId, type ButtonHTMLAttributes, type ComponentType, type ReactNode } from "react";
import { LoaderCircle } from "lucide-react";
import { pressLabel, wholeCredits, type Charge } from "./credits";
import { useViewOnly } from "./ViewOnly";

type Icon = ComponentType<{ size?: number; strokeWidth?: number; className?: string; "aria-hidden"?: boolean }>;
export type Variant = "primary" | "secondary" | "ghost" | "danger";

const base =
  "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-[transform,background-color,border-color,color,box-shadow] duration-(--dur-fast) ease-out active:scale-[0.98] active:duration-(--dur-instant) disabled:cursor-not-allowed disabled:active:scale-100";
const look: Record<Variant, string> = {
  primary: "border border-accent-border bg-accent text-on-accent shadow-press hover:bg-accent-hover active:bg-accent-pressed disabled:border-transparent disabled:bg-disabled disabled:text-disabled-text disabled:shadow-none",
  // v5: outlined on the page's colour, no fill; 32 px and 13/500 on a computer, 44 px on a phone.
  secondary: "border border-border-button bg-transparent text-text hover:border-border-strong/50 hover:bg-surface-2 disabled:border-transparent disabled:bg-disabled disabled:text-disabled-text lg:text-sm",
  ghost: "text-muted hover:bg-surface-2 hover:text-text disabled:text-disabled-text",
  danger: "border border-danger bg-danger-soft text-danger hover:bg-surface-2 disabled:border-transparent disabled:bg-disabled disabled:text-disabled-text",
};

/** The same look as a Button, for a link that downloads or goes somewhere (an <a>). */
export const buttonClass = (variant: Variant = "primary") => `${base} ${look[variant]} ${variant === "secondary" ? secondarySize : "min-h-control px-4"}`;
const secondarySize = "min-h-control px-4 lg:min-h-control-dense lg:px-3";

/** A paid action says its price inside the button: "Make the takes · 8 credits". `null`: not known yet, so a grey
 *  placeholder holds its place (the label never changes length after it shows) and a press waits for it. A price
 *  always comes with its `charge`, so no paid button can skip saying "up to" when the charge can be lower (rule 36). */
type Priced = { price?: never; charge?: never } | { price: number | null | undefined; charge: Charge };

export type ButtonProps = Priced & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> & {
  variant?: Variant;
  /** Desktop-only secondary controls may be 36px; phones are always 44px. */
  dense?: boolean;
  /** Shows a spinner, disables the button and keeps its label. */
  busy?: boolean;
  /** The usual price under an "up to" one ("Usually 3. Anything not used comes back."). */
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
  /** Its keyboard shortcut, after the label and price ("⌘↵"); desktop only. */
  kbd?: string;
  className?: string;
  children?: ReactNode;
};

export function Button({ variant = "primary", dense, busy, price, charge, usually, reason, icon: Icon, trailing: Trailing, spread, reads, kbd, className = "", children, disabled, onClick, type = "button", ...rest }: ButtonProps) {
  const why = useId();
  const lookOnly = useViewOnly() && !(reads ?? (rest["aria-expanded"] !== undefined && price === undefined));
  // Busy is not disabled: it keeps its colour (amber stays amber) and its focus, and just ignores presses.
  const label = children;
  const size = (dense && variant !== "primary") || variant === "secondary" ? secondarySize : "min-h-control px-4";
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
      {busy ? <LoaderCircle size={16} strokeWidth={1.75} aria-hidden className="animate-spin motion-reduce:animate-none" /> : Icon ? <Icon size={20} strokeWidth={1.75} aria-hidden className="shrink-0 lg:size-4" /> : null}
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
            <span className="tabular-nums">· {pressLabel(price, charge ?? "fixed")}</span>
          </>
        )}
      </span>
      {kbd && (
        <kbd aria-hidden className="hidden rounded-sm bg-current/15 px-1 font-sans text-xs leading-4 opacity-90 lg:inline">
          {kbd}
        </kbd>
      )}
      {Trailing && <Trailing size={20} strokeWidth={1.75} aria-hidden className="shrink-0 lg:size-4" />}
    </button>
  );
  const usual = charge === "estimate" && usually !== undefined && price !== undefined && price !== null && !busy ? `Usually ${wholeCredits(usually)}. Anything not used comes back.` : null;
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
