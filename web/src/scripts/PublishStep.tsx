import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Info, Lock } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import { Badge, Button, Card, Dialog } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useCast } from "./useCast";
import { SongFacts } from "./SongParts";
import type { Script } from "./useScript";

const LETTER = ["A", "B", "C"];
const NAME = ["Original", "Variation", "Variation"];

/** Step 7: a card per version, then Publish. After it the words are final; a published script can only be duplicated. */
export function PublishStep({ script: s, brandId, asking, onAsking }: { script: Script; brandId: number; asking: boolean; onAsking: (v: boolean) => void }) {
  const cast = useCast(s.id);
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const versions = s.versions.filter((v) => v.text.trim() !== "");
  const slots = cast.data ?? [];
  const publish = useMutation({
    mutationFn: async () => {
      // Every version's words are approved first; then it goes to the library.
      for (const v of s.versions.filter((x) => x.status === "draft" && x.text.trim() !== "")) {
        const { error, response } = await api.POST("/scripts/{script_id}/drafts/{slot}/approve", { params: { path: { script_id: s.id, slot: v.slot } } });
        if (!response.ok) throw new Error(errorText(error));
      }
      const { data, error } = await api.POST("/scripts/{script_id}/publish", { params: { path: { script_id: s.id } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey: ["scripts"] });
      queryClient.setQueryData(["script-lib", s.id], data);
      toast(`Published. ${versions.length} version${versions.length === 1 ? "" : "s"} ${versions.length === 1 ? "is" : "are"} ready to make.`);
      navigate(`/b/${brandId}/scripts`);
    },
    onError: () => onAsking(false),
  });
  const duplicate = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts/{script_id}/duplicate", { params: { path: { script_id: s.id } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (made) => {
      await queryClient.invalidateQueries({ queryKey: ["scripts"] });
      toast("Duplicated as a new draft.");
      navigate(`/b/${brandId}/scripts/${made.id}?step=script`);
    },
  });

  return (
    <div className="space-y-4">
      {s.published ? (
        <div>
          <Button variant="secondary" icon={Copy} busy={duplicate.isPending} onClick={() => duplicate.mutate()}>
            Duplicate script
          </Button>
        </div>
      ) : (
        <p className="flex max-w-[680px] items-start gap-2 text-sm text-muted">
          <Info size={20} strokeWidth={1.75} aria-hidden className="shrink-0" />
          {s.kind === "song" ? "Publishing makes this ready to make. After that the lyrics can't change (each video still picks its own take). To change the lyrics, duplicate the script." : "Publishing makes these versions ready to make. After that their words can't change. To change one, duplicate the script."}
        </p>
      )}
      {(publish.isError || duplicate.isError) && <p role="alert" className={errorClass}>{(publish.error ?? duplicate.error)?.message}</p>}
      <ul className="grid gap-4 lg:grid-cols-3">
        {versions.map((v) => (
          <li key={v.slot} aria-label={`Version ${LETTER[v.slot]}`}>
            <Card className="h-full space-y-3 text-sm">
              <h3 className="font-display text-md font-bold">
                {LETTER[v.slot]} · {NAME[v.slot] ?? "Variation"}
              </h3>
              <p className="line-clamp-4 whitespace-pre-wrap font-script [overflow-wrap:anywhere]">{v.text}</p>
              <dl className="space-y-2">
                {s.kind === "song" && <SongFacts script={s} />}
                <div>
                  <dt className="font-medium text-muted">Words</dt>
                  <dd className="flex items-center gap-1">
                    {v.status !== "draft" && <Check size={16} strokeWidth={1.75} aria-hidden className="text-success" />}
                    {v.status === "draft" ? "When you publish" : "Approved"}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-muted">Cast</dt>
                  <dd className="flex flex-wrap gap-2">
                    {slots.length === 0 && <span className="text-muted">Everyone is made at Assets</span>}
                    {slots.map((c) => (
                      <Badge key={c.id} icon={c.locked ? Lock : undefined}>
                        {c.sheet_file_id && c.locked && <img src={fileUrl(c.sheet_file_id)} alt="" className="size-4 rounded-sm object-cover" />}
                        {c.role}
                        {!c.locked && " · made at Assets"}
                      </Badge>
                    ))}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-muted">Breakdown</dt>
                  <dd>{v.has_breakdown ? `Planned${v.seconds ? ` · ${Math.round(v.seconds)} s` : ""}` : "Runs when an editor starts"}</dd>
                </div>
              </dl>
            </Card>
          </li>
        ))}
      </ul>
      {asking && !s.published && (
        <Dialog title={`Publish ${versions.length} version${versions.length === 1 ? "" : "s"} of ${s.title}?`} cancelLabel="Not yet" actionLabel="Publish" busy={publish.isPending} onCancel={() => onAsking(false)} onConfirm={() => publish.mutate()}>
          {s.kind === "song" ? "Its lyrics become final." : "Their words become final."}
        </Dialog>
      )}
    </div>
  );
}
