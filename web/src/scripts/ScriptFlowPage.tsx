import { useEffect, useState } from "react";
import { ChevronLeft, Clapperboard, ListOrdered, Plus } from "lucide-react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMe } from "../auth/useMe";
import { Button, Dialog, Skeleton, StepPicker } from "../components";
import { useBrands } from "../shell/useBrands";
import { ActionBar } from "../shell/ActionBar";
import { useRail } from "../useMedia";
import { BreakdownStep, VersionPick, breakdownSlot } from "./BreakdownStep";
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
import { useScript, type Script } from "./useScript";
import { LookSetting } from "./Looks";
import { ProjectPicker, useFolders } from "../folders/Projects";
import { ScriptTop, SettingsRow, ShapeChip } from "./ScriptFrame";
import { FormatAdvice, FormatSetting } from "./Format";
import { HeldRequests } from "../approvals/HeldRequests";
import { ScriptOverview } from "./ScriptOverview";
import { MakeVideoPanel } from "./MakeVideoPanel";
import { finished } from "../freestyle/FromScript";
import { useEstimate } from "../freestyle/useFreestyle";

const nextToMake = (s: Script) => {
  const ready = s.versions.filter(finished);
  return ready.find((v) => !v.project_id) ?? ready[0];
};

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
  // The Overview's Make a video opens on the next version to make, else the first finished one, and says its price.
  const toMake = script.data && nextToMake(script.data);
  const estimate = useEstimate(script.data && toMake ? { script_id: script.data.id, slot: toMake.slot, shape: "9:16" } : null);
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
  // Every script opens on its Overview (C_ScriptOverview); one with no words yet opens on its first step.
  const overview = (params.get("step") ?? "overview") === "overview" && (hasWords(s) || s.published);
  const step = stepFromParam(s, params.get("step"));
  if (!overview && lockReason(step, s, song) !== null) return <Navigate to="?" replace />;
  const move = (to: string) => {
    setHold(null);
    setParams(to === "overview" ? {} : { step: to });
  };
  const steps = stepStates(step, s, song).map((x) => (overview && x.state === "current" ? { ...x, state: "open" as const } : x));
  const videoSlot = /^(\d+)$/.exec(params.get("video") ?? ""); // ?video=2: the Make a video panel, on version C
  const go = (to: string) => (hold ? setLeaving(() => () => move(to)) : move(to));
  const { prev, next } = around(s, step);
  const nextReason = !next ? null : step === "script" && !hasWords(s) ? "Write or paste the script first" : step === "variations" ? variationsReason(s) : lockReason(next.id, s, song);
  const label = stepsFor(s).find((x) => x.id === step)!.label;
  // A script from a reel isn't ready to move on until the reel is read: Read this reel is the one amber button until then.
  const unread = step === "script" && !!reel.data && reel.data.status !== "done";
  const reelReady = unread && !s.published && !rail && (reel.data?.status === "ready" || reel.data?.status === "failed") && reel.data?.failed_step !== "prepare";
  // While accepted directions wait, "Apply N accepted" is the one indigo press, so Next turns secondary (C_Directions).
  // v5 G_Publish: Publish is its own page, with its presses at the end of it, so the top has no Next there.
  const nextButton = reelReady ? <ReadReelButton scriptId={id} /> : step !== "publish" && next && !unread && (
    <Button variant={(step === "directions" && waiting > 0) || step === "breakdown" ? "secondary" : "primary"} disabled={nextReason !== null} reason={nextReason} onClick={() => go(next.id)}>
      Next: {next.label}
    </Button>
  );
  // In the 52 px top bar a held Next says why on its left, so the bar keeps its height.
  const topNext = !reelReady && step !== "publish" && next && !unread && nextReason ? (
    <span className="flex items-center gap-3">
      <span id="next-why" className="text-xs text-muted">
        {nextReason}
      </span>
      <Button disabled aria-describedby="next-why">
        Next: {next.label}
      </Button>
    </span>
  ) : (
    nextButton
  );
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
    <Link key="s" to={`/b/${brandId}/scripts`} onClick={leave(`/b/${brandId}/scripts`)} className="inline-flex min-h-control min-w-11 items-center hover:text-text hover:underline lg:min-h-0 lg:min-w-0">
      Scripts
    </Link>,
    ...(project ? [<span key="p">{project.name}</span>] : []),
    <span key="t" className="font-medium text-text">{s.title}</span>,
    ...(overview || step === "publish" ? [] : [<span key="x">Steps</span>]),
  ];
  // v5 settings per step (C_ScriptWrite: Type, Style, Project and Shape; C_Directions: Type, Style, Project).
  const slot = breakdownSlot(s, params.get("v"));
  const settings = step === "breakdown" ? (
    // C_Breakdown: the version and the shape (read only: each video picks its own).
    <>
      <VersionPick script={s} value={slot} onChange={(v) => setParams({ step: "breakdown", ...(v ? { v: String(v) } : {}) })} />
      <ShapeChip value="9:16" />
    </>
  ) : (
    <>
      <FormatSetting script={s} />
      <LookSetting value={s.look} scriptId={s.id} queryKey={["script-lib", s.id]} readOnly={published} />
      {(mine || me?.role === "owner") && <ProjectPicker pick brandId={s.brand_id} kind="script" id={s.id} folderId={s.folder_id} />}
      {step === "script" && <ShapeChip />}
    </>
  );
  // A story's v5 step bar ends at Cast: Publish is "Publish to library", still the step after Cast (Next: Publish).
  const barSteps = stepsFor(s) === WRITING_STEPS && step !== "publish" ? steps.filter((x) => x.id !== "publish") : steps;
  const v5 = ["script", "directions", "variations", "breakdown", "cast", "publish"].includes(step); // the steps built to v5 so far: their own headings, no step title row
  // v5 settings rows: Variations shows only the steps (G_Variations); Publish has neither (G_Publish).
  const row = overview || (step !== "variations" && step !== "cast" && step !== "publish"); // Cast shows only the steps (C_CastLock)

  return (
    <main className={rail || overview ? "" : "pb-28"}>
      <ScriptTop crumbs={crumbs}>
        {!overview && (hasWords(s) || published) && (
          <Button variant="ghost" dense className="text-muted" onClick={() => go("overview")}>
            Back to overview
          </Button>
        )}
        {overview && !published && (
          <Button variant="secondary" dense disabled={lockReason("publish", s, song) !== null} reason={lockReason("publish", s, song)} onClick={() => go("publish")}>
            Publish to library
          </Button>
        )}
        {/* Any finished version becomes a video from here; publishing isn't needed (E_ScriptMakeVideo, #1194). */}
        {s.kind === "story" && toMake && (
          <Button variant={overview ? "primary" : "secondary"} dense icon={overview ? Plus : Clapperboard} price={overview ? (estimate.data ?? (estimate.isError ? undefined : null)) : undefined} charge="estimate" onClick={() => setParams({ ...(overview ? {} : { step }), video: String(toMake.slot) })}>
            Make a video
          </Button>
        )}
        {mayDelete(s) && <ScriptMenu title={s.title} onDelete={() => del.ask(toTarget(s))} />}
        {!overview && rail && topNext}
      </ScriptTop>
      {overview ? (
        // C_ScriptOverview's band: the Overview tab, and the writing steps behind one quiet press.
        <div className="flex min-h-13 flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2 sm:px-6">
          <span aria-current="page" className="inline-flex min-h-control items-center rounded-md bg-surface-2 px-3 text-sm font-medium lg:min-h-control-dense lg:px-2.5">
            Overview
          </span>
          <Button variant="ghost" dense icon={ListOrdered} className="justify-start text-left" onClick={() => go(stepsFor(s)[0].id)}>
            Open the steps: {barSteps.map((x) => x.label).join(" · ")}
          </Button>
        </div>
      ) : (
        step !== "publish" && (
          <SettingsRow steps={<StepPicker flat steps={barSteps} onPick={(to) => go(to)} />}>
            {row && settings}
          </SettingsRow>
        )
      )}
      {videoSlot && <MakeVideoPanel scriptId={s.id} slot={Number(videoSlot[1])} onClose={() => setParams(overview ? {} : { step })} />}
      <div className="mx-auto max-w-content space-y-4 p-4 sm:p-8">
      {del.dialog}
      <HeldRequests where={{ scriptId: s.id }} />
      {leaving && (
        <Dialog title={hold?.title ?? "Leave this step?"} cancelLabel="Stay" actionLabel="Leave" danger onCancel={() => setLeaving(null)} onConfirm={() => { leaving(); setLeaving(null); }}>
          {hold?.body}
        </Dialog>
      )}
      {overview && <ScriptOverview script={s} brandId={brandId} onMake={(slot) => setParams({ video: String(slot) })} />}
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
          {step === "breakdown" && <BreakdownStep script={s} brandId={brandId} readOnly={s.published} slot={slot} />}
          {step === "publish" && <PublishStep script={s} brandId={brandId} asking={asking} onAsking={setAsking} onNotYet={() => (prev ? go(prev.id) : go("overview"))} />}
        </>
      )}
      </div>
    </main>
  );
}
