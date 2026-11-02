import { useEffect, useState } from "react";
import { ChevronLeft, Clapperboard } from "lucide-react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMe } from "../auth/useMe";
import { Button, Dialog, Skeleton, StepPicker } from "../components";
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
import { WRITING_STEPS, around, hasWords, isNarrated, lockReason, stepFromParam, stepStates, stepsFor } from "./flow";
import { NarrationStep } from "./NarrationStep";
import { SongStep } from "./SongStep";
import { TakesStep } from "./TakesStep";
import { useSongs } from "./useSongs";
import { ScriptMenu, toTarget, useDeleteScript, useMayDelete } from "./DeleteScript";
import { useScript } from "./useScript";
import { LookSetting } from "./Looks";
import { ProjectPicker, useFolders } from "../folders/Projects";
import { ScriptTop, SettingsRow, ShapeChip } from "./ScriptFrame";
import { FormatAdvice, FormatSetting } from "./Format";
import { HeldRequests } from "../approvals/HeldRequests";
import { ScriptOverview } from "./ScriptOverview";
import { VersionPanel } from "./VersionPanel";
import { MakeVideoPanel } from "./MakeVideoPanel";
import { finished } from "../freestyle/FromScript";

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
  const navigate = useNavigate();
  const mayDelete = useMayDelete();
  const del = useDeleteScript(() => navigate(`/b/${brandId}/scripts`));
  const reel = useReelImport(id);
  const folders = useFolders(script.data?.brand_id ?? brandId);
  const [asking, setAsking] = useState(false); // the Publish confirmation, opened from the Next slot
  // Something on this step would be lost by leaving (unsaved words, accepted directions not added): Next and every other way out ask once, and Next still always goes on.
  const [hold, setHold] = useState<{ title: string; body: string } | null>(null);
  const [waiting, setWaiting] = useState(0); // accepted directions not applied yet: Apply is the step's one primary press
  const [leaving, setLeaving] = useState<(() => void) | null>(null);
  useEffect(() => {
    if (!hold) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [hold]);

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
  // A published script opens on its Overview; a draft on its first step, as before.
  const overview = s.published && (params.get("step") ?? "overview") === "overview";
  const step = stepFromParam(s, params.get("step"));
  if (!overview && lockReason(step, s, song) !== null) return <Navigate to="?" replace />;
  const first = s.published ? "overview" : stepsFor(s)[0].id;
  const move = (to: string) => {
    setHold(null);
    setParams(to === first ? {} : { step: to });
  };
  const steps = stepStates(step, s, song).map((x) => (overview && x.state === "current" ? { ...x, state: "open" as const } : x));
  const making = /^(\d+)$/.exec(params.get("make") ?? ""); // ?make=1: Version B's panel, opened from the Overview
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
  // While accepted directions wait, "Apply N accepted" is the one indigo press, so Next turns secondary (C_Directions).
  const nextButton = reelReady ? <ReadReelButton scriptId={id} /> : publishButton || (next && !unread && (
    <Button variant={step === "directions" && waiting > 0 ? "secondary" : "primary"} disabled={nextReason !== null} reason={nextReason} onClick={() => go(next.id)}>
      Next: {next.label}
    </Button>
  ));
  const backButton = prev && (
    <Button variant="ghost" icon={ChevronLeft} aria-label={rail ? undefined : "Back"} onClick={() => go(prev.id)}>
      {rail ? "Back" : ""}
    </Button>
  );
  const published = s.published;
  const mine = s.created_by_id === me?.id;

  // Where a way out goes: every one asks first while something on this step would be lost.
  const leave = (to: string) => (e: React.MouseEvent) => {
    if (!hold) return;
    e.preventDefault();
    setLeaving(() => () => navigate(to));
  };
  const project = folders.data?.find((f) => f.id === s.folder_id);
  const crumbs = [
    <Link key="s" to={`/b/${brandId}/scripts`} onClick={leave(`/b/${brandId}/scripts`)} className="hover:text-text hover:underline">
      Scripts
    </Link>,
    ...(project ? [<span key="p">{project.name}</span>] : []),
    <span key="t" className="font-medium text-text">{s.title}</span>,
    ...(overview ? [] : [<span key="x">Steps</span>]),
  ];
  // v5 settings per step (C_ScriptWrite: Type, Style, Project and Shape; C_Directions: Type, Style, Project).
  const settings = (
    <>
      <FormatSetting script={s} />
      <LookSetting value={s.look} scriptId={s.id} queryKey={["script-lib", s.id]} readOnly={published} />
      {(mine || me?.role === "owner") && <ProjectPicker pick brandId={s.brand_id} kind="script" id={s.id} folderId={s.folder_id} />}
      {step === "script" && <ShapeChip />}
    </>
  );
  // A story's v5 step bar ends at Cast: Publish is "Publish to library", still the step after Cast (Next: Publish).
  const barSteps = stepsFor(s) === WRITING_STEPS && step !== "publish" ? steps.filter((x) => x.id !== "publish") : steps;
  const v5 = step === "script" || step === "directions"; // the steps built to v5 so far: their own headings, no step title row

  return (
    <main className={rail || overview ? "" : "pb-28"}>
      <ScriptTop crumbs={crumbs}>
        {!overview && published && (
          <Button variant="ghost" dense className="text-muted" onClick={() => go("overview")}>
            Back to overview
          </Button>
        )}
        {/* Any finished version becomes a video from here; publishing isn't needed (E_ScriptMakeVideo, #1194). */}
        {s.kind === "story" && s.versions.some(finished) && (
          <Button variant="secondary" dense icon={Clapperboard} onClick={() => setParams({ video: "1" })}>
            Make a video
          </Button>
        )}
        {mayDelete(s) && <ScriptMenu title={s.title} onDelete={() => del.ask(toTarget(s))} />}
        {!overview && rail && nextButton}
      </ScriptTop>
      <SettingsRow steps={<StepPicker flat steps={s.published ? [{ id: "overview", label: "Overview", state: overview ? "current" : "open" }, ...barSteps] : barSteps} onPick={(to) => go(to)} />}>
        {settings}
      </SettingsRow>
      {params.get("video") && <MakeVideoPanel scriptId={s.id} onClose={() => setParams({})} />}
      <div className="mx-auto max-w-content space-y-4 p-4 sm:p-8">
      {del.dialog}
      <HeldRequests where={{ scriptId: s.id }} />
      {leaving && (
        <Dialog title={hold?.title ?? "Leave this step?"} cancelLabel="Stay" actionLabel="Leave" danger onCancel={() => setLeaving(null)} onConfirm={() => { leaving(); setLeaving(null); }}>
          {hold?.body}
        </Dialog>
      )}
      {overview && <ScriptOverview script={s} brandId={brandId} onStep={go} onMake={(slot) => setParams({ make: String(slot) })} />}
      {making && <VersionPanel scriptId={s.id} slot={Number(making[1])} brandId={brandId} onClose={() => setParams({})} />}
      {!overview && (
        <>
          {/* Steps not yet rebuilt to v5 keep their title row; Next sits in the top bar on a computer, in the action bar on a phone. */}
          {!v5 && <h2 className="flex min-h-control items-center type-section">{label}</h2>}
          {!rail && (
            <ActionBar phone>
              <div className="flex items-start gap-2 [&>button]:w-auto [&>span]:flex-1">
                {backButton}
                <span className="flex-1">{nextButton}</span>
              </div>
            </ActionBar>
          )}
          {step === "song" && <SongStep script={s} brandId={brandId} onDirty={(d) => setHold(d ? { title: "Leave without saving?", body: "The lyrics you changed are not saved." } : null)} />}
          {step === "takes" && <TakesStep script={s} />}
          {step === "narration" && <NarrationStep script={s} />}
          {step === "script" && <FormatAdvice script={s} />}
          {step === "script" && <ScriptStep script={s} brandName={brandName} onDirty={(d) => setHold(d ? { title: "Leave without saving?", body: "The words you changed on the Script step are not saved." } : null)} />}
          {step === "directions" && <DirectionsStep script={s} onAccepted={(n) => { setWaiting(n); setHold(n > 0 ? { title: `Leave without applying ${n} accepted?`, body: "They stay accepted but are not applied to the script. Leaving doesn't apply them." } : null); }} />}
          {step === "variations" && <VariationsStep script={s} own={mine} />}
          {step === "cast" && <CastStep script={s} brandId={brandId} readOnly={s.published} />}
          {step === "breakdown" && <BreakdownStep script={s} brandId={brandId} readOnly={s.published} />}
          {step === "publish" && <PublishStep script={s} brandId={brandId} asking={asking} onAsking={setAsking} />}
        </>
      )}
      </div>
    </main>
  );
}
