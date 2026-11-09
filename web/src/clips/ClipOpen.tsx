import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeftRight, Download, Eye, Image as ImageIcon, LoaderCircle, Pencil, RefreshCw, Volume2 } from "lucide-react";
import { api, errorText, must } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Button, TextArea, buttonClass, useToast, useViewOnly } from "../components";
import { refreshJobs } from "../jobs/refresh";
import { mp4, type Head } from "../videos/VideoHead";
import { spent, upTo } from "../videos/money";
import { blocking } from "../projects/problems";
import { RowStatus } from "./RowStatus";
import { SwapBroll } from "../cut/SwapBroll";
import { useCut } from "../projects/useProgress";
import { markWatched, type Clip, type Frame, type Row, type Scene, type Take } from "./data";

type Project = components["schemas"]["ProjectOut"];

/** A press with its price after the label ("Another take · up to $0.32"); `null` waits for the price. */
function Priced({ label, price, wide, ...rest }: { label: string; price: string | null | undefined; wide?: boolean } & Omit<Parameters<typeof Button>[0], "children" | "price" | "charge">) {
  return (
    <Button variant="secondary" className={wide ? "w-full justify-start" : ""} {...rest} busy={price === null || rest.busy}>
      {label}
      {price && (
        <>
          {" "}
          <span className="font-normal text-muted">· {price}</span>
        </>
      )}
    </Button>
  );
}

/** "Cartoon eyes landed on the stomach" → "cartoon eyes landed on the stomach", for "Dropped: …". */
const lower = (t: string) => (t ? t[0].toLowerCase() + t.slice(1) : t).replace(/\.$/, "");

/** A take's line under it (S6-02, S6-03, S-gaps-08): dropped and why, remade on what, kept by whom, or not used. */
function takeLine(t: Take, inCut: boolean, all: Take[], stillNo: (file: number) => number | null) {
  const w = t.watch;
  const from = t.from_still != null && stillNo(t.from_still) ? ` · from still ${stillNo(t.from_still)}` : "";
  if (w?.kept_by) return `Kept by ${w.kept_by}${from}`;
  if (!inCut && w?.action === "redo" && w.found) return `Dropped: ${lower(w.found)}`;
  if (t.remade_from) return `Remade${t.model ? ` on ${t.model}` : ""}${from}`;
  if (!inCut) return all.some((x) => x.id !== t.id) ? `Not used${from}` : "";
  return t.model ? `Made on ${t.model}${from}` : from.replace(/^ · f/, "F");
}

/** What the director's watch found and did on this clip (S6-03), or what it flagged for a person (S6-04). */
function Found({ clip, head, phone, onRemake, onKeep, busy }: { clip: Clip; head: Head | undefined; phone: boolean; onRemake: (note: string) => void; onKeep: (take: Take) => void; busy: boolean }) {
  const picked = clip.takes.find((t) => t.id === clip.picked_take_id);
  const asks = picked?.watch && (picked.watch.action === "flagged" || picked.watch.action === "unsure") ? picked : null;
  if (asks) {
    const w = asks.watch!;
    const remake = upTo(head, clip.take_credits);
    return (
      <div className="flex flex-col gap-3 rounded-lg bg-warning-soft px-3 py-2.5 text-sm text-warning">
        <p className="flex items-start gap-2">
          <Eye size={14} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
          <span>
            <b className="font-semibold">{w.found || "The director isn’t sure about this take."}</b> Remake it ({remake}), or keep it?
          </span>
        </p>
        <div className="flex flex-wrap gap-2">
          <Button icon={RefreshCw} busy={busy} onClick={() => onRemake(w.note ?? "")}>
            Remake it <span className="font-normal opacity-80">· {remake}</span>
          </Button>
          <Button variant="secondary" busy={busy} onClick={() => onKeep(asks)}>
            Keep it
          </Button>
        </div>
      </div>
    );
  }
  const dropped = clip.takes.find((t) => t.watch?.action === "redo" && (t.watch.found || t.watch.did));
  if (!dropped) return null;
  const w = dropped.watch!;
  const cost = w.remake_credits ? ` ${spent(head, w.remake_credits)}.` : ""; // nothing spent: no price
  return (
    <p className="flex items-start gap-2 rounded-lg bg-accent-soft px-3 py-2.5 text-sm text-accent-text">
      <Eye size={14} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
      <span>
        <b className="font-semibold">{phone ? "Found:" : `What I found watching take ${dropped.number}:`}</b> {w.found}
        {!phone && <br />} <b className="font-semibold">{phone ? "Did:" : "What I did:"}</b> {w.did}
        {cost}
      </span>
    </p>
  );
}

/** What stops this clip's take, in the server's plain words, with its one free fix (rule 22): the shape put right in code,
 *  or the prompt rewritten for this clip; a prompt the video model refused is reworded to pass the same way. A fix shows
 *  what changed, with Undo. Wording fixed for you on the way (P3) says so, with Undo. */
