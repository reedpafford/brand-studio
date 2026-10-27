import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { Dialog, Field, useToast } from "../components";

/** Save a video's own look to Cast & places as a normal character, with an Undo that deletes the copy. */
export function useSaveToCast({ projectId, slot, refresh }: { projectId: number; slot: number; refresh: () => Promise<unknown> }) {
  const toast = useToast();
  const [saving, setSaving] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: async (name: string) => {
      const { data, error } = await api.POST("/projects/{project_id}/assets/slots/{slot_id}/save-to-library", { params: { path: { project_id: projectId, slot_id: slot } }, body: { name } });
      if (!data) throw new Error(errorText(error));
      return { copy: data.library_item_id, name };
    },
    onSuccess: async ({ copy, name }) => {
      setSaving(null);
      await refresh();
      toast(`${name} saved to Cast & places.`, async () => {
        await api.DELETE("/library/{kind}/{item_id}", { params: { path: { kind: "character", item_id: copy } } });
        await refresh();
      });
    },
  });
  const dialog = saving !== null && (
    <Dialog title="Save to Cast & places" actionLabel="Save" busy={save.isPending} onCancel={() => { setSaving(null); save.reset(); }} onConfirm={() => save.mutate(saving.trim())}>
      <div className="space-y-2">
        <Field label="Name" value={saving} onChange={(e) => setSaving(e.target.value)} error={save.isError ? save.error.message : null} maxLength={80} />
        <p className="text-sm text-muted">It becomes a normal character any script can use. This video keeps its look either way.</p>
      </div>
    </Dialog>
  );
  return { saving, setSaving, save, dialog };
}
