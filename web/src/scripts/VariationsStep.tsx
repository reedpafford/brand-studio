import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Lock, Pencil, RotateCcw } from "lucide-react";
import { api, errorText } from "../api/client";
import { useJobs } from "../clip/History";
import { Badge, Banner, Button, Card, Skeleton, Tabs, TextArea } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useRail } from "../useMedia";
import { useAllowanceStop, type Script } from "./useScript";

const LETTER = ["A", "B", "C"];
const NAME = ["Original", "Variation", "Variation"];
const GOING = ["queued", "running", "needs_owner_approval"];

type Version = Script["versions"][number];

/** Which lines of a version are not in the original, so they can be marked the same way as Directions. */
export function changedLines(original: string, text: string): boolean[] {
  const had = new Set(original.split("\n").map((l) => l.trim()));
  return text.split("\n").map((l) => l.trim() !== "" && !had.has(l.trim()));
}

/** The variations written so far (slots 1 and 2 with words). */
export const writtenVariations = (s: Script) => s.versions.filter((v) => v.slot > 0 && v.text.trim() !== "");

/** Why Next is held on this step, or null: every variation that was written has to be approved first. */
export function variationsReason(s: Script): string | null {
  const open = writtenVariations(s).find((v) => v.status === "draft");
  return open ? `Approve variation ${LETTER[open.slot]} first.` : null;
}

