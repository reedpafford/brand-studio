import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, Lock, Pencil } from "lucide-react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useMe } from "../auth/useMe";
import { Badge, Button, Dialog, Field, Skeleton, StepPicker } from "../components";
import { useBrands } from "../shell/useBrands";
import { ActionBar } from "../shell/ActionBar";
import { useRail } from "../useMedia";
import { BreakdownStep } from "./BreakdownStep";
import { CastStep } from "./CastStep";
import { DirectionsStep } from "./DirectionsStep";
import { VariationsStep, variationsReason } from "./VariationsStep";
import { ScriptStep } from "./ScriptStep";
import { ReadReelButton, useReelImport } from "./ReelImport";
import { PublishStep } from "./PublishStep";
import { around, hasWords, isNarrated, lockReason, stepFromParam, stepStates, stepsFor } from "./flow";
import { NarrationStep } from "./NarrationStep";
import { SongStep } from "./SongStep";
import { TakesStep } from "./TakesStep";
import { useSongs } from "./useSongs";
import { ScriptMenu, toTarget, useDeleteScript, useMayDelete } from "./DeleteScript";
import { useScript, usePatchScript } from "./useScript";
import { FormatChip, LookSetting } from "./Looks";

/** The writing flow for one script, in the same frame as a video: header, step picker, Back and Next. */
export function ScriptFlowPage() {
  const brandId = Number(useParams().brandId);
  const brandName = useBrands().data?.find((b) => b.id === brandId)?.name;
  const id = Number(useParams().scriptId);
  const [params, setParams] = useSearchParams();
  const rail = useRail();
  const { data: me } = useMe();
  const script = useScript(id);
  const voiced = !!script.data && (script.data.kind === "song" || isNarrated(script.data)); // a song's takes, or a narrated script's narrations
  const songs = useSongs(id, voiced);
  const patch = usePatchScript(id);
  const navigate = useNavigate();
  const mayDelete = useMayDelete();
  const del = useDeleteScript(() => navigate(`/b/${brandId}/scripts`));
  const reel = useReelImport(id);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [asking, setAsking] = useState(false); // the Publish confirmation, opened from the Next slot
  // Something on this step would be lost by leaving (unsaved words, accepted directions not added): Next and every other way out ask once, and Next still always goes on.
  const [hold, setHold] = useState<{ title: string; body: string } | null>(null);
  const [leaving, setLeaving] = useState<(() => void) | null>(null);
  useEffect(() => {
    if (!hold) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [hold]);
  const allowance = useQuery({
    enabled: me?.role !== undefined && me.role !== "owner",
    queryKey: ["allowance"],
    queryFn: async () => (await api.GET("/credits/me")).data ?? null,
  });

  if (script.isPending || (voiced && songs.isPending))
    return (
      <div className="mx-auto max-w-content space-y-4 p-4 sm:p-8" role="status" aria-label="Loading">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-12" />
        <Skeleton className="h-64" />
      </div>
    );
  const s = script.data;
  if (!s) return <p className="p-6">That script doesn't exist.</p>;
  const takes = songs.data?.takes ?? [];
  // Only a Preferred take that sings the lyrics as they are now, and whose video fits the cap, counts: the screen holds the cap whatever the server says.
  const tooLong = (t: (typeof takes)[number]) => t.over_cap && t.trim_to == null;
  const fit = takes.find((t) => t.preferred && !t.out_of_date);
  const song = voiced ? { preferred: !!fit && !tooLong(fit), overCap: !!fit && tooLong(fit), takes: takes.filter((t) => !t.out_of_date && t.status === "ready").length, making: takes.some((t) => t.status === "making" || t.status === "timing"), older: takes.filter((t) => t.out_of_date).length } : undefined;
  const step = stepFromParam(s, params.get("step"));
  if (lockReason(step, s, song) !== null) return <Navigate to="?" replace />;
  const first = stepsFor(s)[0].id;
  const move = (to: string) => {
    setHold(null);
    setParams(to === first ? {} : { step: to });
  };
  const go = (to: string) => (hold ? setLeaving(() => () => move(to)) : move(to));
  const { prev, next } = around(s, step);
  const nextReason = !next ? null : step === "script" && !hasWords(s) ? "Write or paste the script first" : step === "variations" ? variationsReason(s) : lockReason(next.id, s, song);
  const label = stepsFor(s).find((x) => x.id === step)!.label;
  const toPublish = s.versions.filter((v) => v.text.trim() !== "").length;
  const toApprove = s.versions.filter((v) => v.text.trim() !== "" && v.status === "draft").length; // approved on its card first, as Variations says
  const publishReason = toPublish === 0 ? "Write the script first" : toApprove > 0 ? `Approve every version first (${toApprove} left)` : null;
  const publishButton = step === "publish" && !s.published && (
    <Button disabled={!!publishReason} reason={publishReason} onClick={() => setAsking(true)}>
      Publish {toPublish} version{toPublish === 1 ? "" : "s"}
    </Button>
  );
  // A script from a reel isn't ready to move on until the reel is read: Read this reel is the one amber button until then.
  const unread = step === "script" && !!reel.data && reel.data.status !== "done";
  const reelReady = unread && !s.published && !rail && (reel.data?.status === "ready" || reel.data?.status === "failed") && reel.data?.failed_step !== "prepare";
  const nextButton = reelReady ? <ReadReelButton scriptId={id} createdById={s.created_by_id} /> : publishButton || (next && !unread && (
    <Button disabled={nextReason !== null} reason={nextReason} onClick={() => go(next.id)}>
      Next: {next.label}
    </Button>
  ));
  const backButton = prev && (
    <Button variant="ghost" icon={ChevronLeft} aria-label={rail ? undefined : "Back"} onClick={() => go(prev.id)}>
      {rail ? "Back" : ""}
    </Button>
  );
  const published = s.published;
  // Who can see a draft: its author and Reed.
  const mine = s.created_by_id === me?.id;
  const draftNote = mine ? (me?.role === "owner" ? "Draft · only you can see it" : "Draft · only you and the owner can see it") : `Draft · ${s.created_by_name || "an editor"}'s, not published`;

  return (
    <main className={`mx-auto max-w-content space-y-4 p-4 sm:p-8 ${rail ? "" : "pb-28"}`}>
      <Link
        to={`/b/${brandId}/scripts`}
        onClick={(e) => {
          if (hold) {
            e.preventDefault();
            setLeaving(() => () => navigate(`/b/${brandId}/scripts`));
          }
        }}
        className="inline-flex min-h-control items-center gap-1 text-accent-text hover:underline lg:min-h-control-dense"
      >
        <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
        Scripts
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        {renaming === null ? (
          <h1 className="flex min-w-0 items-center gap-2 type-page">
            {published ? (
              <span className="min-w-0 break-words">{s.title}</span>
            ) : (
              <button type="button" aria-label={`Rename ${s.title}`} onClick={() => setRenaming(s.title)} className="min-h-control min-w-0 break-words text-left hover:underline sm:min-h-control-dense">
                {s.title}
              </button>
            )}
            {!published && (
              <button type="button" aria-label="Rename" onClick={() => setRenaming(s.title)} className="grid size-control shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2">
                <Pencil size={20} strokeWidth={1.75} aria-hidden />
              </button>
            )}
          </h1>
        ) : (
          <form
            className="flex w-full min-w-0 basis-full flex-wrap items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (renaming.trim()) patch.mutate({ title: renaming.trim() }, { onSuccess: () => setRenaming(null) });
            }}
          >
            <div className="min-w-48 flex-1">
              <Field label="Title" value={renaming} onChange={(e) => setRenaming(e.target.value)} error={patch.isError ? patch.error.message : null} maxLength={200} autoFocus />
            </div>
            <Button type="submit" busy={patch.isPending} disabled={!renaming.trim()}>
              Save
            </Button>
            <Button type="button" variant="ghost" onClick={() => setRenaming(null)}>
              Cancel
            </Button>
          </form>
        )}
        {published ? (
          <Badge tone="neutral" icon={Lock}>
            Published · final
          </Badge>
        ) : (
          <Badge tone="neutral">{draftNote}</Badge>
        )}
        <FormatChip kind={s.kind} />
        <LookSetting value={s.look} scriptId={s.id} queryKey={["script-lib", s.id]} readOnly={published} />
        {allowance.data && (
          <p className="ml-auto text-sm tabular-nums text-muted">
            This week: {Math.round(allowance.data.quick_clip_credits_used)} of {Math.round(allowance.data.quick_clip_credits_allowed)} credits
          </p>
        )}
        {mayDelete(s) && (
          <div className={allowance.data ? "" : "ml-auto"}>
            <ScriptMenu title={s.title} onDelete={() => del.ask(toTarget(s))} />
          </div>
        )}
      </div>
      {del.dialog}
      {leaving && (
        <Dialog title={hold?.title ?? "Leave this step?"} cancelLabel="Stay" actionLabel="Leave" danger onCancel={() => setLeaving(null)} onConfirm={() => { leaving(); setLeaving(null); }}>
          {hold?.body}
        </Dialog>
      )}
      <StepPicker steps={stepStates(step, s, song)} onPick={(to) => go(to)} />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 className="type-section">{label}</h2>
        {rail ? (
          <div className="flex items-start gap-2">
            {backButton}
            {nextButton}
          </div>
        ) : (
          <ActionBar phone>
            <div className="flex items-start gap-2 [&>button]:w-auto [&>span]:flex-1">
              {backButton}
              <span className="flex-1">{nextButton}</span>
            </div>
          </ActionBar>
        )}
      </div>
      {step === "song" && <SongStep script={s} brandId={brandId} onDirty={(d) => setHold(d ? { title: "Leave without saving?", body: "The lyrics you changed are not saved." } : null)} />}
      {step === "takes" && <TakesStep script={s} />}
      {step === "narration" && <NarrationStep script={s} />}
      {step === "script" && <ScriptStep script={s} brandName={brandName} onDirty={(d) => setHold(d ? { title: "Leave without saving?", body: "The words you changed on the Script step are not saved." } : null)} />}
      {step === "directions" && <DirectionsStep script={s} onAccepted={(n) => setHold(n > 0 ? { title: `Leave without adding ${n} direction${n === 1 ? "" : "s"}?`, body: "They stay accepted but are not added to the script. Leaving doesn't add them." } : null)} onEditWords={() => go("script")} />}
      {step === "variations" && <VariationsStep script={s} own={mine} />}
      {step === "cast" && <CastStep script={s} brandId={brandId} readOnly={s.published} />}
      {step === "breakdown" && <BreakdownStep script={s} brandId={brandId} readOnly={s.published} />}
      {step === "publish" && <PublishStep script={s} brandId={brandId} asking={asking} onAsking={setAsking} />}
    </main>
  );
}
