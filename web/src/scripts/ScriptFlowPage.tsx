import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, Lock, Pencil } from "lucide-react";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useMe } from "../auth/useMe";
import { Badge, Button, Card, Field, Skeleton, StepPicker, TextArea } from "../components";
import { useReferences } from "../projects/BriefPickers";
import { useBrands } from "../shell/useBrands";
import { ScriptText } from "../projects/ScriptTab";
import { ActionBar } from "../shell/ActionBar";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useRail } from "../useMedia";
import { CastStep } from "./CastStep";
import { DescriptionForm } from "./DescriptionForm";
import { VariationsStep, variationsReason, writtenVariations } from "./VariationsStep";
import { ReelBlock, useReelImport } from "./ReelImport";
import { PublishStep } from "./PublishStep";
import { WRITING_STEPS, around, hasWords, lockReason, stepFromParam, stepStates } from "./flow";
import { useScript, usePatchScript, useWriteWords } from "./useScript";

/** The writing flow for one script, in the same frame as a video: header, step picker, Back and Next. */
export function ScriptFlowPage() {
  const brandId = Number(useParams().brandId);
  const brandName = useBrands().data?.find((b) => b.id === brandId)?.name;
  const id = Number(useParams().scriptId);
  const [params, setParams] = useSearchParams();
  const rail = useRail();
  const toast = useToast();
  const { data: me } = useMe();
  const script = useScript(id);
  const patch = usePatchScript(id);
  const reel = useReelImport(id);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [asking, setAsking] = useState(false); // the Publish confirmation, opened from the Next slot
  const [picked, setPicked] = useState(0); // variations chosen on that step, before any is written
  const [editing, setEditing] = useState(false); // a form is open on this step: its own button is the amber one
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
  if (lockReason(step, s) !== null) return <Navigate to="?step=description" replace />;
  const go = (to: string) => {
    setEditing(false);
    setPicked(0);
    setParams(to === "description" ? {} : { step: to });
  };
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
  const unread = step === "description" && !!reel.data && reel.data.status !== "done";
  const nextButton = publishButton || (next && !editing && !unread && !(step === "variations" && picked > 0 && writtenVariations(s).length === 0) && (
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
  const draftNote = mine ? (me?.role === "owner" ? "Draft · only you can see it" : "Draft · only you and Reed can see it") : `Draft · ${s.created_by_name || "an editor"}'s, not published`;

  return (
    <main className={`mx-auto max-w-content space-y-4 p-4 sm:p-8 ${rail ? "" : "pb-28"}`}>
      <Link to={`/b/${brandId}/scripts`} className="inline-flex min-h-control items-center gap-1 text-accent-text hover:underline lg:min-h-control-dense">
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
      </div>
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
      {step === "description" && <DescriptionStep script={s} brandName={brandName} onEditing={setEditing} onDone={() => toast("Description saved.")} />}
      {step === "script" && <ScriptStep scriptId={id} script={s} onEditing={setEditing} />}
      {step === "variations" && <VariationsStep script={s} own={mine} onPicked={setPicked} />}
      {step === "cast" && <CastStep scriptId={id} brandId={brandId} readOnly={s.published} />}
      {step === "publish" && <PublishStep script={s} brandId={brandId} asking={asking} onAsking={setAsking} />}
    </main>
  );
}

function DescriptionStep({ script: s, brandName, onEditing, onDone }: { script: NonNullable<ReturnType<typeof useScript>["data"]>; brandName?: string; onEditing: (v: boolean) => void; onDone: () => void }) {
  const patch = usePatchScript(s.id);
  const [editing, setEditing] = useState(false);
  const refs = useReferences();
  const open = (v: boolean) => {
    setEditing(v);
    onEditing(v);
  };
  if (editing && !s.published)
    return (
      <DescriptionForm
        initial={{ title: s.title, description: s.description, notes: s.notes, reference_id: s.reference_id, reference_replace: s.reference_replace }}
        brandName={brandName}
        submitLabel="Save description"
        busy={patch.isPending}
        error={patch.isError ? patch.error.message : null}
        onCancel={() => open(false)}
        onSubmit={(d) =>
          patch.mutate(d, {
            onSuccess: () => {
              open(false);
              onDone();
            },
          })
        }
      />
    );
  const row = (name: string, value: string) => (
    <div>
      <dt className="text-sm font-medium text-muted">{name}</dt>
      <dd className="whitespace-pre-wrap">{value || "—"}</dd>
    </div>
  );
  return (
    <div className="space-y-4">
    <ReelBlock scriptId={s.id} published={s.published} createdById={s.created_by_id} />
    <Card className="max-w-[680px] space-y-4">
      <dl className="space-y-4">
        {row("Title", s.title)}
        {row("What it's for", s.description)}
        {s.reference_id && row("Reference reel", `${refs.data?.find((r) => r.id === s.reference_id)?.name ?? s.reference_id}${s.reference_replace ? ` — ${s.reference_replace}` : ""}`)}
        {row("Notes", s.notes)}
      </dl>
      {!s.published && (
        <Button variant="secondary" icon={Pencil} onClick={() => open(true)}>
          Edit description
        </Button>
      )}
    </Card>
    </div>
  );
}

/** The original's words. Pasting, uploading and Claude's drafts come as the library API grows; for now you can write or paste them. */
function ScriptStep({ scriptId, script: s, onEditing }: { scriptId: number; script: NonNullable<ReturnType<typeof useScript>["data"]>; onEditing: (v: boolean) => void }) {
  const write = useWriteWords(scriptId);
  const text = s.versions.find((v) => v.slot === 0)?.text ?? "";
  const [editing, setEditingText] = useState<string | null>(null);
  const setEditing = (v: string | null) => {
    setEditingText(v);
    onEditing(v !== null);
  };
  const toast = useToast();
  const save = (t: string) =>
    write.mutate(t, {
      onSuccess: () => {
        setEditing(null);
        toast("Saved.");
      },
    });
  if (editing !== null || (!text.trim() && !s.published))
    return (
      <Card className="max-w-[680px] space-y-3">
        <TextArea label="Your script" rows={14} maxLength={50000} placeholder="Paste or write the script here" value={editing ?? ""} onChange={(e) => setEditing(e.target.value)} />
        {write.isError && <p role="alert" className={errorClass}>{write.error.message}</p>}
        <div className="flex flex-wrap gap-2">
          <Button busy={write.isPending} disabled={!(editing ?? "").trim()} onClick={() => save(editing ?? "")}>
            Save script
          </Button>
          {text.trim() && (
            <Button variant="ghost" onClick={() => setEditing(null)}>
              Cancel
            </Button>
          )}
        </div>
      </Card>
    );
  return (
    <div className="space-y-3">
      {!s.published && (
        <div>
          <Button variant="secondary" icon={Pencil} onClick={() => setEditing(text)}>
            Edit
          </Button>
        </div>
      )}
      <ScriptText text={text} />
    </div>
  );
}
