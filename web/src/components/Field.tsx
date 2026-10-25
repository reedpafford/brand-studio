import { useId, type InputHTMLAttributes, type Ref, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { ChevronDown, CircleAlert } from "lucide-react";

const box =
  "w-full min-h-control rounded-md border bg-surface px-3 py-2 text-base text-text placeholder:text-muted disabled:bg-disabled disabled:text-disabled-text sm:min-h-control";

type Common = { label: string; hint?: ReactNode; error?: string | null; /** "78 / 2,000" */ counter?: string; /** The counter turns green once the field is long enough. */ counterOk?: boolean };

function Frame({ label, hint, error, counter, counterOk, id, children }: Common & { id: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        {counter && <span className={`shrink-0 whitespace-nowrap text-sm tabular-nums ${counterOk ? "text-success" : "text-muted"}`}>{counter}</span>}
      </div>
      {children}
      {error ? (
        <p id={`${id}-note`} className="flex items-start gap-1 text-sm text-danger">
          <CircleAlert size={16} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </p>
      ) : hint ? (
        <p id={`${id}-note`} className="text-sm text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

const edge = (error?: string | null) => (error ? "border-danger" : "border-border-strong");

/** A labelled one-line field. The error replaces the hint and is announced with the field. */
export function Field({ label, hint, error, counter, counterOk, trailing, ...rest }: Common & Omit<InputHTMLAttributes<HTMLInputElement>, "className"> & { /** A control inside the right end of the box (the password eye). */ trailing?: ReactNode }) {
  const id = useId();
  return (
    <Frame {...{ label, hint, error, counter, counterOk, id }}>
      <span className="relative block">
        <input id={id} aria-invalid={!!error || undefined} aria-describedby={error || hint ? `${id}-note` : undefined} className={`${box} ${edge(error)} ${trailing ? "pr-12" : ""}`} {...rest} />
        {trailing && <span className="absolute inset-y-0 right-0 grid w-11 place-items-center">{trailing}</span>}
      </span>
    </Frame>
  );
}

export function TextArea({ label, hint, error, counter, rows = 4, ...rest }: Common & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "className"> & { ref?: Ref<HTMLTextAreaElement> }) {
  const id = useId();
  return (
    <Frame {...{ label, hint, error, counter, id }}>
      <textarea id={id} rows={rows} aria-invalid={!!error || undefined} aria-describedby={error || hint ? `${id}-note` : undefined} className={`${box} ${edge(error)}`} {...rest} />
    </Frame>
  );
}

export function Select({ label, hint, error, counter, children, ...rest }: Common & Omit<SelectHTMLAttributes<HTMLSelectElement>, "className">) {
  const id = useId();
  return (
    <Frame {...{ label, hint, error, counter, id }}>
      <span className="relative block">
        <select id={id} aria-invalid={!!error || undefined} aria-describedby={error || hint ? `${id}-note` : undefined} className={`${box} ${edge(error)} appearance-none pr-10`} {...rest}>
          {children}
        </select>
        <ChevronDown size={20} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted" />
      </span>
    </Frame>
  );
}
