import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { studioName } from "../auth/pages";
import { Button, Card, Skeleton } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

/** The name an invite link shows. A stored slug like "owner-reed" reads as "Reed's studio" until Reed picks a name. */
export function StudioName({ owner }: { owner: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const workspace = useQuery({ queryKey: ["workspace"], queryFn: async () => (await api.GET("/workspace")).data ?? null });
  const [edit, setEdit] = useState<string | null>(null);
  const saved = workspace.data;
  const value = edit ?? (saved ? studioName(saved.name, owner) : "");
  const trimmed = value.trim();
  const reason = !saved || trimmed === saved.name ? "No changes yet" : trimmed === "" ? "Give the studio a name first" : null;

  const put = useMutation({
    mutationFn: async (name: string) => {
      const { data, error } = await api.PUT("/workspace", { body: { name } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => queryClient.setQueryData(["workspace"], data),
  });
  const save = () => {
    if (!saved) return;
    const before = saved.name;
    put.mutate(trimmed, {
      onSuccess: () => {
        setEdit(null);
        toast("Studio name saved.", () => put.mutate(before));
      },
    });
  };

  if (workspace.isPending) return <Skeleton className="h-28" />;
  if (!saved) return null;
  return (
    <section>
      <Card className="space-y-3">
        <div className="space-y-1">
          <label htmlFor="studio-name" className="font-medium">Studio name</label>
          <input id="studio-name" aria-describedby="studio-name-help" value={value} onChange={(e) => setEdit(e.target.value)} className="min-h-control w-full rounded-md border border-border-strong bg-surface px-3" />
          <p id="studio-name-help" className="text-sm text-muted">Shown on invite links.</p>
        </div>
        {put.isError && <p role="alert" className={errorClass}>{put.error.message}</p>}
        <div className="sm:flex sm:justify-end">
          <Button variant="secondary" dense busy={put.isPending} disabled={reason !== null} reason={reason} onClick={save} className="w-full sm:w-auto">
            Save
          </Button>
        </div>
      </Card>
    </section>
  );
}
