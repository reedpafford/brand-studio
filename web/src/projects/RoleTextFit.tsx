import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { Button, Field, TextArea, useToast } from "../components";
import { errorText as errorClass } from "../ui";

type Asset = components["schemas"]["AssetOut"];

/** The approved look and the role's words disagree (Biscuit drawn a French bulldog, written a golden retriever):
 * say so, with the words rewritten to match, ready to edit and save in one press (Undo puts them back).
 * A look approved before this check offers the check itself, at its price. */
export function RoleTextFit({ asset, projectId, stopFor, onDone }: { asset: Asset; projectId: number; stopFor: (cost: number | undefined) => string | null; onDone: () => Promise<unknown> }) {
  const fit = asset.text_fit;
  const toast = useToast();
  const title = asset.role || asset.name;
  const [name, setName] = useState(fit?.name ?? "");
  const [description, setDescription] = useState(fit?.description ?? "");
  const path = { project_id: projectId, slot_id: asset.slot_id! };
  const save = useMutation({
    mutationFn: async (body: { role?: string; description?: string }) => {
      const { response, error } = await api.PATCH("/projects/{project_id}/assets/slots/{slot_id}", { params: { path }, body });
      if (!response.ok) throw new Error(errorText(error));
    },
  });
  const check = useMutation({
    mutationFn: async () => {
      const { response, error } = await api.POST("/projects/{project_id}/assets/slots/{slot_id}/check-text", { params: { path } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: onDone,
  });
  const update = () => {
    const was = { ...(fit!.name ? { role: asset.role } : {}), description: asset.description };
    save.mutate({ ...(fit!.name ? { role: name.trim() } : {}), description: description.trim() }, {
      onSuccess: async () => {
        await onDone();
        toast(`Updated ${title}'s description.`, async () => {
          await save.mutateAsync(was);
          await onDone();
        });
      },
    });
  };
  const error = (save.error ?? check.error)?.message;

  if (fit) {
    return (
      <div className="space-y-2 rounded-md bg-warning-soft p-2 text-sm" role="note" aria-label={`Role words for ${title}`}>
        <p>{fit.seen} The role's words say otherwise.</p>
        {fit.name && <Field label="Role" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />}
        <TextArea label="Description" rows={3} maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} />
        <Button variant="secondary" busy={save.isPending} disabled={!description.trim()} reason={description.trim() ? undefined : "Say who the role is"} onClick={update}>
          Update the description
        </Button>
        {error && <p role="alert" className={errorClass}>{error}</p>}
      </div>
    );
  }
  if (asset.text_check_credits == null) return null;
  const decline = stopFor(asset.text_check_credits);
  return (
    <div className="space-y-1">
      <Button variant="ghost" busy={check.isPending} price={asset.text_check_credits} reason={decline} disabled={!!decline} onClick={() => check.mutate()}>
        Check the description against the look
      </Button>
      {error && <p role="alert" className={errorClass}>{error}</p>}
    </div>
  );
}
