import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Ellipsis, Lock, Pencil, RotateCcw, Undo2 } from "lucide-react";
import { api, errorText } from "../api/client";
import { useJobs } from "../clip/History";
import { Badge, Banner, Button, Card, Dialog, Menu, MenuItem, Skeleton, Tabs, TextArea } from "../components";
import { useMe } from "../auth/useMe";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useRail } from "../useMedia";
import { useApproveAllWith, type ApproveAllResult } from "../projects/ApproveAll";
import { useAllowanceStop, type Script } from "./useScript";
import { serverTime } from "../time";

const LETTER = ["A", "B", "C"];
const NAME = ["Original", "Variation", "Variation"];
const GOING = ["queued", "running", "needs_owner_approval"];

type Version = Script["versions"][number];

/** Which lines of a version are not in the original, so they can be marked the same way as Directions. */
export function changedLines(original: string, text: string): boolean[] {
  const had = new Set(original.split("\n").map((l) => l.trim()));
  return text.split("\n").map((l) => l.trim() !== "" && !had.has(l.trim()));
}

/** The first line of an earlier text that the text on screen doesn't have, so earlier entries can be told apart. */
const firstDifference = (now: string, earlier: string) => {
  const had = new Set(now.split("\n").map((l) => l.trim()));
  return earlier.split("\n").map((l) => l.trim()).find((l) => l !== "" && !had.has(l)) ?? "";
};

/** The variations written so far (slots 1 and 2 with words). */
export const writtenVariations = (s: Script) => s.versions.filter((v) => v.slot > 0 && v.text.trim() !== "");

