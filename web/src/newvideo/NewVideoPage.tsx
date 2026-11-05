import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUp, ChevronRight, CircleHelp, Clock, X } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useMe } from "../auth/useMe";
import { Button, creditsLabel, wholeCredits } from "../components";
import { useFolders } from "../folders/Projects";
import { SHAPES, sentTo } from "../freestyle/useFreestyle";
import { useLooks } from "../scripts/Looks";
import { counts } from "../scripts/ScriptFrame";
import { useFormats } from "../scripts/useFormats";
import { ActionBar } from "../shell/ActionBar";
import { useBrands } from "../shell/useBrands";
import { useRail } from "../useMedia";
import { Attach, Attached, useAttachments } from "./Attach";
import { BrollPicker, FormatCards, StyleCards, type Look } from "./Cards";
import { CastIcon, Chip, FolderIcon } from "./Chips";
import { Reel } from "./Reel";
import { SavedScripts } from "./SavedScripts";
import { useEstimate, useSend, usd, type Estimate, type Send } from "./useNewVideo";

export type Tab = "paste" | "script" | "reel";
const TABS: { id: Tab; name: string; phone: string }[] = [
  { id: "paste", name: "Paste or describe", phone: "Paste" },
  { id: "script", name: "From a saved script", phone: "Saved script" },
  { id: "reel", name: "Use a reel", phone: "Use a reel" },
];
const PLACEHOLDER = "Paste a script, or describe the video. “A Dr. Pickle rant about beer bellies, under a minute, ending on the capsule.”";
export const box = "rounded-[14px] border border-border-strong bg-surface shadow-[0_1px_2px_rgb(28_27_25/0.06),0_2px_8px_rgb(28_27_25/0.04)]";
export const row = "flex flex-wrap items-center gap-2 border-t border-border px-3 pb-3 pt-2";

/** The press's label (rules 34, 36): the owner sees the most in dollars, an editor in credits; a held send goes to the owner. */
export function pressWords(owner: boolean, est: Estimate | undefined, go = "Make it") {
  const held = !owner && !!est?.held;
  const most = !est ? "" : owner && est.usd != null ? `up to ${usd(est.usd)}` : `up to ${creditsLabel(est.credits)}`;
  return { label: held ? "Send to the owner" : go, most, held };
}

/** The line under the box: what the price means, or why it waits and that no generation starts until then (S2-02, -04,
 *  -05; Reed, 4 Nov: never "nothing spent" before Make it, as the plan is a small spend). */
export function Under({ owner, est, phone }: { owner: boolean; est: Estimate | undefined; phone?: boolean }) {
  if (!est) return null;
  if (!owner && est.held) {
    const past = est.budget != null ? `Up to ${wholeCredits(est.credits)} credits is past this video’s budget of ${wholeCredits(est.budget)}, so it goes to the owner first. No generation starts while it waits.` : "The owner approves before any generation starts. You’ll see it in My requests.";
    return (
      <span className="flex items-center gap-1 text-xs text-warning">
        <Clock size={12} aria-hidden /> {past}
      </span>
    );
  }
  if (phone) return <span className="text-xs text-muted">The most it can charge, redos included</span>;
  return <span className="text-xs text-muted">{owner ? "Most it can charge, including redos and the director’s time. Usually less." : "Inside this video’s budget, so it starts straight away."}</span>;
}

/** The main press, with the most it can charge after a dot ("Make it · up to $16.86"). */
export function Press({ owner, est, busy, disabled, onClick, go, wide }: { owner: boolean; est: Estimate | undefined; busy: boolean; disabled: boolean; onClick: () => void; go?: string; wide?: boolean }) {
  const w = pressWords(owner, est, go);
  return (
    <Button busy={busy} disabled={disabled} icon={w.held ? ArrowUp : undefined} onClick={onClick} className={`${wide ? "w-full" : "shrink-0 whitespace-nowrap"} lg:min-h-9 lg:px-3.5`}>
      {w.label}
      {!disabled && w.most && (
        <>
          {" "}
          <span className="opacity-85">· {w.most}</span>
        </>
      )}
    </Button>
  );
}

function useCharacters(brandId: number) {
  return useQuery({
    queryKey: ["library", "character", brandId, false],
    queryFn: async () => (await api.GET("/library/{kind}", { params: { path: { kind: "character" }, query: { brand_id: brandId } } })).data ?? [],
    select: (rows) => rows.filter((c) => !c.owner_project_id && !c.owner_script_id),
  });
}

