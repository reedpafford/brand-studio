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
import { SongRow, useSongLength } from "./SongParts";
import { beingMade } from "./ScriptsPage";
import { useAllowanceStop, useScript, useWeek } from "./useScript";
import { MakeSettings, useMakeEstimate, type Picks } from "./MakeSettings";

const LETTER = ["A", "B", "C"];
const SHOWN = 8;

/** A ready version before it is made: its words, cast and plan. "Make this version" reserves it and opens the video at Plan,
 *  with the plan being made (#941), or the shots when the owner's plan is approved. */
export function VersionPanel({ scriptId, slot, brandId, onClose }: { scriptId: number; slot: number; brandId: number; onClose: () => void }) {
  const script = useScript(scriptId);
  const cast = useCast(scriptId);
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // S6: with the owner's plan approved, starting makes the shots from it, not a plan (#934); the same one paid call.
  const ownerPlan = useQuery({
    queryKey: ["draft-plan", scriptId, slot],
    queryFn: async () => {
      const r = await fetch(`${location.origin}/api/scripts/${scriptId}/drafts/${slot}/plan`, { credentials: "include" });
      return r.ok ? ((await r.json()) as { status: string }) : null; // 404: no plan yet
    },
  });
  const planned = ownerPlan.data?.status === "approved";
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const [all, setAll] = useState(false);
  const [picks, setPicks] = useState<Picks>({}); // the Video settings row's picks (VS1), sent with the press
  const s = script.data;
  const v = s?.versions.find((x) => x.slot === slot);
  const letter = LETTER[slot] ?? String(slot + 1);
  const make = useMutation({
    mutationFn: async () => {
      // #956: the picks go as the body, none when nothing was changed.
      const { data, error } = await api.POST("/scripts/{script_id}/drafts/{slot}/produce", { params: { path: { script_id: scriptId, slot } }, ...(Object.keys(picks).length ? { body: picks } : {}) });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (made) => {
      await queryClient.invalidateQueries({ queryKey: ["scripts"] });
      await queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] });
      // #941: with no saved preview the plan is made first; with the owner's approved plan, the shots.
      const shots = (made as { breakdown_job_id?: number | null }).breakdown_job_id != null;
      toast(`Version ${letter} is yours. Next: ${shots ? "the shots" : "the plan"}.`);
      navigate(`/b/${brandId}/projects/${made.project_id}?step=plan`);
    },
  });
  // With no saved preview, starting makes the plan, or the shots from an approved owner's plan (one paid call each, #941);
  // with one saved, making the version is free.
  const cost = v?.has_breakdown ? undefined : rates.data?.find((r) => r.kind === "write-claude")?.credits_per_unit;
  const stop = useAllowanceStop(s, cost);
  const week = useWeek(s); // an editor making their own script sees how much of the week is used
  const songLength = useSongLength(scriptId, s?.kind === "song");
  const lines = (v?.text ?? "").split("\n");
  const readyToMake = v?.status === "approved";
  // The whole video's price follows the picks (#956's estimate); over the video limit, the press says why.
  const estimate = useMakeEstimate(scriptId, slot, picks, readyToMake);
  const whole = estimate.data?.credits ?? v?.estimate_credits ?? 0;
  const held = stop ?? (estimate.data?.over_cap ? estimate.data.reason || "Over the video limit." : null);
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
          {s.kind === "song" && <section aria-label="Song"><SongRow scriptId={scriptId} /></section>}
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
              {(cast.data ?? []).length === 0 && <span className="text-sm text-muted">Everyone is made in Cast</span>}
              {(cast.data ?? []).map((c) => (
                <Badge key={c.id} icon={c.locked ? Lock : undefined}>
                  {c.sheet_file_id && c.locked && <img src={fileUrl(c.sheet_file_id)} alt="" className="size-4 rounded-sm object-cover" />}
                  {c.role}
                  {c.locked ? " · Locked look" : " · Look made in Cast"}
                </Badge>
              ))}
            </div>
          </section>
          <section aria-label="Breakdown" className="space-y-1">
            <h3 className="text-sm font-medium text-muted">Breakdown</h3>
            <p>
              {v.has_breakdown
                ? [`Planned${v.planned_by ? ` by ${v.planned_by.name}` : ""}`, v.seconds ? `${Math.round(v.seconds)} s` : null, v.clips ? `${v.clips} clip${v.clips === 1 ? "" : "s"}` : null].filter(Boolean).join(" · ")
                : planned
                  ? "From the owner's plan: the shots are made when you start"
                  : "The plan is made when you start"}
            </p>
          </section>
          {readyToMake && <MakeSettings script={s} defaults={v.flavours ?? {}} picks={picks} onPick={setPicks} />}
          {readyToMake && whole > 0 && (
            <p className="text-sm text-muted">
              {/* One line that ties the button's price to the whole video's (#749 LW5). */}
              {cost !== undefined ? `Starting costs ${wholeCredits(cost)} (${planned ? "the shots" : "the plan"}) · the whole video about ${wholeCredits(whole)} credits` : `Starting is free · the whole video about ${wholeCredits(whole)} credits`}
              {songLength && ` · ${songLength} song`}
              {week && ` · This week: ${Math.round(week.used)} of ${Math.round(week.allowed)}`}
            </p>
          )}
          {estimate.isError && <p role="alert" className={errorClass}>{estimate.error.message}</p>}
          {make.isError && <p role="alert" className={errorClass}>{make.error.message}</p>}
          {readyToMake ? (
            <Button charge="estimate" price={cost} disabled={held !== null} reason={held} busy={make.isPending} onClick={() => make.mutate()} className="w-full">
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
