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
import { VariationsStep, variationsReason, writtenVariations } from "./VariationsStep";
import { ScriptStep } from "./ScriptStep";
import { ReadReelButton, useReelImport } from "./ReelImport";
import { PublishStep } from "./PublishStep";
import { WRITING_STEPS, around, hasWords, lockReason, stepFromParam, stepStates } from "./flow";
import { ScriptMenu, toTarget, useDeleteScript, useMayDelete } from "./DeleteScript";
import { useScript, usePatchScript } from "./useScript";

/** The writing flow for one script, in the same frame as a video: header, step picker, Back and Next. */
export function ScriptFlowPage() {
  const brandId = Number(useParams().brandId);
  const brandName = useBrands().data?.find((b) => b.id === brandId)?.name;
  const id = Number(useParams().scriptId);
  const [params, setParams] = useSearchParams();
  const rail = useRail();
  const { data: me } = useMe();
  const script = useScript(id);
  const patch = usePatchScript(id);
  const navigate = useNavigate();
  const mayDelete = useMayDelete();
  const del = useDeleteScript(() => navigate(`/b/${brandId}/scripts`));
  const reel = useReelImport(id);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [asking, setAsking] = useState(false); // the Publish confirmation, opened from the Next slot
  const [picked, setPicked] = useState(0); // variations chosen on that step, before any is written
  const [editing, setEditing] = useState(false); // a form is open on this step (the Script step: unsaved words): its own button is the amber one
  const [leaving, setLeaving] = useState<(() => void) | null>(null);
  useEffect(() => {
    if (!editing) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [editing]);
  const allowance = useQuery({
    enabled: me?.role !== undefined && me.role !== "owner",
    queryKey: ["allowance"],
    queryFn: async () => (await api.GET("/credits/me")).data ?? null,
  });

  if (script.isPending)
    return (
      <div className="mx-auto max-w-content space-y-4 p-4 sm:p-8" role="status" aria-label="Loading">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-12" />
        <Skeleton className="h-64" />
      </div>
    );
  const s = script.data;
  if (!s) return <p className="p-6">That script doesn't exist.</p>;
  const step = stepFromParam(params.get("step"));
  if (lockReason(step, s) !== null) return <Navigate to="?" replace />;
  const move = (to: string) => {
    setEditing(false);
    setPicked(0);
    setParams(to === "script" ? {} : { step: to });
  };
  // Unsaved words on the Script step: leaving asks first.
  const go = (to: string) => (step === "script" && editing ? setLeaving(() => () => move(to)) : move(to));
  const at = WRITING_STEPS.findIndex((x) => x.id === step);
  const { prev, next } = around(step);
  const nextReason = !next ? null : step === "script" && !hasWords(s) ? "Write or paste the script first" : step === "variations" ? variationsReason(s) : null;
  const label = WRITING_STEPS[at].label;
  const toPublish = s.versions.filter((v) => v.text.trim() !== "").length;
  const publishButton = step === "publish" && !s.published && (
    <Button disabled={toPublish === 0} reason={toPublish === 0 ? "Write the script first" : undefined} onClick={() => setAsking(true)}>
      Publish {toPublish} version{toPublish === 1 ? "" : "s"}
    </Button>
  );
  // A script from a reel isn't ready to move on until the reel is read: Read this reel is the one amber button until then.
  const unread = step === "script" && !!reel.data && reel.data.status !== "done";
  const reelReady = unread && !s.published && !rail && (reel.data?.status === "ready" || reel.data?.status === "failed") && reel.data?.failed_step !== "prepare";
  const nextButton = reelReady ? <ReadReelButton scriptId={id} createdById={s.created_by_id} /> : publishButton || (next && !editing && !unread && !(step === "variations" && picked > 0 && writtenVariations(s).length === 0) && (
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
          if (step === "script" && editing) {
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
            <span className="min-w-0 break-words">{s.title}</span>
            {!published && (
              <button type="button" aria-label="Rename" onClick={() => setRenaming(s.title)} className="grid size-control shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2">
                <Pencil size={20} strokeWidth={1.75} aria-hidden />
              </button>
            )}
          </h1>
        ) : (
          <form
            className="flex min-w-0 flex-1 flex-wrap items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (renaming.trim()) patch.mutate({ title: renaming.trim() }, { onSuccess: () => setRenaming(null) });
            }}
          >
            <div className="min-w-0 flex-1">
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
        <Dialog title="Leave without saving?" cancelLabel="Stay" actionLabel="Leave" danger onCancel={() => setLeaving(null)} onConfirm={() => { leaving(); setLeaving(null); }}>
          The words you changed on the Script step are not saved.
        </Dialog>
      )}
      <StepPicker steps={stepStates(step, s)} onPick={(to) => go(to)} />
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
      {step === "script" && <ScriptStep script={s} brandName={brandName} onDirty={setEditing} />}
      {step === "directions" && <DirectionsStep script={s} onEditing={setEditing} onEditWords={() => go("script")} />}
      {step === "variations" && <VariationsStep script={s} own={mine} onPicked={setPicked} />}
      {step === "cast" && <CastStep script={s} brandId={brandId} readOnly={s.published} />}
      {step === "breakdown" && <BreakdownStep script={s} brandId={brandId} readOnly={s.published} />}
      {step === "publish" && <PublishStep script={s} brandId={brandId} asking={asking} onAsking={setAsking} />}
    </main>
  );
}
