import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Ellipsis, Pencil, RotateCcw, Undo2 } from "lucide-react";
import { api, errorText } from "../api/client";
import { GOING, useJobs } from "../clip/History";
import { Banner, Button, Dialog, Dot, Menu, MenuItem, Skeleton, Tabs, TextArea } from "../components";
import { useMe } from "../auth/useMe";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useRail } from "../useMedia";
import type { Script } from "./useScript";
import { serverTime } from "../time";
import { refreshJobs } from "../jobs/refresh";

const LETTER = ["A", "B", "C"];

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
      await refreshJobs(queryClient); // the job list polls while anything is going
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

/** Step 3 (v5 G_Variations): how many more to write in the header, then the versions side by side, each with its own
 *  status and presses at its foot. Optional: most scripts go out as one version. */
export function VariationsStep({ script: s, own }: { script: Script; own: boolean }) {
  const rail = useRail();
  const { data: me } = useMe();
  const act = useVariations(s);
  const mayReadEarlier = me?.role === "owner" || s.created_by_id === me?.id; // the server keeps earlier texts to the author and Reed
  const written = writtenVariations(s);
  const original = s.versions.find((v) => v.slot === 0)?.text ?? "";
  const price = useQuery({ queryKey: ["variations-estimate", s.id], queryFn: async () => (await api.GET("/scripts/{script_id}/variations/estimate", { params: { path: { script_id: s.id } } })).data?.credits });
  // Slots B and C that have no words yet (and aren't being written) can still be written.
  const free = ([1, 2] as const).filter((n) => !written.some((v) => v.slot === n) && !(act.writing && act.slots.includes(n)));
  const [count, setCount] = useState(free.length);
  const n = Math.min(count, free.length) || free.length;
  const [note, setNote] = useState("");
  const [shown, setShown] = useState(1);
  const error = act.write.error ?? act.edit.error ?? act.approve.error ?? act.unapprove.error ?? act.remove.error;
  const writeLabel = `Write ${n}${written.length > 0 ? " more" : ` variation${n === 1 ? "" : "s"}`}`;

  const header = (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-col gap-0.5">
        <h2 className="type-card">Variations</h2>
        <p className="text-xs text-muted">{own ? "Optional. Most scripts go out as one version. " : ""}Writing variations makes A's words final.</p>
      </div>
      {!s.published && free.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-muted">
            How many?
            <select value={n} onChange={(e) => setCount(Number(e.target.value))} className="min-h-control rounded-sm border border-border bg-transparent px-2 text-sm text-text lg:min-h-control-dense">
              {free.map((_, i) => (
                <option key={i} value={i + 1}>
                  {i + 1}
                </option>
              ))}
            </select>
          </label>
          <Button variant="secondary" dense busy={act.write.isPending} disabled={act.writing} charge="estimate" price={price.data} onClick={() => act.write.mutate({ slots: free.slice(0, n), note })}>
            {writeLabel}
          </Button>
        </div>
      )}
    </div>
  );

  if (act.writing && written.length === 0)
    return (
      <div className="space-y-4">
        {header}
        <div className="space-y-3" role="status" aria-label="Writing variations">
          <p className="text-muted">Writing {act.slots.length === 1 ? "1 variation" : "variations"}… This takes a little while.</p>
          <div className="grid gap-4 lg:grid-cols-3">
            <Skeleton className="h-64" />
            <Skeleton className="h-64" />
          </div>
        </div>
      </div>
    );

  const all = [s.versions.find((v) => v.slot === 0), ...written].filter((v): v is Version => !!v);
  const visible = rail ? all : all.filter((v) => v.slot === (all.some((x) => x.slot === shown) ? shown : all[0]?.slot));
  return (
    <div className="space-y-4">
      {header}
      {act.failed && (
        <Banner title="The variations didn't finish. Nothing was charged." action={<Button variant="secondary" onClick={act.retry}>Try again</Button>}>
          Check your connection and try again.
        </Banner>
      )}
      {written.length === 0 && !s.published && free.length > 0 && (
        <div className="max-w-[680px]">
          <TextArea label="Direction (optional)" rows={2} maxLength={2000} placeholder="e.g. swap the altar for a car showroom; keep the payoff about money" value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
      )}
      {error && <p role="alert" className={errorClass}>{error.message}</p>}
      {!rail && all.length > 1 && <Tabs label="Version" value={String(visible[0]?.slot ?? 0)} onChange={(id) => setShown(Number(id))} tabs={all.map((v) => ({ id: String(v.slot), label: `${LETTER[v.slot]}${v.status !== "draft" && v.slot > 0 ? " ✓" : ""}` }))} />}
      <ul className="grid gap-4 lg:grid-cols-3">
        {visible.map((v) => (
          <li key={v.slot} aria-label={`Version ${LETTER[v.slot]}`} className="min-w-0">
            <Column version={v} mayReadEarlier={mayReadEarlier} scriptId={s.id} published={s.published} original={original} act={act} writing={act.writing && act.slots.includes(v.slot)} regenerate={(note) => act.write.mutate({ slots: [v.slot as 1 | 2], note })} price={price.data} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function Column({ version: v, mayReadEarlier, scriptId, published, original, act, writing, regenerate, price }: { version: Version; mayReadEarlier: boolean; scriptId: number; published: boolean; original: string; act: ReturnType<typeof useVariations>; writing: boolean; regenerate: (note: string) => void; price?: number }) {
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
  const approved = v.status !== "draft";
  const draft = v.slot > 0 && !approved && !final;
  return (
    <article className="flex h-full flex-col gap-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-medium">Version {letter}</h3>
        <span className="flex items-center gap-1 text-xs">
          {v.slot === 0 ? <Dot tone="success">Words final</Dot> : approved ? <Dot tone="success">Approved</Dot> : <Dot tone="warning">Draft</Dot>}
          {draft && editing === null && (
            <Menu
              title={`Version ${letter}`}
              align="right"
              trigger={(p) => (
                <button type="button" {...p} aria-label={`More for version ${letter}`} className="-my-1.5 grid size-control place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-control-dense">
                  <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
                </button>
              )}
            >
              {(close) => (
                <>
                  <MenuItem onClick={() => { close(); setEditing(v.text); }}>
                    <Pencil size={20} strokeWidth={1.75} aria-hidden /> Edit the words
                  </MenuItem>
                  <MenuItem onClick={() => { close(); setAsking(""); }}>
                    <RotateCcw size={20} strokeWidth={1.75} aria-hidden /> Write it again…
                  </MenuItem>
                  {before.map((e) => (
                    <MenuItem
                      key={e.id}
                      onClick={() => {
                        close();
                        act.edit.mutate({ slot: v.slot, text: e.text }, { onSuccess: () => toast(`Brought back the ${e.source === "variations" ? "written" : "edited"} text from earlier.`) });
                      }}
                    >
                      <span className="block">
                        Bring back {serverTime(e.created_at).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} · {e.source === "variations" ? "written" : "edited"} · {e.words} words
                        <span className="block max-w-64 truncate text-xs text-muted">{firstDifference(v.text, e.text)}</span>
                      </span>
                    </MenuItem>
                  ))}
                </>
              )}
            </Menu>
          )}
        </span>
      </div>
      {v.slot > 0 && v.changes.length > 0 && <p className="line-clamp-2 text-xs text-muted">What changed: {v.changes.join("; ")}</p>}
      {editing !== null ? (
        <div className="space-y-2">
          <TextArea label={`Words of version ${letter}`} rows={12} maxLength={50000} value={editing} onChange={(e) => setEditing(e.target.value)} />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button busy={act.edit.isPending} disabled={!editing.trim()} onClick={() => act.edit.mutate({ slot: v.slot, text: editing }, { onSuccess: () => setEditing(null) })}>
              Save
            </Button>
          </div>
        </div>
      ) : (
        <div aria-label={`Script text of version ${letter}`} className={`type-script flex-1 whitespace-pre-line text-[13px] text-text/80 [overflow-wrap:anywhere] ${writing ? "opacity-50" : ""}`}>
          {v.text.split("\n").map((line, i) => (
            <span key={i} className={`block ${marks[i] ? "bg-mark shadow-[inset_0_-2px_0_var(--color-mark-line)]" : ""}`}>
              {line || " "}
            </span>
          ))}
        </div>
      )}
      {asking !== null && (
        <div className="space-y-2">
          <TextArea label="What should change? (optional)" rows={2} maxLength={2000} value={asking} onChange={(e) => setAsking(e.target.value)} />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setAsking(null)}>
              Cancel
            </Button>
            <Button variant="secondary" icon={RotateCcw} busy={act.write.isPending || writing} disabled={act.writing} charge="estimate" price={price} onClick={() => { regenerate(asking); setAsking(null); }}>
              Write it again
            </Button>
          </div>
        </div>
      )}
      {v.slot > 0 && !final && editing === null && asking === null && (
        approved ? (
          <div className="mt-auto flex justify-end">
            <Button variant="secondary" dense icon={Undo2} busy={act.unapprove.isPending} onClick={() => act.unapprove.mutate(v.slot)}>
              Undo approval
            </Button>
          </div>
        ) : (
          <div className="mt-auto flex flex-wrap justify-between gap-2">
            <Button variant="secondary" dense onClick={() => setRemoving(true)}>
              Remove
            </Button>
            <Button icon={Check} busy={act.approve.isPending} disabled={writing} onClick={() => act.approve.mutate(v.slot)}>
              Approve {letter}
            </Button>
          </div>
        )
      )}
      {removing && (
        <Dialog title={`Remove variation ${letter}?`} cancelLabel="Keep it" actionLabel="Remove" danger busy={act.remove.isPending} onCancel={() => setRemoving(false)} onConfirm={() => act.remove.mutate(v.slot, { onSuccess: () => setRemoving(false), onError: () => setRemoving(false) })}>
          It won't be made.
        </Dialog>
      )}
    </article>
  );
}
