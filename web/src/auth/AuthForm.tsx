import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { errorText } from "../api/client";
import { Button, Field as TextField } from "../components";
import { useToast } from "../toast";

export type Field = { name: string; label: string; /** Plain help under the field. */ hint?: string; type?: string; autoComplete?: string; /** The shortest a password may be; the browser holds the form until it's long enough. */ minLength?: number; /** Shown read-only, not sent (an email invite's own email, v5 A_Invite). */ value?: string };
type Me = { id: number };
type Result = { data?: Me; error?: unknown; response?: { status: number } };

class Throttled extends Error {}

/** No shell here (v5 A_SignIn, A_Setup, A_Invite): the page alone in the middle, in a 400 px column. */
export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-screen place-items-center p-4">
      <div className="w-full max-w-[400px] space-y-4">{children}</div>
    </main>
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
  /** A small line over the title. */
  eyebrow?: string;
  /** The indigo logo square over a centred title (v5 A_SignIn). */
  logo?: boolean;
  /** The words for a refused sign-in (401), in place of the server's. */
  refusedText?: string;
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
        throw new Error(response?.status === 401 && props.refusedText ? props.refusedText : errorText(error));
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
      // The first field that can be typed in (Email on sign in; not an invite's read-only email) gets the focus back.
      form.current?.querySelector<HTMLInputElement>("input:not([readonly])")?.focus();
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

  const content = (
    <>
          {props.logo && <span aria-hidden className="mx-auto block size-8 rounded-lg bg-accent" />}
          {props.eyebrow && <p className="text-xs text-muted">{props.eyebrow}</p>}
          <h1 className={`text-xl font-semibold ${props.logo ? "text-center" : ""}`}>{props.title}</h1>
          {props.intro}
          {/* v5 A_SignIn, A_Setup, A_Invite: the field labels are muted, 13 px. */}
          <form ref={form} onSubmit={onSubmit} className="flex flex-col gap-4 [&_label]:font-normal [&_label]:text-muted">
            {props.fields.map((f) =>
              f.value !== undefined ? (
                <TextField key={f.name} label={f.label} type={f.type ?? "text"} readOnly value={f.value} />
              ) : (
                <TextField key={f.name} label={f.label} hint={f.hint} type={f.type ?? "text"} autoComplete={f.autoComplete} minLength={f.minLength} required disabled={mutation.isPending} value={values[f.name] ?? ""} onChange={(e) => set(f.name, e.target.value)} />
              ),
            )}
            {/* v5: a refusal is plain red words under the fields, not a box. */}
            {mutation.isError && !(mutation.error instanceof Throttled) && (
              <p role="alert" className="text-sm text-danger">
                {mutation.error.message}
              </p>
            )}
            <Button type="submit" busy={mutation.isPending} disabled={throttled} reason={throttled ? "Too many tries. Wait a minute and try again." : undefined} className="w-full">
              {mutation.isPending ? (props.busyLabel ?? props.submitLabel) : props.submitLabel}
            </Button>
          </form>
          {props.footer}
    </>
  );
  return <AuthShell>{content}</AuthShell>;
}
