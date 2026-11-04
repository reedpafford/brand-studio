import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Upload, WandSparkles } from "lucide-react";
import { Navigate, useParams, useSearchParams } from "react-router-dom";
import { api, must } from "../api/client";
import { useMe } from "../auth/useMe";
import { useBrands } from "../shell/useBrands";
import { Banner, Button } from "../components";
import { useToast } from "../toast";
import { useRail } from "../useMedia";
import { LibraryCard, Picture } from "./Cards";
import { LibraryFrame, useSearch } from "./LibraryFrame";
import { NewItem } from "./NewItem";
import { PresentersTab } from "./PresentersTab";
import { KINDS, PRODUCT_TYPE, cover, day, isKindSlug, upTo, useItems, useNewPrice, videos, type Item, type KindSlug } from "./kinds";
import { addPicture } from "./products";

/** /b/:brandId/library/:tab: one tab of the brand's library (v6 S8-01 to S8-08, P-13). */
export function LibraryPage() {
  const { brandId, kindSlug } = useParams();
  const id = Number(brandId);
  if (kindSlug === "props") return <Navigate to={`/b/${id}/library/products`} replace />; // the old Props tab
  if (kindSlug === "presenters") return <PresentersTab key={id} brandId={id} />;
  if (!isKindSlug(kindSlug)) return <Navigate to={`/b/${id}/library/characters`} replace />;
  return <KindTab key={`${id}/${kindSlug}`} brandId={id} slug={kindSlug} />;
}

const WIDTH = { characters: "lg:w-[200px]", places: "lg:w-[200px]", products: "lg:w-[220px]" } as const;
const SIZES = {
  characters: "aspect-[175/230] w-full lg:aspect-auto lg:h-[266px] lg:w-[200px]",
  places: "aspect-[175/230] w-full lg:aspect-auto lg:h-[266px] lg:w-[200px]",
  products: "aspect-[175/230] w-full lg:aspect-auto lg:h-[300px] lg:w-[220px]",
} as const;