/** New video (v6 S2-01..S2-07, P-03): one message box that becomes the video's chat, with format and style picture cards
 *  that play their samples and name their B-roll look. The brand's saved cast is filled in; the idea lands in the open
 *  folder (?folder=) or Unsorted; the press says the most the run can charge, and Make it opens the video. */
export function NewVideoPage() {
  const brandId = Number(useParams().brandId);
  const [params, setParams] = useSearchParams();
  const tab: Tab = params.get("from") === "script" ? "script" : params.get("from") === "reel" ? "reel" : "paste";
  const setTab = (t: Tab) => setParams((p) => (t === "paste" ? p.delete("from") : p.set("from", t), p), { replace: true });
  const rail = useRail();
  const navigate = useNavigate();
  const me = useMe().data;
  const owner = me?.role === "owner";
  const brand = useBrands().data?.find((b) => b.id === brandId);
  const formats = useFormats().data ?? [];
  const looks = (useLooks().data ?? []) as Look[];
  const folders = useFolders(brandId).data ?? [];
  const characters = useCharacters(brandId).data ?? [];
  const opened = Number(params.get("folder")) || null;
  const [picked, setPicked] = useState<Partial<Send> & { folder?: number | null; cast?: number[] }>({});
  const [text, setText] = useState("");
  const [brolling, setBrolling] = useState(false);
  // From a saved script: the cards show the script's own format and style, locked (its words, format and style are set).
  const [locked, setLocked] = useState<{ type: string; look: string } | null>(null);
  const fixed = tab === "script" ? locked : null;
  const files = useAttachments();
  const firstOn = <T extends { on: boolean; off?: string | null }>(xs: T[]) => xs.find((x) => x.on && !x.off);
  const format = formats.find((f) => f.id === (fixed?.type ?? picked.type)) ?? firstOn(formats);
  const look = looks.find((l) => l.id === (fixed?.look ?? picked.look)) ?? firstOn(looks); // brands keep no default style (S-gaps-05 L1)
  const folder = picked.folder !== undefined ? picked.folder : folders.some((f) => f.id === opened) ? opened : null;
  const cast = picked.cast ?? []; // nobody until picked: brands keep no default cast
  const broll = format?.host ? (picked.broll_look ?? null) : null;
  const settings = { type: format?.id ?? "dialogue", look: look?.id ?? "", shape: picked.shape ?? "9:16", brand_id: brandId, folder_id: folder, broll_look: broll };
  const send: Send = { ...settings, text: text.trim(), cast_ids: cast, attachments: files.ids };
  const est = useEstimate(tab === "paste" && text.trim() && look ? send : null).data;
  const pickFormat = (type: string) => !fixed && setPicked({ ...picked, type });
  const pickLook = (l: string) => !fixed && setPicked({ ...picked, look: l, broll_look: null });
  const sent = useSend((fs) => navigate(sentTo(fs, owner, brandId)));
  const empty = !text.trim() || !look || !format || files.busy;
  const go = () => !empty && !sent.isPending && sent.mutate(send);
  const folderName = folders.find((f) => f.id === folder)?.name ?? "Unsorted";

  const chips = (all: boolean) => (
    <>
      {all && <Chip label="Format" value={settings.type} options={formats.map((f) => ({ id: f.id, name: f.name, off: f.off ? "Off" : undefined }))} onPick={pickFormat} />}
      {all && <Chip label="Style" value={settings.look} options={looks.map((l) => ({ id: l.id, name: l.name, off: l.on ? undefined : "Off" }))} onPick={pickLook} />}
      <Chip label="Cast" icon={CastIcon} many empty="Nobody" value={cast} options={characters.map((c) => ({ id: c.id, name: c.name }))} onPick={(id) => setPicked({ ...picked, cast: cast.includes(id) ? cast.filter((x) => x !== id) : [...cast, id] })} />
      <Chip label="Shape" value={settings.shape} options={SHAPES.map((s) => ({ id: s, name: s }))} onPick={(shape) => setPicked({ ...picked, shape })} />
      <Chip label="Folder" icon={FolderIcon} value={folder ?? 0} options={[...folders.map((f) => ({ id: f.id, name: f.name })), { id: 0, name: "Unsorted" }]} onPick={(f) => setPicked({ ...picked, folder: f || null })} />
    </>
  );
  const seg = (
    <div role="tablist" aria-label="Start from" className="inline-flex gap-0.5 rounded-md bg-surface-2 p-0.5">
      {TABS.map((t) => (
        <button key={t.id} type="button" role="tab" aria-selected={t.id === tab} onClick={() => setTab(t.id)} className={`h-7 whitespace-nowrap rounded-[5px] px-3 text-sm font-medium ${t.id === tab ? "bg-surface text-text shadow-[0_1px_2px_rgb(28_27_25/0.06)]" : "text-muted hover:text-text"}`}>
          {rail ? t.name : t.phone}
        </button>
      ))}
    </div>
  );
  const error = sent.isError && <p role="alert" className="text-sm text-danger">{sent.error.message}</p>;
  const paste = (
    <>
      <div className={box}>
        {rail && <div className="px-3 pt-2.5">{seg}</div>}
        <div className="px-4 pb-2 pt-3.5">
          <Words text={text} setText={setText} go={go} rail={rail} />
          <Attached files={files} />
        </div>
        {rail && (
          <div className={row}>
            <Attach files={files} onReel={() => setTab("reel")} />
            {chips(true)}
            <span className="flex-1" />
            <Press owner={owner} est={est} busy={sent.isPending} disabled={empty} onClick={go} />
          </div>
        )}
      </div>
      {rail && <div className="flex min-h-6 items-center px-1 py-1.5">{!empty && <Under owner={owner} est={est} />}</div>}
    </>
  );
  const body =
    tab === "script" ? <SavedScripts brandId={brandId} brandName={brand?.name} owner={owner} folder={folder} broll={broll} seg={seg} rail={rail} onScript={setLocked} /> : tab === "reel" ? <Reel brandId={brandId} owner={owner} folder={folder} seg={seg} rail={rail} format={settings.type} formatName={format?.name} look={look} broll={broll} /> : paste;
  const picker = (
    <>
      <section aria-label="Format" className={`flex flex-col gap-2 ${rail ? "" : "pt-1"}`}>
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Format</h2>
          {rail && <span className="text-xs text-muted">{fixed ? "From the script" : "How the words are delivered"}</span>}
        </div>
        <FormatCards formats={formats} value={settings.type} onPick={pickFormat} small={!rail} locked={!!fixed} />
      </section>
      <section aria-label="Style" className="relative flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Style</h2>
          {rail && <span className="text-xs text-muted">{fixed ? "From the script. The B-roll follows the style." : "How it looks and how the camera moves. The B-roll follows the style."}</span>}
          <span className="flex-1" />
          {rail && format?.host && look && (
            <button type="button" aria-expanded={brolling} onClick={() => setBrolling(!brolling)} className="text-xs font-medium text-accent-text hover:underline">
              Change B-roll look…
            </button>
          )}
          {brolling && look && <BrollPicker looks={looks} style={look} value={broll} onPick={(b) => (setPicked({ ...picked, broll_look: b }), setBrolling(false))} onClose={() => setBrolling(false)} />}
        </div>
        <StyleCards looks={looks} value={settings.look} onPick={pickLook} small={!rail} locked={!!fixed} />
      </section>
    </>
  );
  const offNote = <OffNote formats={formats} looks={looks} owner={owner} />;
  if (!rail)
    return (
      <main className="flex min-h-[calc(100dvh-var(--tabbar-h))] flex-col">
        <header className="flex items-center gap-2 border-b border-border px-2 py-2">
          <Link to={`/b/${brandId}/videos`} aria-label="Close" className="grid size-control place-items-center rounded-md text-muted">
            <X size={20} aria-hidden />
          </Link>
          <div className="min-w-0">
            <h1 className="text-md font-semibold">New video</h1>
            <p className="truncate text-xs text-muted">{[brand?.name, folderName].filter(Boolean).join(" · ")}</p>
          </div>
        </header>
        <div className="flex flex-col gap-4 p-3.5">
          <div className="self-start">{seg}</div>
          {tab === "paste" ? (
            <div className="rounded-xl border border-border-strong bg-surface p-3">
              <Words text={text} setText={setText} go={go} rail={false} />
              <Attached files={files} />
            </div>
          ) : (
            body
          )}
          {picker}
          {tab === "paste" && <div className="flex flex-wrap gap-2">{chips(false)}</div>}
          {offNote}
          {error}
        </div>
        {tab === "paste" && (
          <ActionBar phone>
            <div className="flex flex-col gap-1">
              <Press owner={owner} est={est} busy={sent.isPending} disabled={empty} onClick={go} wide />
              {!empty && <Under owner={owner} est={est} phone />}
            </div>
          </ActionBar>
        )}
      </main>
    );
  return (
    <main className="flex min-h-screen flex-col">
      <header className="flex h-[52px] items-center border-b border-border px-5 text-sm text-muted">
        {brand?.name}
        <ChevronRight size={12} aria-hidden className="mx-1.5" />
        <span className="font-semibold text-text">New video</span>
      </header>
      <div className="flex justify-center px-8 py-5">
        <div className="flex w-full max-w-[1112px] flex-col gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="type-page text-2xl">What should the director make?</h1>
            <p className="text-md text-muted">Paste a script or describe it. The director plans it, asks what it can’t decide, and makes it in a chat with you.</p>
          </div>
          <div>
            {body}
            {error}
          </div>
          {picker}
          {offNote}
        </div>
      </div>
    </main>
  );
}

