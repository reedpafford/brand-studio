import { useState } from "react";
import { ArrowLeft, Package, Palette } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { SHAPES, sentTo } from "../freestyle/useFreestyle";
import { Attach, Attached } from "../newvideo/Attach";
import { StyleFan, StyleGallery, lookMedia } from "../newvideo/Cards";
import { CastIcon, Chip, FolderIcon, ShapeIcon } from "../newvideo/Chips";
import { Press, Under, box } from "../newvideo/Press";
import { Reel } from "../newvideo/Reel";
import { SavedScripts } from "../newvideo/SavedScripts";
import { useEstimate, useSend } from "../newvideo/useNewVideo";
import { ActionBar } from "../shell/ActionBar";
import { useBrands } from "../shell/useBrands";
import { useRail } from "../useMedia";
import { AssetDialog, type AssetTab } from "./AssetDialog";
import { ModeMenu, PickChip } from "./Chips";
import { StylesDialog, styleWords } from "./StylesDialog";
import { WORDS_ID, Words, WordsAre } from "./Words";
import { useDraft, useSaved } from "./useDraft";

type View = "paste" | "script" | "reel";
const HEADS = { script: "Use a saved script", reel: "Use a reel" };

/** Home (a brand's front door, and New video's address): paste a script or an idea, pick a style, and the director makes
 *  it in a chat. A centred headline over one box, no wider than 720 px, with its settings as small pills (style, product,
 *  cast, shape, folder, mode) and the price on the press; under it the styles, as a gallery: pressing one picks it for
 *  the box and goes to the words. The + menu also starts from a saved script (its own style: no gallery) or a reel
 *  (?from=script|reel). The idea lands in the open folder (?folder=) or Unsorted, and Make it opens the video. */
