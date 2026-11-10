import type { ComponentType } from "react";
import { Package, Users } from "lucide-react";
import { fileUrl } from "../api/upload";
import { Modal } from "../components";
import { SHAPES, type Freestyle } from "../freestyle/useFreestyle";
import { cover, type Item } from "../library/kinds";
import { Attached } from "../newvideo/Attach";
import { Chip } from "../newvideo/Chips";
import { Press, Under, box, row } from "../newvideo/Press";
import { useEstimate, useSend } from "../newvideo/useNewVideo";
import { useRail } from "../useMedia";
import type { AssetTab } from "./AssetDialog";
import { ModeMenu } from "./Chips";
import { CardPicture } from "./StoryCards";
import { Words, WordsAre } from "./Words";
import type { Draft, StoryCard } from "./useDraft";

/** A story card, opened: its style's sample in a phone-shaped frame; beside it the card, the cast and product for it, the
 *  idea or script, and "Make this ad" with the most it can charge. The strip along the foot switches between the cards
 *  in the same style. It sends the box's own draft with the card and the card's style and format. */
export function CardDialog({ card, cards, draft, cast, products, onCard, onAssets, onSent, onClose }: { card: StoryCard; cards: StoryCard[]; draft: Draft; cast: Item[]; products: Item[]; onCard: (c: StoryCard) => void; onAssets: (tab: AssetTab) => void; onSent: (fs: Freestyle) => void; onClose: () => void }) {
  const rail = useRail();
  const { owner, files, size } = draft;
  const look = draft.looks.find((l) => l.id === card.style);
  const send = draft.send(card);
  const empty = !send.text || size.over || files.busy;
  const price = useEstimate(empty ? null : send);
  const sent = useSend(onSent);
  const go = () => !empty && !sent.isPending && sent.mutate(send);
  const others = cards.filter((c) => c.style === card.style);
  const picked = (rows: Item[], ids: number[]) => rows.filter((r) => ids.includes(r.id));
  return (
    <Modal bare title={card.title} onClose={onClose}>
      <div className="flex flex-col gap-5 sm:flex-row sm:gap-6">
        <div className="w-36 shrink-0 self-center overflow-hidden rounded-[20px] border border-border shadow-soft sm:w-[270px] sm:self-start">
          <CardPicture card={card} look={look} playing />
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <div className="flex flex-col gap-1 sm:pr-10">
            <h2 className="type-page">{card.title}</h2>
            {card.subtitle && <p className="text-base text-muted">{card.subtitle}</p>}
            <p className="text-sm text-muted">{[card.style_name, card.format_name, `about ${card.seconds} s`].join(" · ")}</p>
          </div>
          <div className="flex gap-3">
            <PickTile label="Cast" icon={Users} hint="The same person in every ad" items={picked(cast, draft.cast)} onClick={() => onAssets("cast")} />
            <PickTile label="Product" icon={Package} hint="The real one, shown exactly" items={picked(products, draft.products)} onClick={() => onAssets("products")} />
          </div>
          <div>
            <div className={box}>
              <div className="px-4 pb-3 pt-3">
                <Words inDialog id="card-words" label="Describe your idea or paste a script" placeholder="Describe your idea or paste a script…" text={draft.text} size={size} setText={draft.setText} go={go} rail={rail} narrated={draft.formats.find((f) => f.id === card.format)?.engine === "narrated"} />
                <Attached files={files} />
                <div className="pt-2">
                  <WordsAre idea={draft.idea} onPick={draft.setIdea} />
                </div>
              </div>
              <div className={row}>
                <Chip label="Shape" value={send.shape} options={SHAPES.map((s) => ({ id: s, name: s }))} onPick={(shape) => draft.pick({ shape })} />
                <ModeMenu mode={draft.mode} owner={owner} onPick={draft.setMode} />
                <div className="ml-auto max-lg:w-full">
                  <Press owner={owner} price={price} busy={sent.isPending} disabled={empty} onClick={go} go="Make this ad" wide={!rail} shortcut />
                </div>
              </div>
            </div>
            <div className="flex min-h-7 items-center justify-end px-1 pt-2">{!empty && <Under owner={owner} {...price} phone={!rail} />}</div>
            {sent.isError && <p role="alert" className="text-sm text-danger">{sent.error.message}</p>}
          </div>
        </div>
      </div>
      {others.length > 1 && (
        <nav aria-label={`${card.style_name} story cards`} className="mt-5 border-t border-border pt-4">
          <ul className="-m-1 flex gap-2 overflow-x-auto p-1">
            {others.map((c) => (
              <li key={c.id} className="w-[76px] shrink-0">
                <button type="button" aria-label={c.title} aria-current={c.id === card.id || undefined} aria-disabled={!c.on || undefined} onClick={() => c.on && onCard(c)} className={`block w-full overflow-hidden rounded-md border transition-[border-color,box-shadow] duration-(--dur-fast) ${c.id === card.id ? "border-accent ring-2 ring-accent" : c.on ? "border-border hover:border-border-button hover:shadow-hover" : "cursor-not-allowed border-border"}`}>
                  <CardPicture card={c} look={look} playing={false} small />
                </button>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </Modal>
  );
}

/** "Cast" or "Product" for this ad: what is picked (their pictures and names), or what picking gives. Opens the picker. */
function PickTile({ label, icon: I, hint, items, onClick }: { label: string; icon: ComponentType<{ size?: number; strokeWidth?: number; "aria-hidden"?: boolean }>; hint: string; items: Item[]; onClick: () => void }) {
  const pictures = items.map(cover).filter((id): id is number => !!id).slice(0, 3);
  return (
    <button type="button" aria-haspopup="dialog" onClick={onClick} className={`flex min-h-[104px] min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-lg border px-3 py-3 text-center transition-colors duration-(--dur-fast) ${items.length ? "border-accent-line bg-accent-soft" : "border-dashed border-border-strong bg-surface-2/60 hover:bg-surface-2"}`}>
      {pictures.length ? (
        <span aria-hidden className="flex -space-x-2">
          {pictures.map((id) => <img key={id} src={fileUrl(id)} alt="" className="size-9 rounded-full border-2 border-surface bg-surface-2 object-cover" />)}
        </span>
      ) : (
        <span aria-hidden className="grid size-9 place-items-center rounded-full border border-border-button bg-surface text-muted">
          <I size={16} strokeWidth={1.75} />
        </span>
      )}
      <span className="text-sm font-semibold">{label}</span>
      <span className="line-clamp-2 max-w-full text-xs text-muted">{items.length ? items.map((i) => i.name).join(", ") : hint}</span>
    </button>
  );
}
