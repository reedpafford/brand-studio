import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { Button, TextArea, useToast } from "../components";
import { errorText as errorClass } from "../ui";

type Asset = components["schemas"]["AssetOut"];
type Body = { notes?: string; role?: string; description?: string };

/** The approved look and the role's words disagree (Biscuit drawn a French bulldog, written a golden retriever): say so,
 * with the words rewritten to match. "Update to match" puts them on this video's own look (any editor); the owner (or the
 * author before publishing) can also put the script's role right. Each has Undo. A look approved before this check
 * offers the check itself, at its price. */
export function RoleTextFit({ asset, projectId, stopFor, onDone }: { asset: Asset; projectId: number; stopFor: (cost: number | undefined) => string | null; onDone: () => Promise<unknown> }) {
  const fit = asset.text_fit;
  const toast = useToast();
  const title = asset.role || asset.name;
  const [words, setWords] = useState(fit?.description ?? "");
  const path = { project_id: projectId, slot_id: asset.slot_id! };
  const save = useMutation({
    mutationFn: async (body: Body) => {
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
  const press = (body: Body, was: Body, said: string) =>
    save.mutate(body, {
      onSuccess: async () => {
        await onDone();
        toast(said, async () => {
          await save.mutateAsync(was);
          await onDone();
        });
      },
    });
  const error = (save.error ?? check.error)?.message;

  if (fit) {
    const script = { ...(fit.name ? { role: fit.name } : {}), ...(fit.description ? { description: fit.description } : {}) };
    return (
      <div className="w-full space-y-2 rounded-md bg-warning-soft p-2 text-sm" role="note" aria-label={`Role words for ${title}`}>
        <p>{fit.seen}</p>
        {fit.update_look && (
          <>
            <TextArea label="How this video describes them" rows={3} maxLength={2000} value={words} onChange={(e) => setWords(e.target.value)} />
            <Button variant="secondary" busy={save.isPending} disabled={!words.trim()} reason={words.trim() ? undefined : "Say who they are"} onClick={() => press({ notes: words.trim() }, { notes: fit.notes }, `${title} now matches the look in this video.`)}>
              Update to match
            </Button>
          </>
        )}
        {fit.update_script && (
          <Button variant="ghost" busy={save.isPending} onClick={() => press(script, { role: asset.role, description: asset.description }, `Updated the script's role for ${title}.`)}>
            Update the script's role too
          </Button>
        )}
        {fit.note && <p className="text-muted">{fit.note}</p>}
        {error && <p role="alert" className={errorClass}>{error}</p>}
      </div>
    );
  }
  if (asset.text_check_credits == null) return null;
  const decline = stopFor(asset.text_check_credits);
  return (
    <div className="w-full space-y-1">
      <Button variant="ghost" busy={check.isPending} charge="estimate" price={asset.text_check_credits} reason={decline} disabled={!!decline} onClick={() => check.mutate()}>
        Check the words against the look
      </Button>
      {error && <p role="alert" className={errorClass}>{error}</p>}
    </div>
  );
}