export function HomePage() {
  const brandId = Number(useParams().brandId);
  const [params, setParams] = useSearchParams();
  const from = params.get("from");
  const view: View = from === "script" || from === "reel" ? from : "paste";
  const setView = (v: View) => setParams((p) => (v === "paste" ? p.delete("from") : p.set("from", v), p), { replace: true });
  const rail = useRail();
  const navigate = useNavigate();
  const brands = useBrands().data;
  // From a saved script: the Styles dialog shows the script's own format and style, locked (its words, format and style are set).
  const [locked, setLocked] = useState<{ type: string; look: string } | null>(null);
  const draft = useDraft(brandId, Number(params.get("folder")) || null, view === "script" ? locked : null);
  const [dialog, setDialog] = useState<"styles" | AssetTab | null>(null);
  const cast = useSaved("character", brandId).data ?? [];
  const products = useSaved("prop", brandId).data ?? [];
  const { owner, format, look, folder, folders, files, size } = draft;
  const send = draft.send;
  const empty = !send.text || size.over || !look || !format || files.busy;
  const price = useEstimate(view === "paste" && !empty ? send : null);
  const sent = useSend((fs) => navigate(sentTo(fs, owner, brandId)));
  const go = () => !empty && !sent.isPending && sent.mutate(send);
  if (brands && !brands.some((b) => b.id === brandId)) return <p className="p-6">That brand doesn't exist.</p>;

  /** One picked item by its name, several by their number ("2 products"). */
  const said = (ids: number[], rows: { id: number; name: string }[], many: string) => (ids.length === 1 ? (rows.find((r) => r.id === ids[0])?.name ?? `1 ${many}`) : ids.length ? `${ids.length} ${many}` : "");
  const style = <PickChip label="Style" icon={Palette} thumb={look ? lookMedia(look).still : undefined} value={styleWords(draft)} none="not picked" onClick={() => setDialog("styles")} />;
  const chips = (
    <>
      <Attach files={files} onScript={() => setView("script")} onReel={() => setView("reel")} />
      {style}
      <PickChip label="Product" icon={Package} value={said(draft.products, products, "products")} none="None" onClick={() => setDialog("products")} onClear={() => draft.pick({ products: [] })} />
      <PickChip label="Cast" icon={CastIcon} value={said(draft.cast, cast, "people")} none="Nobody" onClick={() => setDialog("cast")} onClear={() => draft.pick({ cast: [] })} />
      <Chip label="Shape" icon={ShapeIcon} value={send.shape} options={SHAPES.map((s) => ({ id: s, name: s }))} onPick={(shape) => draft.pick({ shape })} />
      <Chip label="Folder" icon={FolderIcon} value={folder ?? 0} options={[...folders.map((f) => ({ id: f.id, name: f.name })), { id: 0, name: "Unsorted" }]} onPick={(f) => draft.pick({ folder: f || null })} />
    </>
  );
  const mode = <ModeMenu mode={draft.mode} owner={owner} onPick={draft.setMode} />;
  const words = (
    <>
      <Words text={draft.text} size={size} setText={draft.setText} go={go} rail={rail} narrated={format?.engine === "narrated"} />
      <Attached files={files} />
      <div className="pt-2">
        <WordsAre idea={draft.idea} onPick={draft.setIdea} />
      </div>
    </>
  );
  const head = view !== "paste" && (
    <div className="flex items-center gap-1.5">
      <button type="button" aria-label="Back to the words box" onClick={() => setView("paste")} className="grid size-control shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-text lg:size-7">
        <ArrowLeft size={16} strokeWidth={1.75} aria-hidden />
      </button>
      <h2 className="whitespace-nowrap text-sm font-semibold">{HEADS[view]}</h2>
      {view === "script" && (
        <Link to={`/b/${brandId}/scripts`} className="inline-flex min-h-control items-center whitespace-nowrap pl-2 text-sm text-accent-text hover:underline lg:min-h-7">
          Manage scripts
        </Link>
      )}
    </div>
  );
  const scriptStyle = locked ? style : null; // a saved script's own, once one is picked
  const other =
    view === "script" ? (
      <SavedScripts brandId={brandId} owner={owner} folder={folder} broll={draft.broll} head={head} style={scriptStyle} rail={rail} onScript={setLocked} />
    ) : view === "reel" ? (
      <Reel brandId={brandId} owner={owner} folder={folder} head={head} style={style} rail={rail} format={send.type} formatName={format?.name} look={look} broll={draft.broll} />
    ) : null;
  const error = (
    <>
      {sent.isError && <p role="alert" className="text-sm text-danger">{sent.error.message}</p>}
      {draft.moved && <p role="status" className="text-sm text-warning">{draft.moved}</p>}
    </>
  );
  const hero = (
    <div className={`flex flex-col gap-3 ${rail ? "items-center text-center" : ""}`}>
      {rail && view === "paste" && <StyleFan looks={draft.looks} look={look} />}
      <h1 className={`type-hero ${rail ? "pt-3" : ""}`}>
        <span className="block">Paste your script, pick a style.</span> <span className="block text-muted">We handle the rest.</span>
      </h1>
      <p className="max-w-[560px] text-balance text-md text-muted">The director plans it, asks what it can’t decide, and makes it in a chat with you.</p>
    </div>
  );
  const gallery = view !== "script" && draft.looks.length > 0 && (
    <section aria-labelledby="home-styles" className="flex flex-col gap-4">
      <div className="flex flex-col gap-1 lg:text-center">
        <h2 id="home-styles" className="type-page">Styles</h2>
        <p className="text-sm text-muted">Pick a look. Each one comes with its own way of shooting.</p>
      </div>
      <StyleGallery looks={draft.looks} value={look?.id ?? ""} onPick={(l) => (draft.pickStyle(l), document.getElementById(WORDS_ID)?.focus())} />
    </section>
  );
  const dialogs = (
    <>
      {dialog === "styles" && <StylesDialog draft={draft} onClose={() => setDialog(null)} />}
      {dialog && dialog !== "styles" && <AssetDialog brandId={brandId} draft={draft} start={dialog} onClose={() => setDialog(null)} />}
    </>
  );
  if (!rail)
    return (
      <main className="flex flex-col gap-5 px-4 py-5">
        {hero}
        {other ? (
          <>
            {head}
            {other}
            {(view === "reel" || scriptStyle) && <div className="flex flex-wrap gap-2">{style}</div>}
          </>
        ) : (
          <>
            <div className={`${box} p-3`}>{words}</div>
            <div className="flex flex-wrap gap-2">
              {chips}
              {mode}
            </div>
            <ActionBar phone>
              <div className="flex flex-col gap-1">
                <Press owner={owner} price={price} busy={sent.isPending} disabled={empty} onClick={go} wide />
                {!empty && <Under owner={owner} {...price} phone />}
              </div>
            </ActionBar>
          </>
        )}
        {error}
        {gallery}
        {dialogs}
      </main>
    );
  return (
    <main className="relative isolate flex min-h-screen justify-center px-8 pb-16 pt-[clamp(2rem,6vh,4rem)]">
      {/* A soft indigo light from the top, behind the headline: the page has a source, not a flat sheet. */}
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[560px] bg-[radial-gradient(60%_100%_at_50%_0%,var(--accent-soft),transparent)]" />
      <div className="flex w-full max-w-[1112px] flex-col gap-8">
        <div className="mx-auto flex w-full max-w-[720px] flex-col gap-8">
          {hero}
          <div>
            {other ?? (
              <>
                <div className={`${box} shadow-float`}>
                  <div className="px-4 pb-3 pt-3.5">{words}</div>
                  {/* The pills wrap on the left; Mode and the press keep the right, in room held for the price, so nothing
                      moves when it arrives. */}
                  <div className="flex items-end gap-2 border-t border-border px-3 py-2.5">
                    <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">{chips}</div>
                    <div className="flex min-w-[19rem] shrink-0 items-center justify-end gap-1.5">
                      {mode}
                      <Press owner={owner} price={price} busy={sent.isPending} disabled={empty} onClick={go} shortcut />
                    </div>
                  </div>
                </div>
                <div className="flex min-h-10 items-start justify-end px-1 pt-2">{!empty && <Under owner={owner} {...price} />}</div>
              </>
            )}
            {error}
          </div>
        </div>
        {gallery}
      </div>
      {dialogs}
    </main>
  );
}