/** The words box: the script font as you type; away from it, a long script folds to four lines and its length (S2-02). */
function Words({ text, setText, go, rail }: { text: string; setText: (t: string) => void; go: () => void; rail: boolean }) {
  const [editing, setEditing] = useState(false);
  const lines = text.split("\n").filter((l) => l.trim());
  const c = counts(text);
  const fold = !editing && lines.length > (rail ? 5 : 3);
  if (fold)
    return (
      <button type="button" onClick={() => setEditing(true)} className="block min-h-24 w-full text-left font-script text-sm leading-[1.6]">
        <span className="sr-only">Edit the words: </span>
        {lines.slice(0, rail ? 4 : 2).map((l, i) => (
          <span key={i} className="block">{l}</span>
        ))}
        <span className="block text-muted">{`+ ${lines.length - (rail ? 4 : 2)} more lines${rail ? ` · ${c.words} words · about ${c.seconds} s` : ""}`}</span>
      </button>
    );
  return (
    <>
      <label htmlFor="new-video-words" className="sr-only">
        Paste a script, or describe the video
      </label>
      <textarea
        id="new-video-words"
        autoFocus={rail || editing}
        rows={rail ? 4 : 3}
        maxLength={5000}
        value={text}
        placeholder={PLACEHOLDER}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => setEditing(false)}
        onKeyDown={(e) => e.key === "Enter" && (e.metaKey || e.ctrlKey) && !e.nativeEvent.isComposing && (e.preventDefault(), go())}
        className="field-sizing-content min-h-24 w-full resize-none bg-transparent font-script text-sm leading-[1.6] text-text outline-none! placeholder:font-sans placeholder:text-md placeholder:text-faint"
      />
    </>
  );
}

