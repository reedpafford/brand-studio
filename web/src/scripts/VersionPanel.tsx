import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import { Badge, Button, Panel, Skeleton, wholeCredits } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useCast } from "./useCast";
import { beingMade } from "./ScriptsPage";
import { useAllowanceStop, useScript, useWeek } from "./useScript";

const LETTER = ["A", "B", "C"];
const SHOWN = 8;

/** A ready version before it is made: its words, cast and plan. "Make this version" reserves it and opens the video at Breakdown. */
export function VersionPanel({ scriptId, slot, brandId, onClose }: { scriptId: number; slot: number; brandId: number; onClose: () => void }) {
  const script = useScript(scriptId);
  const cast = useCast(scriptId);
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const [all, setAll] = useState(false);
  const s = script.data;
  const v = s?.versions.find((x) => x.slot === slot);
  const letter = LETTER[slot] ?? String(slot + 1);
  const make = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts/{script_id}/drafts/{slot}/produce", { params: { path: { script_id: scriptId, slot } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (made) => {
      await queryClient.invalidateQueries({ queryKey: ["scripts"] });
      await queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] });
      toast(`Version ${letter} is yours. Next: the breakdown.`);
      navigate(`/b/${brandId}/projects/${made.project_id}?step=breakdown`);
    },
  });
  // With no saved breakdown, starting one is a paid call; with one saved, making the version is free.
  const cost = v?.has_breakdown ? undefined : rates.data?.find((r) => r.kind === "write-claude")?.credits_per_unit;
  const stop = useAllowanceStop(s, cost);
  const week = useWeek(s); // an editor making their own script sees how much of the week is used
  const lines = (v?.text ?? "").split("\n");
  const readyToMake = v?.status === "approved";
  return (
    <Panel title={s ? `${s.title} · Version ${letter}` : "Version"} onClose={onClose}>
      {!s || !v ? (
        <div role="status" aria-label="Loading" className="space-y-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-10" />
        </div>
      ) : (
        <div className="space-y-5">
          {v.variation_of && <p className="-mt-2 text-sm text-muted">Variation of {v.variation_of}</p>}
          <section aria-label="The words" className="space-y-2">
            <p className="whitespace-pre-wrap font-script leading-[1.6] [overflow-wrap:anywhere]">{(all ? lines : lines.slice(0, SHOWN)).join("\n")}</p>
            {lines.length > SHOWN && (
              <Button variant="ghost" onClick={() => setAll(!all)}>
                {all ? "Show less" : "Show all"}
              </Button>
            )}
          </section>
          <section aria-label="Characters" className="space-y-2">
            <h3 className="text-sm font-medium text-muted">Characters</h3>
            <div className="flex flex-wrap gap-2">
              {(cast.data ?? []).length === 0 && <span className="text-sm text-muted">Everyone is made at Assets</span>}
              {(cast.data ?? []).map((c) => (
                <Badge key={c.id} icon={c.locked ? Lock : undefined}>
                  {c.sheet_file_id && c.locked && <img src={fileUrl(c.sheet_file_id)} alt="" className="size-4 rounded-sm object-cover" />}
                  {c.role}
                  {c.locked ? " · Locked look" : " · Look made at Assets"}
                </Badge>
              ))}
            </div>
          </section>
          <section aria-label="Breakdown" className="space-y-1">
            <h3 className="text-sm font-medium text-muted">Breakdown</h3>
            <p>
              {v.has_breakdown
                ? [`Planned${v.planned_by ? ` by ${v.planned_by.name}` : ""}`, v.seconds ? `${Math.round(v.seconds)} s` : null, v.clips ? `${v.clips} clip${v.clips === 1 ? "" : "s"}` : null].filter(Boolean).join(" · ")
                : "Planned automatically when you start"}
            </p>
          </section>
          {readyToMake && v.estimate_credits > 0 && (
            <p className="text-sm text-muted">
              About {wholeCredits(v.estimate_credits)} credits to make
              {week && ` · This week: ${Math.round(week.used)} of ${Math.round(week.allowed)}`}
            </p>
          )}
          {make.isError && <p role="alert" className={errorClass}>{make.error.message}</p>}
          {readyToMake ? (
            <Button price={cost} disabled={stop !== null} reason={stop} busy={make.isPending} onClick={() => make.mutate()} className="w-full">
              Make this version
            </Button>
          ) : (
            <p className="text-sm text-muted">{beingMade(v.status) ? `${v.editor?.name ?? "Someone"} is making this version.` : "This version isn't ready to make."}</p>
          )}
        </div>
      )}
    </Panel>
  );
}
