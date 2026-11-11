import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { studioName } from "../auth/pages";
import { Skeleton } from "../components";
import { SaveButton, SettingRow, type SettingsTop } from "./SettingRow";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

/** The name an invite link shows. A stored slug like "owner-reed" reads as "{owner}'s studio" until the owner picks a name. */
export function StudioName({ owner, top }: { owner: string; top: SettingsTop }) {
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

  if (workspace.isPending)
    return (
      <>
        {top()}
        <Skeleton className="h-28" />
      </>
    );
  if (!saved) return <>{top()}</>;
  return (
    <>
      {top(
        <SaveButton reason={reason} busy={put.isPending} onClick={save} />,
      )}
      <section aria-label="Studio" className="max-w-[900px]">
        <SettingRow htmlFor="studio-name" label="Studio name" help="Shown on invite links.">
          <input id="studio-name" value={value} onChange={(e) => setEdit(e.target.value)} className="min-h-control w-full max-w-[360px] rounded-md border border-border-strong bg-bg px-2.5 lg:min-h-control-dense" />
        </SettingRow>
        {put.isError && <p role="alert" className={`pt-3 ${errorClass}`}>{put.error.message}</p>}
      </section>
    </>
  );
}
