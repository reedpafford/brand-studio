import { useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { errorText } from "../api/client";
import { btnPrimary, card, errorText as errorClass, input } from "../ui";

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
    <main className="mx-auto flex min-h-screen max-w-[432px] flex-col justify-start gap-4 p-4 pt-[20vh] sm:justify-center sm:pt-4">
      <div className={`${card} space-y-4`}>
      <h1 className="text-xl font-semibold">{props.title}</h1>
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        {props.fields.map((f) => (
          <label key={f.name} className="flex flex-col gap-1 text-sm">
            {f.label}
            <input
              className={`${input} min-h-11`}
              type={f.type ?? "text"}
              autoComplete={f.autoComplete}
              required
              value={values[f.name] ?? ""}
              onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
            />
          </label>
        ))}
        {mutation.isError && (
          <p role="alert" className={errorClass}>
            {mutation.error.message}
          </p>
        )}
        <button
          className={`${btnPrimary} min-h-11`}
          disabled={mutation.isPending}
        >
          {props.submitLabel}
        </button>
      </form>
      {props.footer}
      </div>
    </main>
  );
}
