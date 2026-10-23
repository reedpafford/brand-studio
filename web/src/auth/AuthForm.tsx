import { useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { errorText } from "../api/client";

export type Field = { name: string; label: string; type?: string; autoComplete?: string };
type Me = { id: number };
type Result = { data?: Me; error?: unknown };

/** One card with labelled fields. Submits, then refreshes "me" and goes to the app. */
export function AuthForm(props: {
  title: string;
  fields: Field[];
  submitLabel: string;
  submit: (values: Record<string, string>) => Promise<Result>;
  footer?: ReactNode;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const mutation = useMutation({
    mutationFn: async () => {
      const { data, error } = await props.submit(values);
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      navigate("/", { replace: true });
    },
  });
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    mutation.mutate();
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold">{props.title}</h1>
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        {props.fields.map((f) => (
          <label key={f.name} className="flex flex-col gap-1 text-sm">
            {f.label}
            <input
              className="rounded border border-neutral-300 px-3 py-2 text-base"
              type={f.type ?? "text"}
              autoComplete={f.autoComplete}
              required
              value={values[f.name] ?? ""}
              onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
            />
          </label>
        ))}
        {mutation.isError && (
          <p role="alert" className="text-sm text-red-700">
            {mutation.error.message}
          </p>
        )}
        <button
          className="rounded bg-neutral-900 px-3 py-2 text-white disabled:opacity-50"
          disabled={mutation.isPending}
        >
          {props.submitLabel}
        </button>
      </form>
      {props.footer}
    </main>
  );
}