function KindTab({ brandId, slug }: { brandId: number; slug: KindSlug }) {
  const { kind, one, title } = KINDS[slug];
  const [params, setParams] = useSearchParams();
  const adding = params.get("new") === "1";
  const setAdding = (on: boolean) => setParams((p) => (on ? p.set("new", "1") : p.delete("new"), p), { replace: true });
  const [photo, setPhoto] = useState<File | null>(null); // S8-02 "Upload a photo": picked first, then named
  const [archived, setArchived] = useState(false);
  const [q] = useSearch();
  const rail = useRail();
  const me = useMe().data;
  const owner = me?.role === "owner";
  const items = useItems(kind, brandId);
  const gone = useItems(kind, brandId, true);
  const price = useNewPrice(kind);
  const picker = useRef<HTMLInputElement>(null);
  const match = (i: Item) => i.name.toLowerCase().includes(q.trim().toLowerCase());
  const live = (items.data ?? []).filter(match);
  const old = archived ? (gone.data ?? []).filter(match) : [];
  const empty = items.data?.length === 0 && !adding;
  const New = `New ${one}`;
  const action = (
    <Button variant={empty ? "secondary" : "primary"} icon={Plus} onClick={() => setAdding(true)}>
      {New}
    </Button>
  );
  const start = (file: File | null) => {
    setPhoto(file);
    setAdding(true);
  };
  return (
    <LibraryFrame brandId={brandId} tab={slug} action={adding ? undefined : action} onAdd={() => setAdding(true)} addLabel={New}>
      <input ref={picker} type="file" accept="image/*" className="sr-only" aria-label={`${one} photo`} tabIndex={-1} onChange={(e) => e.target.files?.[0] && start(e.target.files[0])} />
      {items.isError && <Banner title="Couldn't load the library." action={<Button variant="secondary" onClick={() => void items.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {adding ? (
        <NewItem brandId={brandId} kind={kind} photo={photo} onClose={() => (setAdding(false), setPhoto(null))} />
      ) : empty ? (
        <Empty brandId={brandId} slug={slug} price={kind === "prop" ? "" : upTo(price.data?.credits, price.data?.usd)} onUpload={() => picker.current?.click()} onMake={() => start(null)} />
      ) : (
        items.data && (
          <>
            {rail && (
              <div className="mb-4 flex items-center gap-2">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} className="size-4 rounded-sm" />
                  Show archived
                </label>
                <span className="flex-1" />
                {me && !owner && <span className="text-sm text-muted">Editors can add and edit {title.toLowerCase()} here too.</span>}
              </div>
            )}
            {live.length + old.length === 0 && q && <p className="text-sm text-muted">Nothing called “{q}”.</p>}
            <ul className="grid grid-cols-2 gap-x-3 gap-y-3.5 lg:flex lg:flex-wrap lg:items-start lg:gap-5">
              {live.map((i) => (slug === "products" ? <ProductCard key={i.id} brandId={brandId} item={i} /> : <ItemCard key={i.id} brandId={brandId} slug={slug} item={i} />))}
              {old.map((i) => <ArchivedCard key={i.id} item={i} slug={slug} owner={owner} />)}
            </ul>
          </>
        )
      )}
    </LibraryFrame>
  );
}

/** A character's or place's card: "UGC presenter · used in 6 videos", tagged Uploaded when it came from a photo. */
function ItemCard({ brandId, slug, item: i }: { brandId: number; slug: KindSlug; item: Item }) {
  const rail = useRail();
  const used = i.used_in_count;
  const role = i.presenter ? "Presenter" : "";
  const line = !rail ? videos(used) : role ? `${role} · ${used ? `used in ${videos(used)}` : "not used yet"}` : used ? `Used in ${videos(used)}` : "Not used yet";
  return <LibraryCard to={`/b/${brandId}/library/${slug}/${i.id}`} size={SIZES[slug]} width={WIDTH[slug]} picture={<Picture id={cover(i)} alt={i.name} className="size-full" />} name={i.name} tag={rail && i.source_photo_file_id ? "Uploaded" : undefined} line={line} />;
}

/** A product's card (S8-06, S-gaps-05 L1): its first picture, tagged App or Physical, and its line ("10 screens · shown
 *  as given; numbers follow the story", or what must read right); with no picture yet, a dashed box that takes one. */
function ProductCard({ brandId, item: i }: { brandId: number; item: Item }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const add = useMutation({
    mutationFn: (file: File) => addPicture(brandId, i, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["library", "prop"] }),
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const pic = cover(i);
  const app = i.product_type === "app";
  const n = i.pictures?.length ?? 0;
  const words = app ? `${n} screen${n === 1 ? "" : "s"} · shown as given; numbers follow the story` : i.notes || i.main_claim || i.short_description || "";
  const tag = PRODUCT_TYPE[app ? "app" : "physical"];
  if (pic) return <LibraryCard to={`/b/${brandId}/library/products/${i.id}`} size={SIZES.products} width={WIDTH.products} picture={<Picture id={pic} alt={i.name} className="size-full" />} name={i.name} tag={tag} line={words} />;
  const box = (
    <label className={`flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-md border border-dashed border-border-strong bg-surface-2 text-muted ${SIZES.products}`}>
      <Upload size={20} strokeWidth={1.75} aria-hidden />
      <span className="text-sm">{add.isPending ? "Uploading…" : i.name}</span>
      <input type="file" accept="image/*" className="sr-only" aria-label={`Add a photo of ${i.name}`} onChange={(e) => e.target.files?.[0] && add.mutate(e.target.files[0])} />
    </label>
  );
  return <LibraryCard size="" width={WIDTH.products} picture={box} name={i.name} tag={tag} line={app ? "No screens yet. The director asks for them when a video needs them." : "No photo yet. The director asks for it when a video needs it."} />;
}

/** An archived item (S8-08): faded, "Archived 20 Oct · kept for old videos", with Unarchive (and the owner's Delete
 *  forever) under it. */
function ArchivedCard({ item: i, slug, owner }: { item: Item; slug: KindSlug; owner: boolean }) {
  const { kind } = KINDS[slug];
  const queryClient = useQueryClient();
  const toast = useToast();
  const path = { kind, item_id: i.id };
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["library", kind] });
  const back = useMutation({
    mutationFn: () => must(api.POST("/library/{kind}/{item_id}/unarchive", { params: { path } })),
    onSuccess: () => {
      void refresh();
      toast(`${i.name} is back.`, async () => {
        await must(api.DELETE("/library/{kind}/{item_id}", { params: { path } }));
        void refresh();
      });
    },
  });
  const purge = useMutation({ mutationFn: () => must(api.DELETE("/library/{kind}/{item_id}/permanent", { params: { path } })), onSuccess: refresh });
  const when = i.archived_at ? `Archived ${day(i.archived_at)}` : "Archived";
  return (
    <LibraryCard size={SIZES[slug]} width={WIDTH[slug]} faded picture={<Picture id={cover(i)} alt={i.name} className="size-full" />} name={i.name} tag="Archived" line={`${when} · kept for old videos`}>
      <span className="mt-1 flex gap-3 text-sm">
        <button type="button" className="min-h-control text-accent-text hover:underline lg:min-h-0" aria-label={`Unarchive ${i.name}`} onClick={() => back.mutate()}>Unarchive</button>
        {owner && (
          <button type="button" className="min-h-control text-danger hover:underline lg:min-h-0" aria-label={`Delete ${i.name} forever`} onClick={() => window.confirm(`Delete ${i.name} forever? This removes all versions and can't be undone.`) && purge.mutate()}>
            Delete forever
          </button>
        )}
      </span>
    </LibraryCard>
  );
}

const EMPTY: Record<KindSlug, (brand: string) => string> = {
  characters: (b) => `Add the people who recur in ${b}’s videos. The director casts them without asking, and every shot keeps the same face.`,
  places: (b) => `Add the places ${b}’s videos come back to. The director uses them without asking, and every shot keeps the same room.`,
  products: (b) => `Add ${b}’s products: an app with its screens, or a thing with its real photo. Videos show them exactly as given.`,
};

/** A brand with none yet (S8-02): three empty frames, what they're for, and Upload a photo or Make one with its price. */
function Empty({ brandId, slug, price, onUpload, onMake }: { brandId: number; slug: KindSlug; price: string; onUpload: () => void; onMake: () => void }) {
  const name = useBrandName(brandId);
  const { title } = KINDS[slug];
  return (
    <section className="flex min-h-[640px] flex-col items-center justify-center gap-3 text-center">
      <div aria-hidden className="flex gap-2">
        {[0, 1, 2].map((n) => <span key={n} className="h-[120px] w-[90px] rounded-md border border-dashed border-border-strong bg-surface-2" />)}
      </div>
      <h2 className="text-xl font-semibold">No {title.toLowerCase()} in {name} yet</h2>
      <p className="max-w-[460px] text-md text-muted">{EMPTY[slug](name)}</p>
      <div className="flex flex-wrap justify-center gap-2">
        <Button icon={Upload} onClick={onUpload}>Upload a photo</Button>
        {slug !== "products" && (
          <Button variant="secondary" icon={WandSparkles} onClick={onMake}>
            Make one{price && <span className="opacity-80"> · {price}</span>}
          </Button>
        )}
      </div>
    </section>
  );
}

const useBrandName = (id: number) => useBrands().data?.find((b) => b.id === id)?.name ?? "";