function useVariations(s: Script) {
  const queryClient = useQueryClient();
  const toast = useToast();
  // The running job is remembered for this script, so leaving the step and coming back doesn't offer to pay twice.
  const key = `variations-job-${s.id}`;
  const [run, setRun] = useState<{ id: number; slots: number[] } | null>(() => {
    try {
      return JSON.parse(sessionStorage.getItem(key) ?? "null");
    } catch {
      return null;
    }
  });
  const remember = (r: { id: number; slots: number[] } | null) => {
    setRun(r);
    try {
      if (r) sessionStorage.setItem(key, JSON.stringify(r));
      else sessionStorage.removeItem(key);
    } catch {
      /* private window: it just won't be remembered */
    }
  };
  const jobId = run?.id ?? null;
  const jobs = useJobs();
  const job = jobs.data?.find((j) => j.id === jobId);
  const writing = jobId !== null && (!job || GOING.includes(job.status));
  const failed = !!job && !GOING.includes(job.status) && job.status !== "succeeded";
  const done = !!job && job.status === "succeeded";
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["script-lib", s.id] }), queryClient.invalidateQueries({ queryKey: ["scripts"] })]);
  useEffect(() => {
    if (done) {
      try {
        sessionStorage.removeItem(key);
      } catch {
        /* nothing remembered */
      }
      void refresh().then(() => toast("Variations ready. Read them side by side."));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [done, jobId]);
  const write = useMutation({
    mutationFn: async (a: { slots: (1 | 2)[]; note: string }) => {
      // The server writes variations from an approved original.
      const original = s.versions.find((v) => v.slot === 0);
      if (original && original.status !== "approved") {
        const approved = await api.POST("/scripts/{script_id}/drafts/{slot}/approve", { params: { path: { script_id: s.id, slot: 0 } } });
        if (!approved.response.ok) throw new Error(errorText(approved.error));
      }
      const { data, error } = await api.POST("/scripts/{script_id}/variations", { params: { path: { script_id: s.id } }, body: a });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (data, a) => {
      remember({ id: data.id, slots: a.slots });
      await queryClient.invalidateQueries({ queryKey: ["jobs"] }); // the job list polls while anything is going
    },
  });
  const edit = useMutation({
    mutationFn: async (a: { slot: number; text: string }) => {
      const { data, error } = await api.PUT("/scripts/{script_id}/drafts/{slot}", { params: { path: { script_id: s.id, slot: a.slot } }, body: { text: a.text } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (data) => {
      queryClient.setQueryData(["script-lib", s.id], data);
      await refresh();
    },
  });
  const approve = useMutation({
    mutationFn: async (slot: number) => {
      const { data, error } = await api.POST("/scripts/{script_id}/drafts/{slot}/approve", { params: { path: { script_id: s.id, slot } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (data) => {
      queryClient.setQueryData(["script-lib", s.id], data);
      await refresh();
    },
  });
  return { write, edit, approve, writing, failed, slots: run?.slots ?? [], retry: () => remember(null) };
}

/** Step 4: choose how many variations, write them at one price, then read them next to the original and approve each. */
export function VariationsStep({ script: s, own, onPicked }: { script: Script; own: boolean; onPicked: (n: number) => void }) {
  const rail = useRail();
  const act = useVariations(s);
  const written = writtenVariations(s);
  const original = s.versions.find((v) => v.slot === 0)?.text ?? "";
  const price = useQuery({ queryKey: ["variations-estimate", s.id], queryFn: async () => (await api.GET("/scripts/{script_id}/variations/estimate", { params: { path: { script_id: s.id } } })).data?.credits });
  const [count, setCountState] = useState<0 | 1 | 2>(0);
  const setCount = (n: 0 | 1 | 2) => {
    setCountState(n);
    onPicked(n); // once Write is the amber button, Next steps aside
  };
  const stop = useAllowanceStop(s, price.data);
  const [note, setNote] = useState("");
  const [shown, setShown] = useState(1);
  const [changesOnly, setChangesOnly] = useState(false);
  const error = act.write.error ?? act.edit.error ?? act.approve.error;

  if (act.writing && written.length === 0)
    return (
      <div className="space-y-3" role="status" aria-label="Writing variations">
        <p className="text-muted">Writing {act.slots.length === 1 ? "1 variation" : "variations"}… This takes a little while.</p>
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );

  if (written.length === 0)
    return (
      <div className="max-w-[680px] space-y-4">
        {act.failed && (
          <Banner title="The variations didn't finish. Nothing was charged." action={<Button variant="secondary" onClick={act.retry}>Try again</Button>}>
            Check your connection and try again.
          </Banner>
        )}
        {own && <p className="text-sm text-muted">Optional. Most scripts go out as one version.</p>}
        <fieldset className="space-y-2">
          <legend className="font-medium">How many variations?</legend>
          <div role="radiogroup" aria-label="How many variations?" className="inline-flex rounded-md border border-border">
            {([0, 1, 2] as const).map((n) => (
              <button key={n} type="button" role="radio" aria-checked={count === n} onClick={() => setCount(n)} className={`min-h-control min-w-16 px-4 font-medium lg:min-h-control-dense ${count === n ? "bg-accent-soft text-text" : "text-muted hover:bg-surface-2"}`}>
                {n === 0 ? "None" : n}
              </button>
            ))}
          </div>
        </fieldset>
        {count > 0 && (
          <>
            <TextArea label="Direction (optional)" rows={2} maxLength={2000} placeholder="e.g. swap the altar for a car showroom; keep the payoff about money" value={note} onChange={(e) => setNote(e.target.value)} />
            {error && <p role="alert" className={errorClass}>{error.message}</p>}
            <p className="text-sm text-muted">Writing variations makes A's words final.</p>
            <Button busy={act.write.isPending} price={price.data} disabled={stop !== null} reason={stop} onClick={() => act.write.mutate({ slots: count === 1 ? [1] : [1, 2], note })}>
              Write {count} variation{count === 1 ? "" : "s"}
            </Button>
          </>
        )}
      </div>
    );

  const all = [s.versions.find((v) => v.slot === 0), ...written].filter((v): v is Version => !!v);
  const visible = rail ? all : all.filter((v) => v.slot === shown);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-sm text-muted">
          {written.length} variation{written.length === 1 ? "" : "s"} · {written.filter((v) => v.status !== "draft").length} approved
        </p>
        <label className="inline-flex min-h-control items-center gap-2 text-sm lg:min-h-control-dense">
          <input type="checkbox" role="switch" checked={changesOnly} onChange={(e) => setChangesOnly(e.target.checked)} className="size-5" />
          Changes only
        </label>
      </div>
      {!rail && <Tabs label="Version" value={String(shown)} onChange={(id) => setShown(Number(id))} tabs={all.map((v) => ({ id: String(v.slot), label: `${LETTER[v.slot]}${v.status !== "draft" && v.slot > 0 ? " ✓" : ""}` }))} />}
      {error && <p role="alert" className={errorClass}>{error.message}</p>}
      <ul className={`grid gap-4 ${rail ? (all.length === 3 ? "grid-cols-3" : "grid-cols-2") : ""}`}>
        {visible.map((v) => (
          <li key={v.slot} aria-label={`Version ${LETTER[v.slot]}`} className="min-w-0">
            <Column version={v} original={original} changesOnly={changesOnly} act={act} writing={act.writing && act.slots.includes(v.slot)} stop={stop} regenerate={(note) => act.write.mutate({ slots: [v.slot as 1 | 2], note })} price={price.data} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function Column({ version: v, original, changesOnly, act, writing, stop, regenerate, price }: { version: Version; original: string; changesOnly: boolean; act: ReturnType<typeof useVariations>; writing: boolean; stop: string | null; regenerate: (note: string) => void; price?: number }) {
  const [editing, setEditing] = useState<string | null>(null);
  const [asking, setAsking] = useState<string | null>(null);
  const letter = LETTER[v.slot];
  const marks = v.slot > 0 ? changedLines(original, v.text) : [];
  const lines = v.text.split("\n");
  const hidden = changesOnly && v.slot > 0;
  const rows: { n: number; text: string; changed: boolean }[] = [];
  let quiet = 0;
  lines.forEach((text, i) => {
    if (hidden && !marks[i]) {
      quiet += 1;
      return;
    }
    if (quiet) rows.push({ n: -1, text: `· ${quiet} unchanged line${quiet === 1 ? "" : "s"} ·`, changed: false });
    quiet = 0;
    rows.push({ n: i + 1, text, changed: !!marks[i] });
  });
  if (quiet) rows.push({ n: -1, text: `· ${quiet} unchanged line${quiet === 1 ? "" : "s"} ·`, changed: false });
  const approved = v.status !== "draft";
  return (
    <Card className="flex h-full flex-col gap-3 p-4">
      <div className="space-y-1">
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-display text-md font-bold">
            {letter} · {NAME[v.slot]}
          </h3>
          {v.slot === 0 ? <Badge icon={Lock}>Words final</Badge> : approved ? <Badge tone="success" icon={Check}>Approved</Badge> : <Badge>Draft</Badge>}
        </div>
        {v.slot > 0 && v.changes.length > 0 && <p className="line-clamp-2 text-sm text-muted">What changed: {v.changes.join("; ")}</p>}
      </div>
      {editing !== null ? (
        <div className="space-y-2">
          <TextArea label={`Words of version ${letter}`} rows={14} maxLength={50000} value={editing} onChange={(e) => setEditing(e.target.value)} />
          <div className="flex gap-2">
            <Button busy={act.edit.isPending} disabled={!editing.trim()} onClick={() => act.edit.mutate({ slot: v.slot, text: editing }, { onSuccess: () => setEditing(null) })}>
              Save
            </Button>
            <Button variant="ghost" onClick={() => setEditing(null)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <ol aria-label={`Script text of version ${letter}`} className="flex-1 rounded-md border border-border bg-surface p-3 font-script text-sm leading-[1.6] [overflow-wrap:anywhere]">
          {rows.map((r, i) => (
            <li key={i} className={r.n < 0 ? "py-1 text-center text-xs text-faint" : "grid grid-cols-[1.75rem_1fr] gap-2"}>
              {r.n >= 0 && <span className="text-right text-xs text-faint">{r.n}</span>}
              <span className={r.changed ? "bg-mark underline decoration-mark-line decoration-2 underline-offset-2" : ""}>{r.text}</span>
            </li>
          ))}
        </ol>
      )}
      {v.slot === 0 ? (
        <p className="flex items-center gap-1 text-sm text-muted">
          <Lock size={16} strokeWidth={1.75} aria-hidden /> Your script · words final
        </p>
      ) : approved ? (
        <p className="flex items-center gap-1 text-sm text-muted">
          <Lock size={16} strokeWidth={1.75} aria-hidden /> Approved · words final
        </p>
      ) : editing === null ? (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" icon={Check} busy={act.approve.isPending} onClick={() => act.approve.mutate(v.slot)}>
              Approve
            </Button>
            <Button variant="ghost" icon={Pencil} onClick={() => setEditing(v.text)}>
              Edit
            </Button>
            {asking === null && (
              <Button variant="ghost" icon={RotateCcw} price={price} busy={writing} disabled={act.writing || stop !== null} reason={stop} onClick={() => setAsking("")}>
                Regenerate
              </Button>
            )}
          </div>
          {asking !== null && (
            <div className="space-y-2">
              <TextArea label="What should change? (optional)" rows={2} maxLength={2000} value={asking} onChange={(e) => setAsking(e.target.value)} />
              <div className="flex gap-2">
                <Button icon={RotateCcw} busy={act.write.isPending || writing} disabled={act.writing || stop !== null} reason={stop} price={price} onClick={() => regenerate(asking)}>
                  Regenerate
                </Button>
                <Button variant="ghost" onClick={() => setAsking(null)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </Card>
  );
}