/** Why Next is held on this step, or null: every variation that was written has to be approved first. */
export function variationsReason(s: Script): string | null {
  const open = writtenVariations(s).find((v) => v.status === "draft");
  return open ? `Approve or remove variation ${LETTER[open.slot]} first.` : null;
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
  // A write for this script that is still going, from the job list: it shows on any tab or device, not just where it was started.
  const going = jobs.data?.some((j) => j.script_id === s.id && j.step === "variations" && GOING.includes(j.status)) ?? false;
  const writing = going || (jobId !== null && (!job || GOING.includes(job.status)));
  const failed = !writing && !!job && job.status !== "succeeded";
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["script-lib", s.id] }), queryClient.invalidateQueries({ queryKey: ["scripts"] })]);
  const was = useRef(writing);
  useEffect(() => {
    // When a write that was going stops, read the new words; the remembered job is done with.
    if (was.current && !writing && !failed) {
      try {
        sessionStorage.removeItem(key);
      } catch {
        /* nothing remembered */
      }
      void refresh().then(() => toast("Variations ready. Read them side by side."));
    }
    was.current = writing;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [writing]);
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
  const unapprove = useMutation({
    mutationFn: async (slot: number) => {
      const { data, error } = await api.DELETE("/scripts/{script_id}/drafts/{slot}/approve", { params: { path: { script_id: s.id, slot } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (data) => {
      queryClient.setQueryData(["script-lib", s.id], data);
      await refresh();
    },
  });
  const remove = useMutation({
    mutationFn: async (slot: number) => {
      const { error, response } = await api.DELETE("/scripts/{script_id}/drafts/{slot}", { params: { path: { script_id: s.id, slot } } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: refresh,
  });
  return { write, edit, approve, unapprove, remove, writing, failed, slots: run?.slots ?? [1, 2], retry: () => remember(null) };
}

/** Step 4: choose how many variations, write them at one price, then read them next to the original and approve each. */
export function VariationsStep({ script: s, own, onPicked }: { script: Script; own: boolean; onPicked: (n: number) => void }) {
  const rail = useRail();
  const { data: me } = useMe();
  const act = useVariations(s);
  const mayReadEarlier = me?.role === "owner" || s.created_by_id === me?.id; // the server keeps earlier texts to the author and Reed
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
  const error = act.write.error ?? act.edit.error ?? act.approve.error ?? act.unapprove.error ?? act.remove.error;
  const queryClient = useQueryClient();
  const drafts = written.filter((v) => v.status === "draft").length;
  const approveAll = useApproveAllWith({
    noun: "version",
    ready: drafts,
    waiting: s.versions.filter((v) => v.slot > 0 && v.status === "draft").length, // one still being written is waiting too, so the button says "Approve 1"
    press: async () => {
      const { data, error } = await api.POST("/scripts/{script_id}/drafts/approve-all", { params: { path: { script_id: s.id } } });
      if (!data) throw new Error(errorText(error));
      return data as ApproveAllResult;
    },
    undo: async (ids) => {
      const back = await api.POST("/scripts/{script_id}/drafts/approve-all/undo", { params: { path: { script_id: s.id } }, body: { ids } });
      if (back.data) queryClient.setQueryData(["script-lib", s.id], back.data);
      return back;
    },
    refresh: () => Promise.all([queryClient.invalidateQueries({ queryKey: ["script-lib", s.id] }), queryClient.invalidateQueries({ queryKey: ["scripts"] })]),
    name: (k) => k.label ?? "",
    target: (k) => `Version ${k.label}`,
  });

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
        <span className="ml-auto flex w-full sm:w-auto">{approveAll.button}</span>
      </div>
      {approveAll.line}
      {!rail && <Tabs label="Version" value={String(shown)} onChange={(id) => setShown(Number(id))} tabs={all.map((v) => ({ id: String(v.slot), label: `${LETTER[v.slot]}${v.status !== "draft" && v.slot > 0 ? " ✓" : ""}` }))} />}
      {error && <p role="alert" className={errorClass}>{error.message}</p>}
      <ul className={`grid gap-4 ${rail ? (all.length === 3 ? "grid-cols-3" : "grid-cols-2") : ""}`}>
        {visible.map((v) => (
          <li key={v.slot} aria-label={`Version ${LETTER[v.slot]}`} className="min-w-0">
            <Column version={v} mayReadEarlier={mayReadEarlier} scriptId={s.id} published={s.published} original={original} changesOnly={changesOnly} act={act} writing={act.writing && act.slots.includes(v.slot)} stop={stop} regenerate={(note) => act.write.mutate({ slots: [v.slot as 1 | 2], note })} price={price.data} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function Column({ version: v, mayReadEarlier, scriptId, published, original, changesOnly, act, writing, stop, regenerate, price }: { version: Version; mayReadEarlier: boolean; scriptId: number; published: boolean; original: string; changesOnly: boolean; act: ReturnType<typeof useVariations>; writing: boolean; stop: string | null; regenerate: (note: string) => void; price?: number }) {
  const [editing, setEditing] = useState<string | null>(null);
  const [asking, setAsking] = useState<string | null>(null);
  const [removing, setRemoving] = useState(false);
  const toast = useToast();
  const letter = LETTER[v.slot];
  const final = published;
  const earlier = useQuery({
    enabled: mayReadEarlier && v.slot > 0 && v.status === "draft" && !final,
    queryKey: ["script-history", v.slot, v.text],
    queryFn: async () => (await api.GET("/scripts/{script_id}/drafts/{slot}/history", { params: { path: { script_id: scriptId, slot: v.slot } } })).data ?? [],
  });
  const before = (earlier.data ?? []).filter((e) => e.text !== v.text);
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
          <div className="flex items-center gap-1">
            {v.slot === 0 ? <Badge icon={Lock}>Words final</Badge> : approved ? <Badge tone="success" icon={Check}>Approved</Badge> : <Badge>Draft</Badge>}
            {v.slot > 0 && !approved && !final && (
              <Menu
                title={`Version ${letter}`}
                align="right"
                trigger={(p) => (
                  <button type="button" {...p} aria-label={`More for version ${letter}`} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-control-dense">
                    <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
                  </button>
                )}
              >
                {(close) => (
                  <MenuItem
                    danger
                    onClick={() => {
                      close();
                      setRemoving(true);
                    }}
                  >
                    Remove variation {letter}
                  </MenuItem>
                )}
              </Menu>
            )}
          </div>
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
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="flex items-center gap-1 text-sm text-muted">
            <Lock size={16} strokeWidth={1.75} aria-hidden /> Approved · words final
          </p>
          {!final && (
            <Button variant="ghost" icon={Undo2} busy={act.unapprove.isPending} onClick={() => act.unapprove.mutate(v.slot)}>
              Undo approval
            </Button>
          )}
        </div>
      ) : editing === null ? (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" icon={Check} busy={act.approve.isPending} onClick={() => act.approve.mutate(v.slot)}>
              Approve
            </Button>
            <Button variant="ghost" icon={Pencil} onClick={() => setEditing(v.text)}>
              Edit
            </Button>
            {before.length > 0 && (
              <Menu
                title={`Earlier texts of version ${letter}`}
                trigger={(p) => (
                  <Button variant="ghost" {...p}>
                    Earlier: {before.length}
                  </Button>
                )}
              >
                {(close) =>
                  before.map((e) => (
                    <MenuItem
                      key={e.id}
                      onClick={() => {
                        close();
                        act.edit.mutate({ slot: v.slot, text: e.text }, { onSuccess: () => toast(`Brought back the ${e.source === "variations" ? "written" : "edited"} text from earlier.`) });
                      }}
                    >
                      <span className="block">
                        {serverTime(e.created_at).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} · {e.source === "variations" ? "written" : "edited"} · {e.words} words
                      </span>
                      <span className="block max-w-64 truncate text-xs text-muted">{firstDifference(v.text, e.text)}</span>
                    </MenuItem>
                  ))
                }
              </Menu>
            )}
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
      {removing && (
        <Dialog title={`Remove variation ${letter}?`} cancelLabel="Keep it" actionLabel="Remove" danger busy={act.remove.isPending} onCancel={() => setRemoving(false)} onConfirm={() => act.remove.mutate(v.slot, { onSuccess: () => setRemoving(false), onError: () => setRemoving(false) })}>
          It won't be made.
        </Dialog>
      )}
    </Card>
  );
}
