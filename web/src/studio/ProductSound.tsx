import { useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2, Upload } from "lucide-react";
import { api, errorText } from "../api/client";
import { fileUrl, uploadFile } from "../api/upload";
import type { Item } from "../library/kinds";
import { SAMPLE_TYPES } from "../library/Voices";
import { PlayButton } from "./libraryParts";

/** The product's own sound (an alarm's whistle, a click): kept on the product, and laid over the shots the director
 *  marks it heard in: loud on its own, down under a spoken line. One file; adding another replaces it. Free. */
export function ProductSound({ item }: { item: Item }) {
  const queryClient = useQueryClient();
  const picker = useRef<HTMLInputElement>(null);
  const set = useMutation({
    mutationFn: async (file: File | null) => {
      const voice_file_id = file ? (await uploadFile(file)).id : null;
      const { error, response } = await api.PATCH("/library/{kind}/{item_id}", { params: { path: { kind: "prop", item_id: item.id } }, body: { voice_file_id } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["library", "prop"] }),
  });
  const has = item.voice_file_id != null;
  return (
    <section className="how" aria-label="Its sound">
      <h3>Its sound</h3>
      {has ? (
        <div className="snd">
          <PlayButton src={fileUrl(item.voice_file_id!)} of={`${item.name}’s sound`} />
          <span className="clip">{item.voice_file_name || "A sound file"}</span>
        </div>
      ) : (
        <p className="hint">None yet. Add the sound it makes, and the cut plays it over the shots where it is heard.</p>
      )}
      <div className="offers">
        <button type="button" className="btn soft" disabled={set.isPending} onClick={() => picker.current?.click()}>
          <Upload size={14} strokeWidth={1.75} aria-hidden />
          {set.isPending ? "Saving…" : has ? "Replace" : "Add its sound"}
        </button>
        {has && (
          <button type="button" className="btn ghost" disabled={set.isPending} onClick={() => set.mutate(null)}>
            <Trash2 size={14} strokeWidth={1.75} aria-hidden />
            Remove
          </button>
        )}
      </div>
      <input ref={picker} type="file" hidden aria-label={`A sound file for ${item.name}`} accept={SAMPLE_TYPES} onChange={(e) => (e.target.files?.[0] && set.mutate(e.target.files[0]), (e.target.value = ""))} />
      {set.isError && (
        <p className="hint bad" role="alert">
          {set.error.message}
        </p>
      )}
      {has && <p className="hint">The cut plays it over the shots where the director marks it heard: loud on its own, lower under a spoken line.</p>}
    </section>
  );
}
