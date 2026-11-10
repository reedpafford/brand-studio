import { useState } from "react";
import { ArrowLeft, Package, Palette } from "lucide-react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { SHAPES, sentTo } from "../freestyle/useFreestyle";
import { Attach, Attached } from "../newvideo/Attach";
import { CastIcon, Chip, FolderIcon } from "../newvideo/Chips";
import { Press, Under, box, row } from "../newvideo/Press";
import { Reel } from "../newvideo/Reel";
import { SavedScripts } from "../newvideo/SavedScripts";
import { useEstimate, useSend } from "../newvideo/useNewVideo";
import { ActionBar } from "../shell/ActionBar";
import { useBrands } from "../shell/useBrands";
import { useRail } from "../useMedia";
import { AssetDialog, type AssetTab } from "./AssetDialog";
import { CardDialog } from "./CardDialog";
import { ModeMenu, PickChip } from "./Chips";
import { StoryCards } from "./StoryCards";
import { StylesDialog, styleWords } from "./StylesDialog";
import { Words, WordsAre } from "./Words";
import { useCards, useDraft, useSaved, type StoryCard } from "./useDraft";

type View = "paste" | "script" | "reel";
const HEADS = { script: "Use a saved script", reel: "Use a reel" };

/** Home (a brand's front door, and New video's address): paste a script or an idea, pick a style, and the director makes
 *  it in a chat. One box with its settings as chips (style, product, cast, shape, folder, mode) and the price on the
 *  press; under it the story cards. The + menu also starts from a saved script or a reel (?from=script|reel). The idea
 *  lands in the open folder (?folder=) or Unsorted, and Make it opens the video. */
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
  const cards = useCards();
  const [dialog, setDialog] = useState<"styles" | AssetTab | null>(null);
  const [card, setCard] = useState<StoryCard | null>(null);
  const cast = useSaved("character", brandId).data ?? [];
  const products = useSaved("prop", brandId).data ?? [];
  const { owner, format, look, folder, folders, files, size } = draft;
  const send = draft.send();
  const empty = !send.text || size.over || !look || !format || files.busy;
  const price = useEstimate(view === "paste" && !card && !empty ? send : null);
  const sent = useSend((fs) => navigate(sentTo(fs, owner, brandId)));
  const go = () => !empty && !sent.isPending && sent.mutate(send);
  if (brands && !brands.some((b) => b.id === brandId)) return <p className="p-6">That brand doesn't exist.</p>;

  /** One picked item by its name, several by their number ("2 products"). */
  const said = (ids: number[], rows: { id: number; name: string }[], many: string) => (ids.length === 1 ? (rows.find((r) => r.id === ids[0])?.name ?? `1 ${many}`) : ids.length ? `${ids.length} ${many}` : "");
  const style = <PickChip label="Style" icon={Palette} value={styleWords(draft)} none="not picked" onClick={() => setDialog("styles")} />;
  const chips = (
    <>
      <Attach files={files} onScript={() => setView("script")} onReel={() => setView("reel")} />
      {style}
      <PickChip label="Product" icon={Package} value={said(draft.products, products, "products")} none="None" onClick={() => setDialog("products")} />
      <PickChip label="Cast" icon={CastIcon} value={said(draft.cast, cast, "people")} none="Nobody" onClick={() => setDialog("cast")} />
      <Chip label="Shape" value={send.shape} options={SHAPES.map((s) => ({ id: s, name: s }))} onPick={(shape) => draft.pick({ shape })} />
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
    </div>
  );
  const scriptStyle = locked ? style : null; // a saved script's own, once one is picked
  const other =
    view === "script" ? (
      <SavedScripts brandId={brandId} owner={owner} folder={folder} broll={draft.broll} head={head} style={scriptStyle} rail={rail} onScript={setLocked} />
    ) : view === "reel" ? (
      <Reel brandId={brandId} owner={owner} folder={folder} head={head} style={style} rail={rail} format={send.type} formatName={format?.name} look={look} broll={draft.broll} />
    ) : null;
  const error = sent.isError && <p role="alert" className="text-sm text-danger">{sent.error.message}</p>;
  const hero = (
    <div className={`flex flex-col gap-2 ${rail ? "items-center text-center" : ""}`}>
      <h1 className="type-page">
        <span className="block">Paste your script, pick a style.</span> <span className="block text-muted">We handle the rest.</span>
      </h1>
      <p className="max-w-[560px] text-base text-muted">The director plans it, asks what it can’t decide, and makes it in a chat with you.</p>
    </div>
  );
  const gallery = <StoryCards cards={cards.data ?? []} loading={cards.isPending} looks={draft.looks} onOpen={setCard} />;
  const dialogs = (
    <>
      {card && <CardDialog card={card} cards={cards.data ?? []} draft={draft} cast={cast} products={products} onCard={setCard} onAssets={setDialog} onSent={(fs) => navigate(sentTo(fs, owner, brandId))} onClose={() => setCard(null)} />}
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
    <main className="flex min-h-screen justify-center px-8 pb-16 pt-14">
      <div className="flex w-full max-w-[1112px] flex-col gap-12">
        <div className="mx-auto flex w-full max-w-[880px] flex-col gap-6">
          {hero}
          <div>
            {other ?? (
              <>
                <div className={box}>
                  <div className="px-4 pb-3 pt-3">{words}</div>
                  <div className={row}>
                    {chips}
                    {/* Kept to the right, on whichever line the chips leave it. */}
                    <div className="ml-auto flex items-center gap-1.5">
                      {mode}
                      <Press owner={owner} price={price} busy={sent.isPending} disabled={empty} onClick={go} shortcut />
                    </div>
                  </div>
                </div>
                <div className="flex min-h-7 items-center justify-end px-1 pt-2">{!empty && <Under owner={owner} {...price} />}</div>
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
