import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText, must } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl, uploadFile } from "../api/upload";
import { Elapsed, useJobs } from "../clip/History";
import { useMe } from "../auth/useMe";
import { Sheet } from "../projects/Sheet";
import { useMedia } from "../useMedia";
import { useToast } from "../toast";
import { btnPrimary, btnSecondary, card, errorText as errorClass, input, linkText } from "../ui";

type Item = components["schemas"]["ItemOut"];
const MODEL = "nano-banana-pro";
const RESOLUTION = "2K";
/** 1.5 stays 1.5, 3 stays 3. */
export const credits = (n: number) => `${+n.toFixed(1)} credits`;

/** Photo → house-style sheet. Only an approved sheet is used in videos. */
export function SheetPanel(props: { item: Item; kind: "character" | "place"; ensureSaved: () => Promise<unknown> }) {
  const { item, kind } = props;
  const toast = useToast();
  const phone = useMedia("(max-width: 639px)");
  const queryClient = useQueryClient();
  const path = { kind, item_id: item.id };
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["library", kind] }), queryClient.invalidateQueries({ queryKey: ["assets"] })]);
  const [redoing, setRedoing] = useState<string | null>(null);
  const models = useQuery({ queryKey: ["models"], queryFn: async () => (await api.GET("/models")).data ?? [] });
  const price = models.data?.find((m) => m.id === MODEL)?.credits_per_unit?.[RESOLUTION];
  const allowance = useQuery({ queryKey: ["allowance"], queryFn: async () => (await api.GET("/credits/me")).data ?? null });
  const jobs = useJobs();
  const last = (jobs.data ?? []).filter((j) => j.step === "sheet" && j.library_item_id === item.id).sort((a, b) => b.id - a.id)[0];
  const status = item.sheet_status;
  const drawing = status === "drawing";
  const held = status === "waiting_for_owner"; // over the weekly allowance: Reed has to say yes
  const failed = last?.status === "failed" && !drawing;
  const photo = item.source_photo_file_id;
  const cost = price === undefined ? "" : ` · ${credits(price)}`;
  // Past an editor's weekly allowance the server declines a new sheet, so don't offer one.
  const { data: me } = useMe();
  const a = allowance.data;
  const over = me?.role === "editor" && price !== undefined && !!a && a.quick_clip_credits_used + price > a.quick_clip_credits_allowed;
  const declined = over && a ? `You've used this week's ${Math.round(a.quick_clip_credits_allowed)} credits. It resets Monday.` : null;

  const upload = useMutation({
    mutationFn: async (file: File) => {
      await props.ensureSaved();
      const f = await uploadFile(file);
      await must(api.PATCH("/library/{kind}/{item_id}", { params: { path }, body: { source_photo_file_id: f.id } }));
    },
    onSuccess: refresh,
  });
  const make = useMutation({
    mutationFn: async (change: string) => {
      await props.ensureSaved();
      const { data, error } = await api.POST("/library/{kind}/{item_id}/sheet", { params: { path }, body: { model_id: MODEL, change } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => {
      setRedoing(null);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      refresh();
    },
  });
  const approve = useMutation({
    mutationFn: () => must(api.POST("/library/{kind}/{item_id}/sheet/approve", { params: { path } })),
    onSuccess: () => {
      refresh();
      toast(`${item.name}'s sheet approved.`, async () => {
        await api.DELETE("/library/{kind}/{item_id}/sheet/approve", { params: { path } });
        refresh();
      });
    },
  });
  const unapprove = useMutation({
    mutationFn: () => must(api.DELETE("/library/{kind}/{item_id}/sheet/approve", { params: { path } })),
    onSuccess: refresh,
  });
  const err = upload.error ?? make.error ?? approve.error ?? unapprove.error;
  const btn = "min-h-11 w-full sm:min-h-9 sm:w-auto";

  const redoForm = (
    <div className="space-y-2">
      <label className="block text-sm">
        What should change? (optional)
        <textarea className={input} rows={3} maxLength={500} value={redoing ?? ""} onChange={(e) => setRedoing(e.target.value)} />
      </label>
      <div className="flex flex-wrap gap-2">
        <button className={`${btnPrimary} ${btn}`} disabled={make.isPending || !!declined} onClick={() => make.mutate((redoing ?? "").trim())}>
          Redo
          {cost}
        </button>
        <button className={`${btnSecondary} ${btn}`} onClick={() => setRedoing(null)}>
          Cancel
        </button>
      </div>
    </div>
  );

  return (
    <section className={`${card} space-y-3`} aria-label="House-style sheet">
      <h2 className="text-[length:var(--text-md)] font-semibold">House-style sheet</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1 text-sm">
          {photo ? <img src={fileUrl(photo)} alt={`Source photo of ${item.name}`} className="w-full rounded-md border border-border bg-surface-2 object-contain" /> : <div className="grid h-32 place-items-center rounded-md bg-surface-2 text-muted">No photo yet</div>}
          <p className="text-muted">Source photo, not used in videos</p>
          <label className={`inline-flex min-h-11 cursor-pointer items-center sm:min-h-0 ${linkText}`}>
            {photo ? "Replace photo" : "Upload a photo"}
            <input type="file" accept="image/*" className="sr-only" aria-label="Source photo file" onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])} />
          </label>
          {upload.isPending && <span className="text-muted"> Uploading…</span>}
        </div>
        <div className="space-y-2 text-sm">
          {held ? (
            <div className="grid min-h-40 place-items-center rounded-md bg-warning-soft font-medium text-warning" aria-label="Waiting for Reed">
              Waiting for Reed to approve
            </div>
          ) : drawing ? (
            <div className="grid min-h-40 place-items-center rounded-md bg-surface-2 text-muted" aria-label="Drawing the sheet">
              Drawing… {last && <Elapsed since={last.created_at} />}
            </div>
          ) : item.sheet_file_id ? (
            <img
              src={fileUrl(item.sheet_file_id)}
              alt={`House-style sheet of ${item.name}`}
              className={`w-full rounded-md bg-surface-2 object-contain ${status === "approved" ? "border-2 border-accent" : "border border-border"}`}
            />
          ) : null}
          {status === "approved" && <p className="font-medium text-success">✓ Approved sheet</p>}
          {status === "needs_approval" && <p className="text-warning">Needs a sheet approval. Videos only use an approved sheet.</p>}
          {status === "none" && !failed && !held && <p className="text-warning">Needs a sheet</p>}
          {failed && <p className="text-danger">Didn't finish · credits returned</p>}
          {drawing && <p className="text-muted">A sheet is being made.</p>}
          {held && <p className="text-warning">The sheet starts when Reed says yes. You can't ask for another meanwhile.</p>}
          {declined && !drawing && !held && <p className="text-warning">{declined}</p>}
        </div>
      </div>
      {!drawing && !held && status === "none" && (photo || kind === "place") && (
        <div className="space-y-2">
          <p>{photo ? "Turn this photo into a house-style sheet?" : "Make a sheet from the notes?"}</p>
          <button className={`${btnPrimary} ${btn}`} disabled={make.isPending || !!declined} onClick={() => make.mutate("")}>
            {failed ? "Try again" : "Make house-style sheet"}
            {cost}
          </button>
        </div>
      )}
      {!drawing && !held && status === "none" && !photo && kind === "character" && <p className="text-muted">Upload a photo to make a sheet.</p>}
      {!drawing && !held && (status === "needs_approval" || status === "approved") && (
        <div className="flex flex-wrap gap-2">
          {status === "needs_approval" && (
            <button className={`${btnPrimary} ${btn}`} disabled={approve.isPending} onClick={() => approve.mutate()}>
              Approve
            </button>
          )}
          {status === "approved" && (
            <button className={`${btnSecondary} ${btn}`} disabled={unapprove.isPending} onClick={() => unapprove.mutate()}>
              Undo approval
            </button>
          )}
          {redoing === null && (
            <button className={`${btnSecondary} ${btn}`} disabled={!!declined} onClick={() => setRedoing("")}>
              Redo
              {cost}
            </button>
          )}
        </div>
      )}
      {redoing !== null && !drawing && !held && (phone ? <Sheet title="Redo the sheet" closeLabel="Cancel" onClose={() => setRedoing(null)}>{redoForm}</Sheet> : redoForm)}
      {err && <p role="alert" className={errorClass}>{err.message}</p>}
    </section>
  );
}
