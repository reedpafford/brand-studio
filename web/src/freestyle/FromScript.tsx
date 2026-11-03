import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Button, Skeleton } from "../components";
import { useFolders } from "../folders/Projects";
import { lookName, useLooks } from "../scripts/Looks";
import { letterOf, useDebounced } from "../scripts/status";
import { useScript, type Script } from "../scripts/useScript";
import { ActionBar } from "../shell/ActionBar";
import { useBrands } from "../shell/useBrands";
import { useRail } from "../useMedia";
import { Pick, SendPress, sendKey, shapeOptions } from "./Composer";
import { SendError, useEstimate, useFreestyleActions, type Freestyle, type Shape } from "./useFreestyle";

type Row = Script["versions"][number];
/** "0:32" */
export const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
/** A version that can become a video: one with its words finished (any of them; publishing isn't needed, #1190). */
export const finished = (v: { status: string }) => v.status !== "draft";

/** Making a video from one script's version (E_PickInComposer, E_ScriptMakeVideo): the version and shape picked, the
 *  send's "up to" price, the send itself, and a version that already has a video (the Producer: never a dead end; Open it,
 *  or Make another through the usual holds). */
export function useMakeFromScript(scriptId: number | null, onCreated: (fs: Freestyle) => void, start?: number) {
  const script = useScript(scriptId ?? 0);
  const s = scriptId ? script.data : undefined;
  const versions = (s?.versions ?? []).filter(finished);
  const [picked, setPicked] = useState<number | null>(start ?? null);
  const [shape, setShape] = useState<Shape>("9:16");
  const version = versions.find((v) => v.slot === picked) ?? versions[0];
  const source = s && version ? { script_id: s.id, slot: version.slot, shape } : null;
  const estimate = useEstimate(source);
  const create = useFreestyleActions(null).create;
  const refused = create.error instanceof SendError ? create.error.hasVideo : undefined;
  const video = refused?.project_id ?? version?.project_id ?? null;
  const send = (another = false) => source && !create.isPending && create.mutate({ ...source, ...(another ? { make_another: true } : {}) }, { onSuccess: onCreated });
  const pick = (slot: number) => {
    setPicked(slot);
    create.reset();
  };
  return { script: s, loading: !!scriptId && script.isPending, versions, version, pick, shape, setShape: (x: Shape) => (setShape(x), create.reset()), price: refused?.up_to ?? estimate.data, create, video, send, error: create.isError && !refused ? create.error.message : null };
}
export type Making = ReturnType<typeof useMakeFromScript>;

/** The picked version already has a video: open it, or make another (its own price, the usual holds). */
export function HasVideo({ m, brandId }: { m: Making; brandId: number }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3" role="status">
      <p className="text-sm">
        This version already has a video ·{" "}
        <Link to={`/b/${brandId}/videos/${m.video}`} className="text-accent-text underline-offset-2 hover:underline">
          Open it
        </Link>
      </p>
      <Button variant="secondary" dense busy={m.create.isPending} price={m.price} charge="estimate" onClick={() => m.send(true)}>
        Make another
      </Button>
    </div>
  );
}

/** The scripts in this brand with a version ready to make, by title (an editor sees the published ones). */
function useReadyScripts(brandId: number, owner: boolean, q: string) {
  return useQuery({
    queryKey: ["scripts", "ready-to-make", brandId, owner, q],
    queryFn: async () => {
      const { data } = await api.GET("/scripts", { params: { query: { brand_id: brandId, ...(owner ? {} : { status: "published" }), ...(q ? { q } : {}), sort: "title", limit: 50 } } });
      return (data ?? []).filter((r) => r.kind === "story" && r.versions.some(finished)); // Dialogue is the director's kind for now
    },
  });
}

const span = (vs: { seconds: number }[]) => {
  const s = vs.map((v) => v.seconds).filter((n) => n > 0);
  if (!s.length) return null;
  const [lo, hi] = [Math.min(...s), Math.max(...s)];
  return lo === hi ? mmss(lo) : `${mmss(lo)}–${mmss(hi)}`;
};

