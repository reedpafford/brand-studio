import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, errorText } from "../api/client";
import { Button, Card, Dialog, Dot, wholeCredits } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { SongFacts } from "./SongParts";
import type { Script } from "./useScript";

const LETTER = ["A", "B", "C"];
type Version = Script["versions"][number];

/** What a version brings with it, in one quiet line (G_Publish). Planned costs read "about N credits (planned)" (rule 34). */
function about(v: Version) {
  if (v.status === "draft") return "Draft: not approved yet";
  return v.has_breakdown ? `Planned${v.seconds ? ` · ${Math.round(v.seconds)} s` : ""}${v.estimate_credits ? ` · about ${wholeCredits(v.estimate_credits)} credits (planned)` : ""}` : "Words approved · each video plans its own shots";
}

/** Publish to the library (v5 G_Publish): optional, for sharing with editors. A list of the versions with Approve, a card
 *  on what publishing does, then Not yet and Publish. After it the words are final; a published script can be duplicated. */
export function PublishStep({ script: s, brandId, asking, onAsking, onNotYet }: { script: Script; brandId: number; asking: boolean; onAsking: (v: boolean) => void; onNotYet: () => void }) {
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const versions = s.versions.filter((v) => v.text.trim() !== "");
  const approve = useMutation({
    mutationFn: async ({ slot, yes }: { slot: number; yes: boolean }) => {
      const args = { params: { path: { script_id: s.id, slot } } };
      const { data, error } = yes ? await api.POST("/scripts/{script_id}/drafts/{slot}/approve", args) : await api.DELETE("/scripts/{script_id}/drafts/{slot}/approve", args);
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => queryClient.setQueryData(["script-lib", s.id], data),
  });
  const publish = useMutation({
    mutationFn: async () => {
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
  // The server publishes only when every version is approved (or removed), as Variations says.
  const open = versions.filter((v) => v.status === "draft");
  const reason = versions.length === 0 ? "Write the script first" : open.length > 0 ? `Approve or remove version ${open.map((v) => LETTER[v.slot]).join(" and ")} first` : null;
  const words = s.kind === "song" ? "lyrics" : "words";

  return (
    <section className="flex max-w-[720px] flex-col gap-4" aria-labelledby="publish-title">
      <div className="flex flex-col gap-1">
        <h1 id="publish-title" className="font-display text-2xl font-semibold tracking-tight">
          {s.published ? "In the library" : "Publish to the library"}
        </h1>
        <p className="text-text/80">
          {s.published
            ? `It's in the team's library, and its ${words} are final. To change them, duplicate the script.`
            : "Publishing keeps this script for the team: editors can make videos from it. You don't need to publish to make a video yourself."}
        </p>
      </div>
      {(publish.isError || duplicate.isError || approve.isError) && <p role="alert" className={errorClass}>{(publish.error ?? duplicate.error ?? approve.error)?.message}</p>}
      <ul aria-label="Versions">
        {versions.map((v) => (
          <li key={v.slot} aria-label={`Version ${LETTER[v.slot]}`} className="flex min-h-14 flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-border py-2">
            <div className="min-w-0">
              <p className="font-medium">Version {LETTER[v.slot]}</p>
              <p className="text-xs tabular-nums text-muted">{about(v)}</p>
            </div>
            {v.status === "draft" && !s.published ? (
              <Button variant="secondary" dense busy={approve.isPending && approve.variables?.slot === v.slot} onClick={() => approve.mutate({ slot: v.slot, yes: true })}>
                Approve version {LETTER[v.slot]}
              </Button>
            ) : (
              <span className="flex items-center gap-2 text-xs">
                <Dot tone="success">{s.published ? "Published" : "Approved"}</Dot>
                {!s.published && (
                  <Button variant="ghost" dense className="text-muted" aria-label={`Undo approval of version ${LETTER[v.slot]}`} busy={approve.isPending && approve.variables?.slot === v.slot} onClick={() => approve.mutate({ slot: v.slot, yes: false })}>
                    Undo
                  </Button>
                )}
              </span>
            )}
          </li>
        ))}
      </ul>
      {s.kind === "song" && (
        <dl className="space-y-2 text-sm">
          <SongFacts script={s} />
        </dl>
      )}
      {s.published ? (
        <div className="flex justify-end">
          <Button variant="secondary" icon={Copy} busy={duplicate.isPending} onClick={() => duplicate.mutate()}>
            Duplicate script
          </Button>
        </div>
      ) : (
        <>
          <Card className="flex flex-col gap-2">
            <p className="font-medium">When it's published</p>
            <p className="text-text/80">Their {words} become final. Editors see it under Scripts › Ready to make, and each video they start waits for the owner's OK.</p>
          </Card>
          <div className="flex flex-wrap items-start justify-end gap-2">
            <Button variant="ghost" className="text-muted" onClick={onNotYet}>
              Not yet
            </Button>
            <Button disabled={!!reason} reason={reason} onClick={() => onAsking(true)}>
              Publish {versions.length} version{versions.length === 1 ? "" : "s"}
            </Button>
          </div>
        </>
      )}
      {asking && !s.published && (
        <Dialog title={`Publish ${versions.length} version${versions.length === 1 ? "" : "s"} of ${s.title}?`} cancelLabel="Not yet" actionLabel="Publish" busy={publish.isPending} onCancel={() => onAsking(false)} onConfirm={() => publish.mutate()}>
          {s.kind === "song" ? "Its lyrics become final." : "Their words become final."}
        </Dialog>
      )}
    </section>
  );
}
