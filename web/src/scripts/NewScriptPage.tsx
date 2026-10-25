import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { DescriptionForm, type Description } from "./DescriptionForm";
import { ReelPicker } from "./ReelImport";

/** Step 1 before the script exists: Create script makes the draft and moves on to the script. */
export function NewScriptPage() {
  const brandId = Number(useParams().brandId);
  const { data: brands } = useBrands();
  const brand = brands?.find((b) => b.id === brandId);
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"describe" | "reel">("describe");
  const create = useMutation({
    mutationFn: async (d: Description) => {
      const { data, error } = await api.POST("/scripts", { body: { brand_id: brandId, title: d.title, description: d.description, notes: d.notes, reference_id: d.reference_id, reference_replace: d.reference_replace, text: "" } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (made) => {
      await queryClient.invalidateQueries({ queryKey: ["scripts"] });
      toast("Draft saved. Next: the script.");
      navigate(`/b/${brandId}/scripts/${made.id}?step=script`);
    },
  });
  return (
    <main className="mx-auto max-w-content space-y-5 p-4 sm:p-8">
      <Link to={`/b/${brandId}/scripts`} className="inline-flex min-h-control items-center gap-1 text-accent-text hover:underline lg:min-h-control-dense">
        <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
        Scripts
      </Link>
      <h1 className="type-page">New script</h1>
      <div role="radiogroup" aria-label="How to start" className="inline-flex w-full rounded-lg border border-border bg-surface p-1 sm:w-auto">
        {(
          [
            ["describe", "Describe it"],
            ["reel", "Import a reel"],
          ] as const
        ).map(([id, label]) => (
          <button key={id} type="button" role="radio" aria-checked={mode === id} onClick={() => setMode(id)} className={`min-h-control flex-1 whitespace-nowrap rounded-md px-4 font-medium sm:flex-none ${mode === id ? "bg-surface-2 text-text" : "text-muted hover:text-text"}`}>
            {label}
          </button>
        ))}
      </div>
      {mode === "reel" ? <ReelPicker brandId={brandId} /> : null}
      {mode === "describe" && <DescriptionForm brandName={brand?.name} submitLabel="Create script" busy={create.isPending} error={create.isError ? create.error.message : null} onSubmit={(d) => create.mutate(d)} />}
    </main>
  );
}