/** New video › From a script (E_PickInComposer; E_PhonePick at 390): find a script on the left, pick its version on the
 *  right; its words are read-only and its type, style and brand are locked chips. Shape is still yours. */
export function FromScript({ brandId, owner, onCreated }: { brandId: number; owner: boolean; onCreated: (fs: Freestyle) => void }) {
  const rail = useRail();
  const [text, setText] = useState("");
  const q = useDebounced(text.trim());
  const rows = useReadyScripts(brandId, owner, q);
  const folders = useFolders(brandId).data;
  const looks = useLooks().data;
  const [picked, setPicked] = useState<number | null>(null);
  const m = useMakeFromScript(picked, onCreated);
  const list = rows.data ?? [];
  const at = list.findIndex((r) => r.id === picked);
  const choose = setPicked;
  const press = <SendPress owner={owner} price={m.video ? undefined : m.price} busy={m.create.isPending} disabled={!m.version || !!m.video} wide={!rail} onClick={() => m.send()} />;
  const note = owner ? "The director plans, casts, makes and cuts it. You can stop it any time." : "The director plans, casts, makes and cuts it. The owner approves it before anything is spent.";
  return (
    <div className="flex min-h-0 flex-1 flex-col lg:flex-row" onKeyDown={sendKey(() => !m.video && m.send())}>
      <section aria-label="Scripts ready to make" className="flex flex-col gap-3 p-4 lg:w-[360px] lg:shrink-0 lg:border-r lg:border-border">
        <label htmlFor="find-script" className={rail ? "text-sm text-muted" : "sr-only"}>
          Find a script ready to make
        </label>
        <input id="find-script" type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder={rail ? undefined : "Find a script ready to make"} className="min-h-control w-full rounded-md border border-border-strong bg-surface px-3 text-base outline-none placeholder:text-muted focus:border-focus" onKeyDown={(e) => {
          if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
          e.preventDefault();
          const next = list[Math.min(list.length - 1, Math.max(0, at + (e.key === "ArrowDown" ? 1 : -1)))];
          if (next) setPicked(next.id);
        }} />
        {rows.isPending && <Skeleton className="h-14" />}
        <ul role="listbox" aria-label="Scripts" className="-mx-4 flex flex-col lg:mx-0 lg:gap-1">
          {list.map((r) => {
            const on = r.id === picked;
            const ready = r.versions.filter(finished);
            const where = folders?.find((f) => f.id === r.folder_id)?.name ?? "No project";
            const meta = [on && m.version && !rail ? `Version ${letterOf(m.version.slot)}` : `${ready.length} version${ready.length === 1 ? "" : "s"}`, span(on && m.version && !rail ? [m.version] : ready), lookName(looks, r.look)].filter(Boolean).join(" · ");
            return (
              <li key={r.id} role="option" aria-selected={on} tabIndex={0} onClick={() => choose(r.id)} onKeyDown={(e) => e.key === "Enter" && !(e.metaKey || e.ctrlKey) && choose(r.id)} className={`flex min-h-14 cursor-pointer items-center gap-3 px-4 py-2.5 lg:rounded-md lg:border lg:px-3 ${on ? "bg-surface-2 shadow-[inset_3px_0_0_var(--accent)] lg:border-accent lg:bg-surface lg:shadow-none" : "border-transparent hover:bg-surface-2"} border-b border-border lg:border-b`}>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{r.title}</p>
                  <p className="truncate text-sm text-muted">{meta}</p>
                </div>
                {/* A phone picks the version right in the row (E_PhonePick): no sheet over the press. */}
                {!rail && on && m.versions.length > 1 && m.version ? (
                  <span onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
                    <Versions versions={m.versions} slot={m.version.slot} onPick={m.pick} letters />
                  </span>
                ) : (
                  <span className="shrink-0 text-sm text-muted">{rail ? where : ready.map((v) => letterOf(v.slot)).join(" ")}</span>
                )}
              </li>
            );
          })}
        </ul>
        {rows.data && list.length === 0 && <p className="text-sm text-muted">{q ? "No script matches that." : "Nothing ready to make yet."}</p>}
        <p className="text-sm text-muted">{rail ? "Only scripts with a finished version show here. Drafts appear once a version is ready." : owner ? "You can stop it any time." : "The owner approves it before anything is spent."}</p>
      </section>
      {rail ? (
        <section aria-label="The script" className="min-w-0 flex-1 px-8 py-6">
          {m.loading ? <Skeleton className="h-40" /> : m.script && m.version ? <Picked m={m} brandId={brandId} note={note} press={press} /> : (
            <div className="flex items-center justify-between gap-4 border-t border-border pt-4">
              <p className="text-sm text-muted">Pick a script on the left. Its words, type, style and brand come with it.</p>
              <Button disabled kbd="⌘↵">Pick a script</Button>
            </div>
          )}
        </section>
      ) : (
        <>
          <div className="space-y-3 px-4 empty:hidden">
            {m.video && <HasVideo m={m} brandId={brandId} />}
            {m.error && <p role="alert" className="text-sm text-danger">{m.error}</p>}
          </div>
          <ActionBar phone>{m.version ? press : <Button disabled>Pick a script</Button>}</ActionBar>
        </>
      )}
    </div>
  );
}