/** Why a format or style is off here (S2-03): Song's music provider, a style the owner hasn't switched on. */
function OffNote({ formats, looks, owner }: { formats: { name: string; off?: string | null }[]; looks: Look[]; owner: boolean }) {
  const parts: ReactNode[] = [];
  for (const f of formats.filter((x) => x.off))
    parts.push(f.off === "off" ? <span key={f.name}><b className="font-semibold">{f.name}</b> is off on this site. </span> : <span key={f.name}><b className="font-semibold">{f.name}</b> is coming next: {f.off}. </span>);
  const off = looks.filter((l) => !l.on);
  if (off.length)
    parts.push(
      <span key="looks">
        {off.map((l, i) => (
          <span key={l.id}>
            {i > 0 && (i === off.length - 1 ? " and " : ", ")}
            <b className="font-semibold">{l.name}</b>
          </span>
        ))}{" "}
        {off.length === 1 ? "is" : "are"} off on this site; the owner turns {off.length === 1 ? "it" : "them"} on in Settings → Looks.
      </span>,
    );
  if (!parts.length) return null;
  return (
    <div className="flex items-start gap-2 rounded-lg bg-surface-2 px-3 py-2.5 text-sm">
      <CircleHelp size={14} aria-hidden className="mt-0.5 shrink-0 text-muted" />
      <span className="min-w-0 flex-1">{parts}</span>
      {owner && (
        <Link to="/settings?tab=looks" className="shrink-0 font-medium text-accent-text hover:underline">
          Settings → Looks
        </Link>
      )}
    </div>
  );
}
