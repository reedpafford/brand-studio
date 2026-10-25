import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { errorText } from "../api/client";
import { Banner, Button, Card, Field as TextField } from "../components";
import { useToast } from "../toast";

export type Field = { name: string; label: string; type?: string; autoComplete?: string; /** A password counter: turns green at this many characters. */ minLength?: number };
type Me = { id: number };
type Result = { data?: Me; error?: unknown; response?: { status: number } };

class Throttled extends Error {}

/** No shell here: a wordmark, one centred card, and a footnote. */
export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-[452px] flex-col items-stretch justify-start gap-4 p-4 pt-16 sm:justify-center sm:pt-4">
      <p className="text-center font-display text-xl font-extrabold">Brand Studio</p>
      {children}
      <p className="text-center text-sm text-muted">Made for Reed's studio.</p>
    </main>
  );
}

function PasswordField({ field, value, onChange, disabled }: { field: Field; value: string; onChange: (v: string) => void; disabled: boolean }) {
  const [shown, setShown] = useState(false);
  const long = field.minLength !== undefined && value.length >= field.minLength;
  return (
    <TextField
      label={field.label}
      type={shown ? "text" : "password"}
      autoComplete={field.autoComplete}
      required
      disabled={disabled}
      value={value}
      counter={field.minLength !== undefined ? `${value.length} / ${field.minLength}` : undefined}
      counterOk={long}
      onChange={(e) => onChange(e.target.value)}
      trailing={
        <button type="button" aria-label={shown ? "Hide password" : "Show password"} aria-pressed={shown} onClick={() => setShown(!shown)} className="grid size-control place-items-center rounded-md text-muted hover:text-text">
          {shown ? <EyeOff size={20} strokeWidth={1.75} aria-hidden /> : <Eye size={20} strokeWidth={1.75} aria-hidden />}
        </button>
      }
    />
  );
}

/** One card with labelled fields. Submits, then refreshes "me" and goes to the app. */
export function AuthForm(props: {
  title: string;
  fields: Field[];
  submitLabel: string;
  busyLabel?: string;
  submit: (values: Record<string, string>) => Promise<Result>;
  footer?: ReactNode;
  intro?: ReactNode;
  welcome?: (values: Record<string, string>) => string;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [throttled, setThrottled] = useState(false);
  const form = useRef<HTMLFormElement>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const mutation = useMutation({
    mutationFn: async () => {
      const { data, error, response } = await props.submit(values);
      if (!data) {
        if (response?.status === 429) throw new Throttled("Too many tries. Wait a minute and try again.");
        throw new Error(errorText(error));
      }
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      if (props.welcome) toast(props.welcome(values));
      navigate("/", { replace: true });
    },
    onError: (e) => {
      if (e instanceof Throttled) setThrottled(true);
      // The first field (Email on sign in) gets the focus back.
      form.current?.querySelector("input")?.focus();
    },
  });
  // A throttled button comes back after a minute.
  useEffect(() => {
    if (!throttled) return;
    const t = setTimeout(() => setThrottled(false), 60_000);
    return () => clearTimeout(t);
  }, [throttled]);
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    mutation.mutate();
  };
  const set = (name: string, v: string) => setValues({ ...values, [name]: v });

  return (
    <AuthShell>
      <Card className="space-y-4 p-5 sm:p-6">
        <h1 className="type-page">{props.title}</h1>
        {props.intro}
        <form ref={form} onSubmit={onSubmit} className="flex flex-col gap-4">
          {props.fields.map((f) =>
            f.type === "password" && f.name !== "setup_token" ? (
              <PasswordField key={f.name} field={f} value={values[f.name] ?? ""} onChange={(v) => set(f.name, v)} disabled={mutation.isPending} />
            ) : (
              <TextField key={f.name} label={f.label} type={f.type ?? "text"} autoComplete={f.autoComplete} required disabled={mutation.isPending} value={values[f.name] ?? ""} onChange={(e) => set(f.name, e.target.value)} />
            ),
          )}
          {mutation.isError && !(mutation.error instanceof Throttled) && <Banner title={mutation.error.message} />}
          <Button type="submit" busy={mutation.isPending} disabled={throttled} reason={throttled ? "Too many tries. Wait a minute and try again." : undefined} className="w-full">
            {mutation.isPending ? (props.busyLabel ?? props.submitLabel) : props.submitLabel}
          </Button>
        </form>
        {props.footer}
      </Card>
    </AuthShell>
  );
}