/** The picked script: its versions, read-only words, the locked chips with Shape, and (desktop) the note and the press. */
function Picked({ m, brandId, note, press }: { m: Making; brandId: number; note?: string; press?: ReactNode }) {
  const looks = useLooks().data;
  const brands = useBrands().data;
  const s = m.script!;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="type-section">{s.title}</h2>
        <Versions versions={m.versions} slot={m.version!.slot} onPick={m.pick} />
      </div>
      <p className="whitespace-pre-line break-words rounded-lg border border-border bg-surface p-4 font-script text-sm leading-[1.6] text-muted">{m.version!.text}</p>
      <div className="flex flex-wrap gap-1.5">
        <Pick locked label="Type" value="Dialogue" />
        <Pick locked label="Style" value={lookName(looks, s.look)} />
        <Pick locked label="Brand" value={brands?.find((b) => b.id === s.brand_id)?.name ?? ""} />
        <Pick label="Shape" value={m.shape} options={shapeOptions} onPick={m.setShape} />
      </div>
      <p className="text-sm text-muted">Type, style and brand come from the script. Change them on the script itself.</p>
      {m.video ? <HasVideo m={m} brandId={brandId} /> : press && (
        <div className="flex items-center justify-between gap-6 border-t border-border pt-4">
          <p className="min-w-0 flex-1 text-sm text-muted">{note}</p>
          <div className="shrink-0 whitespace-nowrap">{press}</div>
        </div>
      )}
      {m.error && <p role="alert" className="text-sm text-danger">{m.error}</p>}
    </div>
  );
}

/** Version A · 0:32 | B · 0:35 | C · 0:38, as one segmented control. */
/** `letters`: just A B C, each a 44 px target (a phone's row, E_PhonePick). */
export function Versions({ versions, slot, onPick, letters }: { versions: Row[]; slot: number; onPick: (slot: number) => void; letters?: boolean }) {
  return (
    <div role="radiogroup" aria-label="Version" className="inline-flex rounded-md border border-border p-0.5">
      {versions.map((v) => (
        <button key={v.slot} type="button" role="radio" aria-checked={v.slot === slot} onClick={() => onPick(v.slot)} className={`min-h-control rounded-sm text-sm tabular-nums lg:min-h-control-dense ${letters ? "min-w-11 px-2" : "px-3"} ${v.slot === slot ? "bg-surface-2 font-medium text-text" : "text-muted hover:text-text"}`}>
          {letterOf(v.slot)}
          {!letters && v.seconds > 0 && ` · ${mmss(v.seconds)}`}
        </button>
      ))}
    </div>
  );
}