function Problems({ p, clip, onDone }: { p: Project; clip: Clip; onDone: () => Promise<unknown> }) {
  const toast = useToast();
  const viewOnly = useViewOnly();
  const path = { project_id: p.id, clip_id: clip.id };
  const stops = blocking(clip.problems, clip.kept);
  const refused = stops.some((x) => x.startsWith("The video model refused"));
  const fix = useMutation({
    mutationFn: async () => (await must(api.POST("/projects/{project_id}/clips/{clip_id}/fix", { params: { path } }))).data!,
    onSuccess: async (out) => {
      await onDone();
      if (out.fixed === true)
        toast("Fixed this clip’s prompt · free.", () => void must(api.PUT("/projects/{project_id}/clips/{clip_id}", { params: { path }, body: { prompt: out.before, references: clip.references } })).then(onDone));
      else if (out.fixed === false) toast(out.reason, undefined, "error");
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const undo = useMutation({ mutationFn: () => must(api.POST("/projects/{project_id}/clips/{clip_id}/auto-fix/undo", { params: { path } })), onSuccess: onDone, onError: (e: Error) => toast(e.message, undefined, "error") });
  const auto = clip.auto_fix && !clip.auto_fix.undone ? clip.auto_fix : null;
  if (!stops.length && !auto) return null;
  return (
    <div className="flex flex-col gap-2">
      {stops.length > 0 && (
        <div className="flex flex-col items-start gap-2 rounded-lg bg-danger-soft px-3 py-2.5 text-sm text-danger">
          <ul className="flex flex-col gap-1">
            {stops.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
          {!viewOnly && (
            <Button variant="secondary" busy={fix.isPending} onClick={() => fix.mutate()}>
              {refused ? "Reword it to pass" : "Fix this clip’s prompt"} <span className="font-normal text-muted">· free</span>
            </Button>
          )}
        </div>
      )}
      {auto && (
        <p className="flex flex-wrap items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm">
          <span className="flex-1">Fixed for you: {auto.fixed.join(", ")}.</span>
          {!viewOnly && (
            <Button variant="ghost" dense busy={undo.isPending} onClick={() => undo.mutate()}>
              Undo
            </Button>
          )}
        </p>
      )}
    </div>
  );
}

/** A real image an older cut still cuts in flat over a stretch, to switch off. A real product or screen is the clip's
 *  reference, never a flat cut-in (Reed, 8 Nov: rule 13), so none is switched on here. Free. */
function Inserts({ p, clip, onDone }: { p: Project; clip: Clip; onDone: () => Promise<unknown> }) {
  const toast = useToast();
  const viewOnly = useViewOnly();
  const set = useMutation({
    mutationFn: ({ shot, on }: { shot: string; on: boolean }) => must(api.PUT("/projects/{project_id}/clips/{clip_id}/inserts/{shot_id}", { params: { path: { project_id: p.id, clip_id: clip.id, shot_id: shot } }, body: { use_real_image: on } })),
    onSuccess: onDone,
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const cut = clip.inserts.filter((i) => i.use_real_image);
  if (!cut.length) return null;
  return (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="mb-1 text-xs font-semibold text-muted">Real images cut in by an older cut</legend>
      {cut.map((i) => (
        <label key={i.shot_id} className="flex min-h-11 items-center gap-2 text-sm lg:min-h-8">
          <input type="checkbox" checked={i.use_real_image} disabled={viewOnly || set.isPending} onChange={(e) => set.mutate({ shot: i.shot_id, on: e.target.checked })} className="size-4 accent-[var(--accent)]" />
          <span>
            Cut in the real image: {i.name} <span className="text-muted">· {i.start.toFixed(1)}–{i.end.toFixed(1)} s · free</span>
          </span>
        </label>
      ))}
    </fieldset>
  );
}

/** The last Change this… (or a still change's take) as it stands: being made, made nothing, or stopped and why, with the
 *  press that tries again (rule 22). */
function ChangeLine({ clip, busy, onAgain }: { clip: Clip; busy: boolean; onAgain: (note: string) => void }) {
  const c = clip.change as { status?: string; note?: string; error?: string; how?: string } | null;
  if (!c?.status) return null;
  // how: an Omni edit of the take, or why it's a new take instead (Reed, 9 Nov)
  const how = c.how ? <span className="block text-muted">{c.how}</span> : null;
  if (c.status === "changing") return <p role="status" className="rounded-lg bg-surface-2 px-3 py-2 text-sm">Changing it: “{c.note}”…{how}</p>;
  if (c.status === "unchanged") return <p className="rounded-lg bg-surface-2 px-3 py-2 text-sm text-muted">Your note “{c.note}” left the prompt as it was, so nothing was made or charged.</p>;
  if (c.status === "done" && how) return <p className="rounded-lg bg-surface-2 px-3 py-2 text-sm">{how}</p>;
  if (c.status !== "failed") return null;
  return (
    <div className="flex flex-col items-start gap-2 rounded-lg bg-danger-soft px-3 py-2.5 text-sm text-danger">
      <span>{c.error || "That change didn’t finish. Nothing was charged for it."}</span>
      <Button variant="secondary" busy={busy} onClick={() => onAgain(c.note ?? "")}>
        Try again
      </Button>
    </div>
  );
}

/** A clip made for an older plan: its prompt is written again for the new shots first, at its price (rule 22). */
function Rewrite({ p, head, clip, onDone }: { p: Project; head: Head | undefined; clip: Clip; onDone: () => Promise<unknown> }) {
  const toast = useToast();
  const viewOnly = useViewOnly();
  const price = useQuery({ queryKey: ["rewrite-price", p.id, clip.clip_id], retry: false, queryFn: async () => (await must(api.GET("/projects/{project_id}/clips/prompts/price", { params: { path: { project_id: p.id }, query: { clip_id: clip.clip_id } } }))).data!.credits });
  const rewrite = useMutation({
    mutationFn: () => must(api.POST("/projects/{project_id}/clips/prompts", { params: { path: { project_id: p.id } }, body: { clip_id: clip.clip_id } })),
    onSettled: onDone,
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  return (
    <div className="flex flex-col items-start gap-2 rounded-lg bg-warning-soft px-3 py-2.5 text-sm text-warning">
      <span>This clip was made for an older plan. Its prompt is written again for the new shots before another take.</span>
      {!viewOnly && <Priced label="Rewrite its prompt" price={price.isError ? undefined : price.data == null ? null : upTo(head, price.data)} busy={rewrite.isPending} onClick={() => rewrite.mutate()} />}
    </div>
  );
}

type Finding = { index: number; kind: string; text: string; note: string; fix?: string; at?: number | null; mute?: number[] | null };
type Check = { id: number; status: string; findings: Finding[]; kept?: Finding[] } | null | undefined;

/** How a check stands, in words: never "Looks fine" unless it really ran and found nothing (Reed, 4 Nov). */
function checkLine(what: string, c: Check) {
  if (!c) return `${what}: not checked.`;
  if (c.status === "checking") return `${what}: checking…`;
  if (c.status === "failed") return `${what}: the check didn’t finish, so it isn’t known. Watch it yourself.`;
  if (c.status === "skipped") return `${what}: not checked (paused at the budget). Watch it yourself.`;
  if (c.status === "ok" && !c.findings.length && !(c.kept ?? []).length) return `${what}: checked, nothing found.`;
  return null;
}

/** The still's own check (rule 21: a flag comes to a person; S-gaps-08's stills row): what it found on the still in use,
 *  each with its Advice, Change the still… (priced, with its note) and Keep it (Undo). Before a take too: a still is checked
 *  once it's drawn. */
function StillReview({ p, check, price, blocked, makes, onChange, onDone }: { p: Project; check: Check; price: string | null | undefined; blocked: string | null; makes: string; onChange: (note: string) => void; onDone: () => Promise<unknown> }) {
  const toast = useToast();
  const viewOnly = useViewOnly();
  const run = useMutation({ mutationFn: (f: () => Promise<unknown>) => f(), onSettled: onDone, onError: (e: Error) => toast(e.message, undefined, "error") });
  if (!check) return null;
  const at = (f: Finding, how: "dismiss" | "restore") => api.POST(`/projects/{project_id}/checks/{check_id}/findings/{index}/${how}` as "/projects/{project_id}/checks/{check_id}/findings/{index}/dismiss", { params: { path: { project_id: p.id, check_id: check.id, index: f.index } } });
  const keep = (f: Finding) =>
    run.mutate(async () => {
      await must(at(f, "dismiss"));
      toast("Kept as it is.", () => void must(at(f, "restore")).then(onDone));
    });
  const line = checkLine("The still", check);
  const kept = check.kept ?? [];
  return (
    <section aria-label="The still's check" className="flex flex-col gap-2">
      {line && <p className="text-sm text-muted">{line}</p>}
      {check.findings.map((f) => (
        <div key={f.index} className="flex flex-col items-start gap-2 rounded-lg bg-warning-soft px-3 py-2.5 text-sm text-warning">
          <span>
            <span className="font-medium">The still: </span>
            {f.text}
          </span>
          {!viewOnly && (
            <div className="flex flex-wrap items-center gap-2">
              <Priced icon={ImageIcon} label="Change the still…" price={price} disabled={!!blocked} reason={blocked} onClick={() => onChange(f.note)} />
              <span className="text-xs">{makes}</span>
              <Button variant="ghost" busy={run.isPending} onClick={() => keep(f)}>
                Keep it
              </Button>
            </div>
          )}
        </div>
      ))}
      {kept.length > 0 && (
        <div className="flex flex-col gap-1 text-sm text-muted">
          <span className="text-xs font-semibold">On the still: {kept.length} kept as it is</span>
          {kept.map((f) => (
            <span key={`k${f.index}`} className="flex flex-wrap items-center gap-2">
              <span className="flex-1">{f.text}</span>
              {!viewOnly && (
                <Button variant="ghost" dense busy={run.isPending} onClick={() => run.mutate(() => must(at(f, "restore")))}>
                  Undo
                </Button>
              )}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

/** The clip's review (Reed, item 6): what the checks and the director's watch found on the take in the cut, each with its
 *  action: Fix with a note (priced), Mute this stretch (free, Undo), or Keep it (Undo). Problems and doubts stay visible. */
function Review({ p, head, clip, fixPrice, fixError, onNote, onTake, takeBlock, onDone }: { p: Project; head: Head | undefined; clip: Clip; fixPrice: number | null | undefined; fixError?: string | null; onNote: (note: string) => void; onTake: () => void; takeBlock?: string | null; onDone: () => Promise<unknown> }) {
  const toast = useToast();
  const viewOnly = useViewOnly();
  const run = useMutation({ mutationFn: (f: () => Promise<unknown>) => f(), onSettled: onDone, onError: (e: Error) => toast(e.message, undefined, "error") });
  const picked = clip.takes.find((t) => t.id === clip.picked_take_id);
  if (!picked) return null;
  const path = { project_id: p.id, clip_id: clip.id };
  const keep = (c: NonNullable<Check>, f: Finding) =>
    run.mutate(async () => {
      await must(api.POST("/projects/{project_id}/checks/{check_id}/findings/{index}/dismiss", { params: { path: { project_id: p.id, check_id: c.id, index: f.index } } }));
      toast("Kept as it is.", () => void must(api.POST("/projects/{project_id}/checks/{check_id}/findings/{index}/restore", { params: { path: { project_id: p.id, check_id: c.id, index: f.index } } })).then(onDone));
    });
  const mute = (span: number[]) =>
    run.mutate(async () => {
      const out = (await must(api.POST("/projects/{project_id}/clips/{clip_id}/mute", { params: { path }, body: { start: span[0], end: span[1] } }))).data!;
      const i = (out.takes.find((t) => t.id === picked.id)?.mutes.length ?? 1) - 1;
      toast(`Muted ${span[0].toFixed(1)}–${span[1].toFixed(1)} s · free.`, () => void must(api.DELETE("/projects/{project_id}/clips/{clip_id}/mute/{index}", { params: { path: { ...path, index: i } } })).then(onDone));
    });
  const checks: [string, Check][] = [["Picture", picked.check as Check], ["Words", picked.words as Check]];
  // The director's watch: flagged or unsure takes ask above (Remake it / Keep it); here, how the watch stands and what it
  // found on a take it kept or held, with Another take, and Keep it on a held one.
  const w = picked.watch;
  const watchLine = !w ? null : w.state === "watching" ? "The director’s watch: watching…" : w.state === "failed" ? "The director’s watch didn’t finish, so it isn’t known. Watch it yourself." : w.state === "skipped" ? "The director’s watch was skipped (paused at the budget). Watch it yourself." : null;
  const faults = w && ["keep", "held"].includes(w.action ?? "") && !w.kept_by ? (w.faults ?? []) : [];
  const lines = [...checks.map(([x, c]) => checkLine(x, c)), watchLine].filter(Boolean) as string[];
  const findings = checks.flatMap(([, c]) => (c?.findings ?? []).map((f) => [c!, f] as const));
  const kept = checks.flatMap(([, c]) => (c?.kept ?? []).map((f) => [c!, f] as const));
  const muted = (span: number[]) => (picked.mutes ?? []).some((m) => Math.abs(m[0] - span[0]) < 0.05 && Math.abs(m[1] - span[1]) < 0.05);
  const fix = fixPrice == null ? null : upTo(head, fixPrice);
  return (
    <section aria-label="Review" className="flex flex-col gap-1.5 border-t border-border pt-5">
      <h4 className="mb-1 text-sm font-semibold">Review of take {picked.number}</h4>
      {lines.map((l) => (
        <p key={l} className="text-sm">
          {l}
        </p>
      ))}
      {faults.length > 0 && (
        <div className="flex flex-col items-start gap-2 rounded-lg bg-warning-soft px-3 py-2.5 text-sm text-warning">
          {faults.map((f) => (
            <span key={`${f.kind}-${f.at}-${f.says}`}>
              {f.at != null ? `${f.at.toFixed(1)} s · ` : ""}
              {f.says}
            </span>
          ))}
          {w?.action === "held" && <span className="text-xs">Its remake waits for the owner’s OK on the price.</span>}
          {!viewOnly && (
            <div className="flex flex-wrap gap-2">
              {!clip.stale && (
                <Button variant="secondary" busy={run.isPending} disabled={!!takeBlock} reason={takeBlock} onClick={onTake}>
                  Another take <span className="font-normal text-muted">· {upTo(head, clip.take_credits)}</span>
                </Button>
              )}
              {w?.action === "held" && (
                <Button variant="ghost" busy={run.isPending} onClick={() => run.mutate(() => must(api.POST("/projects/{project_id}/clips/{clip_id}/takes/{take_id}/keep", { params: { path: { ...path, take_id: picked.id } } })))}>
                  Keep it
                </Button>
              )}
            </div>
          )}
        </div>
      )}
      {findings.map(([c, f]) => (
        <div key={`${c.id}-${f.index}`} className="flex flex-col items-start gap-2 rounded-lg bg-warning-soft px-3 py-2.5 text-sm text-warning">
          <span>
            {f.at != null ? `${f.at.toFixed(1)} s · ` : ""}
            {f.text}
          </span>
          {f.fix && <span className="text-xs">{f.fix}</span>}
          {!viewOnly && (
            <div className="flex flex-wrap gap-2">
              {f.mute && f.mute.length === 2 && !muted(f.mute) && (
                <Button variant="secondary" busy={run.isPending} onClick={() => mute(f.mute!)}>
                  Mute this stretch <span className="font-normal text-muted">· free</span>
                </Button>
              )}
              {f.mute && f.mute.length === 2 && muted(f.mute) && <span className="text-xs">Muted in the cut.</span>}
              {f.note && !clip.stale && (
                <Button variant="secondary" busy={fix == null && !fixError} disabled={!!fixError} reason={fixError} onClick={() => onNote(f.note)}>
                  Fix it with a note {fix && <span className="font-normal text-muted">· {fix}</span>}
                </Button>
              )}
              <Button variant="ghost" busy={run.isPending} onClick={() => keep(c, f)}>
                Keep it
              </Button>
            </div>
          )}
        </div>
      ))}
      {kept.length > 0 && (
        <div className="flex flex-col gap-1 text-sm text-muted">
          <span className="text-xs font-semibold">{kept.length} kept as it is</span>
          {kept.map(([c, f]) => (
            <span key={`${c.id}-k${f.index}`} className="flex flex-wrap items-center gap-2">
              <span className="flex-1">{f.text}</span>
              {!viewOnly && (
                <Button variant="ghost" dense busy={run.isPending} onClick={() => run.mutate(() => must(api.POST("/projects/{project_id}/checks/{check_id}/findings/{index}/restore", { params: { path: { project_id: p.id, check_id: c.id, index: f.index } } })))}>
                  Undo
                </Button>
              )}
            </span>
          ))}
        </div>
      )}
      {(picked.mutes ?? []).map((m, i) => (
        <p key={`${m[0]}-${m[1]}`} className="flex flex-wrap items-center gap-2 text-sm text-muted">
          <span className="flex-1">
            Muted {m[0].toFixed(1)}–{m[1].toFixed(1)} s in the cut.
          </span>
          {!viewOnly && (
            <Button variant="ghost" dense busy={run.isPending} onClick={() => run.mutate(() => must(api.DELETE("/projects/{project_id}/clips/{clip_id}/mute/{index}", { params: { path: { ...path, index: i } } })))}>
              Hear it again
            </Button>
          )}
        </p>
      ))}
    </section>
  );
}

/** History (Reed, item 4): the clip's earlier prompts, each with Go back to this. Going back is free and never makes a take;
 *  it says first what stays and what a new take from it would cost. Earlier stills and takes are in the row above. */
function History({ p, head, clip, onDone }: { p: Project; head: Head | undefined; clip: Clip; onDone: () => Promise<unknown> }) {
  const toast = useToast();
  const viewOnly = useViewOnly();
  const [asking, setAsking] = useState<number | null>(null);
  const run = useMutation({ mutationFn: (f: () => Promise<unknown>) => f(), onSettled: onDone, onError: (e: Error) => toast(e.message, undefined, "error") });
  const earlier = (clip.versions ?? []).filter((v) => !v.current);
  if (!earlier.length) return null;
  const go = (index: number) =>
    run.mutate(async () => {
      await must(api.POST("/projects/{project_id}/clips/{clip_id}/versions/{index}/use", { params: { path: { project_id: p.id, clip_id: clip.id, index } } }));
      setAsking(null);
      toast("That prompt is in use again. Nothing was made.", () => void must(api.POST("/projects/{project_id}/clips/{clip_id}/versions/{index}/use", { params: { path: { project_id: p.id, clip_id: clip.id, index: 1 } } })).then(onDone));
    });
  return (
    <details className="group rounded-lg border border-border">
      <summary className="flex min-h-11 cursor-pointer items-center px-3 text-sm font-medium lg:min-h-9">History · {earlier.length} earlier prompt{earlier.length === 1 ? "" : "s"}</summary>
      <ul className="flex flex-col gap-3 border-t border-border p-3">
        {earlier.map((v) => (
          <li key={v.index} className="flex flex-col gap-1.5">
            <span className="text-xs text-muted">
              {new Date(v.made_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
              {v.made_by ? ` · ${v.made_by.name}` : " · the director"}
            </span>
            <p className="rounded-md bg-surface-2 px-3 py-2 font-mono text-xs whitespace-pre-wrap text-text/80">{v.prompt}</p>
            {!viewOnly &&
              (asking === v.index ? (
                <div className="flex flex-col items-start gap-2 text-sm">
                  <span className="text-muted">Free. Nothing is made: the take in the cut stays as it is. To see it, make Another take from it after ({upTo(head, clip.take_credits)}).</span>
                  <div className="flex gap-2">
                    <Button variant="secondary" busy={run.isPending} onClick={() => go(v.index)}>
                      Use this prompt again
                    </Button>
                    <Button variant="ghost" onClick={() => setAsking(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <button type="button" onClick={() => setAsking(v.index)} className="self-start text-xs font-medium text-accent-text hover:underline max-lg:min-h-11">
                  Go back to this prompt
                </button>
              ))}
          </li>
        ))}
      </ul>
    </details>
  );
}

/** What changed (Reed, item 5): the last change's note, the prompt before and after, and Restore the earlier version (free:
 *  the earlier take comes back with its prompt, or the earlier still). */
function WhatChanged({ p, clip, frame, stillUse, onStill, onDone }: { p: Project; clip: Clip; frame: Frame | undefined; stillUse: (file: number) => string; onStill: (file: number) => void; onDone: () => Promise<unknown> }) {
  const toast = useToast();
  const viewOnly = useViewOnly();
  const run = useMutation({ mutationFn: (f: () => Promise<unknown>) => f(), onSettled: onDone, onError: (e: Error) => toast(e.message, undefined, "error") });
  type Change = { status?: string; note?: string; before?: string; after?: string; was_take_id?: number | null; was_file_id?: number | null } | null;
  const parts = [
    ["This clip", clip.change as Change, "clip"],
    ["Its still", (frame?.change ?? null) as Change, "still"],
  ] as const;
  // Shown until the earlier version is back in use (then there's nothing left to restore).
  const shown = parts.filter(([, c, kind]) => c?.status === "done" && c.before && c.after && c.before !== c.after && (kind === "clip" ? clip.prompt !== c.before : frame?.file_id !== c.was_file_id));
  if (!shown.length) return null;
  const restore = (kind: "clip" | "still", c: NonNullable<Change>) =>
    run.mutate(async () => {
      if (kind === "still" && c.was_file_id) return onStill(c.was_file_id); // as Use this still: its take back, or priced
      if (kind === "clip" && c.was_take_id && clip.takes.some((t) => t.id === c.was_take_id)) await must(api.POST("/projects/{project_id}/clips/{clip_id}/takes/{take_id}/use", { params: { path: { project_id: p.id, clip_id: clip.id, take_id: c.was_take_id } } }));
      else await must(api.PUT("/projects/{project_id}/clips/{clip_id}", { params: { path: { project_id: p.id, clip_id: clip.id } }, body: { prompt: c.before!, references: clip.references } }));
      toast("The earlier version is back. Nothing was charged.");
    });
  return (
    <details className="rounded-lg border border-border">
      <summary className="flex min-h-11 cursor-pointer items-center px-3 text-sm font-medium lg:min-h-9">What changed</summary>
      <div className="flex flex-col gap-3 border-t border-border p-3">
        {shown.map(([label, c, kind]) => (
          <div key={kind} className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">
              {label}
              {c!.note ? `: “${c!.note}”` : ""}
            </span>
            <span className="text-xs font-semibold text-muted">Before</span>
            <p className="rounded-md bg-surface-2 px-3 py-2 font-mono text-xs whitespace-pre-wrap text-text/80">{c!.before}</p>
            <span className="text-xs font-semibold text-muted">After</span>
            <p className="rounded-md bg-surface-2 px-3 py-2 font-mono text-xs whitespace-pre-wrap text-text/80">{c!.after}</p>
            {!viewOnly && (
              <Button variant="secondary" className="self-start" busy={run.isPending} onClick={() => restore(kind, c!)}>
                Restore the earlier version <span className="font-normal text-muted">· {kind === "still" && c!.was_file_id ? stillUse(c!.was_file_id) : "free"}</span>
              </Button>
            )}
          </div>
        ))}
      </div>
    </details>
  );
}

/** One clip open (S6-02, S6-03, S6-06, P-11, S-gaps-08): its stills and takes, what the watch found, the model and why, the
 *  words over it, what it cost, the director's prompt (read and edit), and its presses, each with its "up to" price. */
export function ClipOpen({ p, head, row, clip, frames, scene, phone, onCast }: { p: Project; head: Head | undefined; row: Row; clip: Clip; frames: Frame[]; scene: Scene; phone: boolean; onCast: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const viewOnly = useViewOnly();
  const [box, setBox] = useState<null | { kind: "change" | "still" | "sound" | "prompt"; text: string }>(null);
  const [recut, setRecut] = useState(false);
  const [swapping, setSwapping] = useState(false);
  const cut = useCut(p.id).data;
  const piece = row.broll && cut?.can_edit ? cut.timeline.pieces.find((x) => x.clip_id === row.clip_id) : undefined; // in the cut
  const path = { project_id: p.id, clip_id: clip.id };
  const frame = frames.find((f) => f.clip_id === clip.clip_id);
  const changePrice = useQuery({ queryKey: ["clip-change-price", clip.id, clip.takes.length], retry: false, queryFn: async () => (await must(api.GET("/projects/{project_id}/clips/{clip_id}/change", { params: { path } }))).data!.credits });
  const stillPrice = useQuery({
    queryKey: ["still-change-price", frame?.id, clip.takes.length],
    enabled: !!frame?.file_id,
    retry: false,
    queryFn: async () => (await must(api.GET("/projects/{project_id}/storyboard/frames/{frame_id}/change", { params: { path: { project_id: p.id, frame_id: frame!.id } } }))).data!.credits,
  });
  const stillMakes = clip.takes.length ? "a new still and a new take" : "a new still"; // what Change the still… makes (S-gaps-08)
  const refresh = async () => {
    await refreshJobs(queryClient);
    await Promise.all([["project-clips", p.id], ["storyboard", p.id], ["run-progress", p.id], ["project-video", p.id], ["idea", p.id], ["project", p.id]].map((queryKey) => queryClient.invalidateQueries({ queryKey })));
  };
  // Read again however a press ends: one that stops midway (a still picked, its take refused) shows where it got to.
  const run = useMutation({ mutationFn: (f: () => Promise<unknown>) => f(), onSettled: refresh, onError: (e: Error) => toast(e.message, undefined, "error") });
  const go = (f: () => Promise<unknown>) => run.mutate(f);
  const take = (note = "") => go(() => must(api.POST("/projects/{project_id}/clips/{clip_id}/generate", { params: { path }, body: { note } })));
  // A person's pick is their OK; the cut that uses this clip is made again by itself, free (S-gaps-08 5, S7-05).
  const pickTake = (t: Take, keep = false) =>
    go(async () => {
      const route = keep ? "/projects/{project_id}/clips/{clip_id}/takes/{take_id}/keep" : "/projects/{project_id}/clips/{clip_id}/takes/{take_id}/use";
      await must(api.POST(route, { params: { path: { ...path, take_id: t.id } } }));
      const cut = queryClient.getQueryData(["project-video", p.id]);
      if (!cut) return;
      setRecut(true);
      try {
        const made = await api.POST("/projects/{project_id}/cut", { params: { path: { project_id: p.id } } }); // the next cut (#1299)
        if (made.data) queryClient.setQueryData(["project-cut", p.id], made.data);
        else toast(recutRefused(errorText(made.error)), undefined, "error"); // the pick stays; say why and what next (rule 22)
      } finally {
        setRecut(false);
      }
    });
  const send = (kind: "change" | "still" | "sound" | "prompt", text: string) =>
    go(async () => {
      if (kind === "change") await must(api.POST("/projects/{project_id}/clips/{clip_id}/change", { params: { path }, body: { note: text } }));
      if (kind === "still") await must(api.POST("/projects/{project_id}/storyboard/frames/{frame_id}/change", { params: { path: { project_id: p.id, frame_id: frame!.id } }, body: { note: text } }));
      if (kind === "sound") await must(api.POST("/projects/{project_id}/clips/{clip_id}/sound", { params: { path }, body: { asked: text } }));
      if (kind === "prompt") {
        await must(api.PUT("/projects/{project_id}/clips/{clip_id}", { params: { path }, body: { prompt: text, references: clip.references } }));
        toast(clip.takes.length ? "Prompt saved. Nothing was made: the take in the cut stays until you make another." : "Prompt saved. Nothing was made: a take being made keeps the prompt it started with, and reads out of date when it lands.");
      }
      setBox(null);
    });
  // An earlier still back in use (S-gaps-08 2): a take already made from it comes back with it (free); else, once the clip
  // has takes, a new take is made from it at its price; before any take it's just the still.
  const reuse = (fileId: number) => [...clip.takes].reverse().find((t) => t.from_still === fileId) ?? null;
  const pickStill = (fileId: number) =>
    go(async () => {
      const at = { project_id: p.id, frame_id: frame!.id };
      await must(api.POST("/projects/{project_id}/storyboard/frames/{frame_id}/pick", { params: { path: at }, body: { file_id: fileId } }));
      await must(api.POST("/projects/{project_id}/storyboard/frames/{frame_id}/approve", { params: { path: at } }));
      const again = reuse(fileId);
      if (again) await must(api.POST("/projects/{project_id}/clips/{clip_id}/takes/{take_id}/use", { params: { path: { ...path, take_id: again.id } } }));
      else if (clip.takes.length) await must(api.POST("/projects/{project_id}/clips/{clip_id}/generate", { params: { path }, body: { note: "" } }));
    });
  const picked = clip.takes.find((t) => t.id === clip.picked_take_id);
  const kind = row.broll ? "B-roll" : row.model;
  const takePrice = upTo(head, clip.take_credits);
  // Why a new take can't start yet, said under its press (rule 22), as the server would refuse it.
  const takeBlock = clip.stale ? "Rewrite its prompt first (above)." : blocking(clip.problems, clip.kept).length ? "Fix this clip’s prompt first (above, free)." : row.state === "making" || (clip.change as { status?: string } | null)?.status === "changing" ? "A take of this clip is being made." : null;
  const earlier = (frame?.earlier ?? []) as { file_id: number; made_at?: string }[];
  // Stills are numbered oldest first: the earlier ones, then the one in use.
  const stillNo = (file: number) => (file === frame?.file_id ? earlier.length + 1 : earlier.findIndex((e) => e.file_id === file) + 1 || null);
  const stillUse = (file: number) => (reuse(file) ? `free · take ${reuse(file)!.number} comes back` : clip.takes.length ? `${takePrice} · a new take` : "free");
  const size = phone ? "h-[171px] w-[96px]" : "h-[199px] w-[112px] @[760px]:h-[231px] @[760px]:w-[130px]";
  const tile = (key: string | number, media: ReactNode, title: string, line: string, after?: ReactNode, faded?: boolean) => (
    <li key={key} className={`flex shrink-0 flex-col gap-1 ${phone ? "w-[96px]" : "w-[112px] @[760px]:w-[130px]"} ${faded ? "opacity-60" : ""}`}>
      {media}
      <span className="text-sm font-semibold">{title}</span>
      {line && <span className="text-xs text-muted">{line}</span>}
      {after}
    </li>
  );
  const still = (file: number, selected: boolean) => (
    <span className={`relative block ${size} overflow-hidden rounded-md bg-black ${selected ? "outline-2 outline-offset-2 outline-accent" : ""}`}>
      <img src={fileUrl(file)} alt="" className="size-full object-cover" />
      <span className="absolute top-1.5 left-1.5 inline-flex items-center gap-1 rounded-[3px] bg-black/60 px-1.5 text-[11px] leading-4 font-semibold text-white">
        <ImageIcon size={11} strokeWidth={1.75} aria-hidden />
        Still
      </span>
    </span>
  );
  const kv: [string, ReactNode][] = [
    ["Model", clip.model?.name ?? picked?.model ?? row.model ?? ""],
    ...(clip.model?.why ? [["Why", <span className="text-muted">{clip.model.why}</span>] as [string, ReactNode]] : []),
    ...(row.words ? [[row.broll ? "Words over it" : "Words in this clip", row.broll ? `“${row.words}”` : row.said] as [string, ReactNode]] : []),
    ["Cost", `${spent(head, clip.spent)}${clip.stills || clip.takes.length ? ` (${[clip.stills && `${clip.stills} still${clip.stills === 1 ? "" : "s"}`, clip.takes.length && `${clip.takes.length} take${clip.takes.length === 1 ? "" : "s"}`].filter(Boolean).join(", ")})` : ""}`],
  ];
  const presses = (
    <div className={`flex gap-2 ${phone ? "flex-col" : "flex-wrap"}`}>
      {frame && !frame.file_id && <Priced wide={phone} icon={ImageIcon} label="Draw the still" price={upTo(head, frame.still_credits)} busy={run.isPending || frame.drawing} onClick={() => go(() => must(api.POST("/projects/{project_id}/storyboard/frames/{frame_id}/render", { params: { path: { project_id: p.id, frame_id: frame.id } } })))} />}
      {frame?.file_id && (
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <Priced wide={phone} icon={ImageIcon} label="Change the still…" price={stillPrice.isError ? undefined : stillPrice.data == null ? null : upTo(head, stillPrice.data)} disabled={stillPrice.isError} reason={stillPrice.isError ? stillPrice.error.message : null} onClick={() => setBox({ kind: "still", text: "" })} />
          <span className="text-xs text-muted">{stillMakes}</span>
        </span>
      )}
      {!clip.stale && <Priced wide={phone} icon={Pencil} label="Change this…" price={changePrice.isError ? undefined : changePrice.data == null ? null : upTo(head, changePrice.data)} disabled={changePrice.isError} reason={changePrice.isError ? changePrice.error.message : null} onClick={() => setBox({ kind: "change", text: "" })} />}
      <Priced wide={phone} icon={RefreshCw} label={clip.takes.length ? "Another take" : "Make the take"} price={takePrice} busy={run.isPending} disabled={!!takeBlock} reason={takeBlock} onClick={() => take()} />
      {picked && (clip.sound?.state === "none" || clip.sound?.state === "removed") && <Priced wide={phone} icon={Volume2} label="Add sound effects" price={upTo(head, clip.sound.credits)} onClick={() => setBox({ kind: "sound", text: "" })} />}
      {piece && !viewOnly && (
        <Button variant="secondary" icon={ArrowLeftRight} aria-expanded={swapping} className={phone ? "w-full justify-start" : ""} onClick={() => setSwapping(!swapping)}>
          Swap B-roll <span className="font-normal text-muted">· free</span>
        </Button>
      )}
      {picked && clip.sound?.state === "ready" && clip.sound.asked && <p className="text-xs text-muted">Sound effects: {clip.sound.asked}</p>}{/* why they're there: a person's words, or the style guide's the director named */}
      {picked && clip.sound?.state === "ready" && (
        <Button variant="secondary" icon={Volume2} className={phone ? "w-full justify-start" : ""} onClick={() => go(() => must(api.DELETE("/projects/{project_id}/clips/{clip_id}/sound", { params: { path } })))}>
          Remove the sound effects
        </Button>
      )}
      {picked && !phone && (
        <a className={`${buttonClass("secondary")} gap-2`} href={fileUrl(picked.file_id)} download={mp4(`${p.name} clip ${row.number}`)}>
          <Download size={20} strokeWidth={1.75} aria-hidden />
          Download
        </a>
      )}
    </div>
  );
  const swapBox = swapping && piece && <SwapBroll projectId={p.id} piece={piece.id} onDone={() => setSwapping(false)} />;
  const boxes = { change: ["Change this…", "What should change in this clip?"], still: ["Change the still…", "What should change in the still?"], sound: ["Add sound effects", "Slight footsteps, wind…"], prompt: ["The director’s prompt", ""] } as const;
  const boxPrice = box?.kind === "change" ? changePrice.data : box?.kind === "still" ? stillPrice.data : box?.kind === "sound" ? clip.sound?.credits : undefined;
  return (
    <section aria-label={`Clip ${row.number}`} className="flex flex-col gap-6">
      {!phone && (
        <div className="flex flex-wrap items-baseline gap-x-2">
          <h3 className="text-lg font-semibold">Clip {row.number}</h3>
          <span className="text-sm text-muted">{[`Scene ${scene.id}`, scene.name, `${row.seconds} s`, kind].filter(Boolean).join(" · ")}</span>
          <span className="flex-1" />
          <RowStatus r={row} />
        </div>
      )}
      <Found clip={clip} head={head} phone={phone} busy={run.isPending} onRemake={take} onKeep={(t) => pickTake(t, true)} />
      {row.state === "failed" && (
        <div className="flex flex-col items-start gap-2 rounded-lg bg-danger-soft px-3 py-2.5 text-sm text-danger">
          <span>{row.note || "This take couldn’t be made. Nothing was charged."}</span>
          <Priced icon={RefreshCw} label="Try again" price={takePrice} busy={run.isPending} onClick={() => take()} />
        </div>
      )}
      {row.state === "waiting" && row.note && (
        <div className="flex flex-col items-start gap-2 rounded-lg bg-warning-soft px-3 py-2.5 text-sm text-warning">
          <span>{row.note}</span>
          {/cast and places OK/.test(row.note) && (
            <Button variant="secondary" onClick={onCast}>
              Open Cast
            </Button>
          )}
        </div>
      )}
      <Problems p={p} clip={clip} onDone={refresh} />
      {clip.take_stale && clip.picked_take_id != null && !clip.stale && (
        // Reed, rule 21: an edited prompt never buys a take by itself. The take in the cut stays; this says so, with the price.
        <div className="flex flex-col items-start gap-2 rounded-lg bg-warning-soft px-3 py-2.5 text-sm text-warning">
          <span>Out of date: the take in the cut was made before the prompt or its pictures changed. It stays in the cut, and every take is kept.</span>
          {!viewOnly && (
            <Button variant="secondary" busy={run.isPending} disabled={!!takeBlock} reason={takeBlock} onClick={() => take()}>
              Another take <span className="font-normal text-muted">· {takePrice}</span>
            </Button>
          )}
        </div>
      )}
      <ChangeLine clip={clip} busy={run.isPending} onAgain={(note) => (note ? send("change", note) : take())} />
      {clip.stale && <Rewrite p={p} head={head} clip={clip} onDone={refresh} />}
      {recut && (
        <p role="status" className="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2.5 text-sm">
          <LoaderCircle size={14} strokeWidth={1.75} aria-hidden className="animate-spin motion-reduce:animate-none" />
          Making the cut again with your change · free. The cut before keeps playing until then.
        </p>
      )}
      <ul aria-label="Stills and takes" className="flex max-w-full min-w-0 items-start gap-3 overflow-x-auto pb-1">
        {frame?.file_id && tile(`still-${frame.file_id}`, still(frame.file_id, false), "Still · in use", earlier.length ? `Still ${earlier.length + 1}` : "")}
        {frame &&
          [...earlier].reverse().map((e, i) =>
            tile(
              `still-${e.file_id}`,
              still(e.file_id, false),
              `Still ${earlier.length - i}`,
              "Replaced",
              !viewOnly && (
                <button type="button" onClick={() => pickStill(e.file_id)} className="text-left text-xs text-accent-text hover:underline max-lg:min-h-11">
                  Use this still · {stillUse(e.file_id)}
                </button>
              ),
              true,
            ),
          )}
        {(frame?.file_id || earlier.length > 0) && clip.takes.length > 0 && <li aria-hidden className="w-px self-stretch bg-border" />}
        {[...clip.takes]
          .sort((a, b) => a.number - b.number)
          .map((t) => {
            const inCut = t.id === clip.picked_take_id;
            return tile(
              t.id,
              <video
                src={fileUrl(t.file_id)}
                controls
                preload="metadata"
                aria-label={`Take ${t.number}`}
                onPlay={() => row.changed && !row.watched && inCut && void markWatched(p.id, [t.id])}
                className={`${size} rounded-md bg-black object-cover ${inCut ? "outline-2 outline-offset-2 outline-accent" : ""}`}
              />,
              `Take ${t.number}${inCut ? " · in the cut" : ""}`,
              takeLine(t, inCut, clip.takes, stillNo),
              !inCut &&
                !viewOnly &&
                (phone ? (
                  <button type="button" onClick={() => pickTake(t)} className="min-h-11 text-left text-xs text-accent-text hover:underline">
                    Use this take · free
                  </button>
                ) : (
                  <Button variant="secondary" dense busy={run.isPending} onClick={() => pickTake(t)}>
                    Use this take <span className="font-normal text-muted">· free</span>
                  </Button>
                )),
            );
          })}
      </ul>
      {frame?.file_id && <StillReview p={p} check={frame.check as Check} price={stillPrice.isError ? undefined : stillPrice.data == null ? null : upTo(head, stillPrice.data)} blocked={stillPrice.isError ? stillPrice.error.message : null} makes={stillMakes} onChange={(note) => setBox({ kind: "still", text: note })} onDone={refresh} />}
      <Review p={p} head={head} clip={clip} fixPrice={changePrice.data ?? null} fixError={changePrice.isError ? changePrice.error.message : null} onNote={(note) => setBox({ kind: "change", text: note })} onTake={() => take()} takeBlock={takeBlock} onDone={refresh} />
      <Inserts p={p} clip={clip} onDone={refresh} />
      <WhatChanged p={p} clip={clip} frame={frame} stillUse={stillUse} onStill={pickStill} onDone={refresh} />
      <History p={p} head={head} clip={clip} onDone={refresh} />
      {box ? (
        <form className="flex flex-col gap-2" onSubmit={(e) => (e.preventDefault(), box.text.trim() && send(box.kind, box.text.trim()))}>
          {box.kind === "still" && (
            <p className="text-xs text-muted">
              {clip.takes.length ? "A new still, then a new take of this clip from it. " : "A new still; the take is made from it later. "}
              How a character or place looks is changed in Cast, never here.{" "}
              <button type="button" onClick={onCast} className="text-accent-text hover:underline max-lg:min-h-11">
                Open Cast
              </button>
            </p>
          )}
          <TextArea autoFocus label={boxes[box.kind][0]} rows={box.kind === "prompt" ? 6 : 2} maxLength={box.kind === "prompt" ? 8000 : box.kind === "sound" ? 300 : undefined} placeholder={boxes[box.kind][1]} value={box.text} onChange={(e) => setBox({ ...box, text: e.target.value })} />
          <div className="flex flex-wrap gap-2">
            <Priced type="submit" label={box.kind === "prompt" ? "Save the prompt" : box.kind === "sound" ? "Add" : "Change it"} price={boxPrice == null ? undefined : upTo(head, boxPrice)} busy={run.isPending} disabled={!box.text.trim()} />
            <Button variant="ghost" onClick={() => setBox(null)}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <>
          {!phone && (
            <dl className="grid grid-cols-[112px_1fr] gap-x-4 gap-y-2.5 border-t border-border pt-5 text-sm">
              {kv.map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-muted">{k}</dt>
                  <dd className="whitespace-pre-line">{v}</dd>
                </div>
              ))}
            </dl>
          )}
          {!phone && (
            <Prompt text={clip.prompt} onEdit={viewOnly ? undefined : () => setBox({ kind: "prompt", text: clip.prompt })} />
          )}
          {presses}
          {swapBox}
        </>
      )}
    </section>
  );
}

/** The director's prompt, in full: a long one opens at its first lines with the rest a press away (it is always there to
 *  read and change, rule 21; it just doesn't push the clip's own picture and review off the screen). */
function Prompt({ text, onEdit }: { text: string; onEdit?: () => void }) {
  const [all, setAll] = useState(false);
  const lines = text.split("\n").length;
  const long = lines > 8;
  return (
    <div className="flex flex-col gap-2 border-t border-border pt-5">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold">The director’s prompt</h4>
        {onEdit && (
          <Button variant="ghost" dense icon={Pencil} onClick={onEdit}>
            Edit
          </Button>
        )}
      </div>
      <div className="relative">
        <p className={`overflow-hidden whitespace-pre-wrap rounded-lg border border-border bg-surface-2/60 px-3.5 py-3 font-mono text-xs leading-[1.6] text-text/80 ${long && !all ? "max-h-44" : ""}`}>{text}</p>
        {long && !all && <span aria-hidden className="pointer-events-none absolute inset-x-px bottom-px h-16 rounded-b-lg bg-linear-to-t from-surface-2 to-transparent" />}
      </div>
      {long && (
        <button type="button" aria-expanded={all} onClick={() => setAll(!all)} className="self-start text-sm font-medium text-accent-text underline-offset-2 hover:underline max-lg:min-h-control">
          {all ? "Show less" : `Show all ${lines} lines`}
        </button>
      )}
    </div>
  );
}

/** Why a pick's cut didn't start, said with what happens to the pick: a cut already being made takes it next. */
export function recutRefused(why: string): string {
  const making = /^Cut (\d+) is being made/.exec(why);
  return making ? `Cut ${making[1]} is being made; your pick goes in the next cut. Make it from the Cut tab once Cut ${making[1]} is ready.` : `Your pick is kept, but the cut wasn’t made: ${why}`;
}
