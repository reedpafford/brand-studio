import { useState } from "react";
import { Check, Plus } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, Modal, Segmented, Skeleton } from "../components";
import { Picture } from "../library/Cards";
import { cover } from "../library/kinds";
import { Attached, UploadPress } from "../newvideo/Attach";
import { useSaved, type Draft } from "./useDraft";

export type AssetTab = "cast" | "products" | "uploads";
const many = (n: number, one: string, more = `${one}s`) => `${n} ${n === 1 ? one : more}`;
const grid = "grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5";

/** Cast | Products | Uploads for this video: the brand's saved characters and products as picture tiles (pick several),
 *  and pictures or clips for this video only. A pick is kept at once; Done closes. The "new" tiles open Cast & places
 *  in a new tab, so the words already typed stay; the list refreshes on coming back. */
export function AssetDialog({ brandId, draft, start, onClose }: { brandId: number; draft: Draft; start: AssetTab; onClose: () => void }) {
  const [tab, setTab] = useState(start);
  const cast = useSaved("character", brandId);
  const products = useSaved("prop", brandId);
  const uploads = draft.files.files.length;
  const picked = [draft.cast.length && many(draft.cast.length, "person", "people"), draft.products.length && many(draft.products.length, "product"), uploads && many(uploads, "upload")].filter(Boolean).join(" · ");
  const count = (n: number) => (n ? <span className="tabular-nums text-muted">{n}</span> : null);
  const foot = (
    <div className="flex items-center gap-3">
      <p className="min-w-0 flex-1 truncate text-sm text-muted">{picked ? `Picked: ${picked}` : "Nothing picked yet"}</p>
      <Button onClick={onClose}>Done</Button>
    </div>
  );
  return (
    <Modal title="Cast and products" onClose={onClose} footer={foot}>
      <Segmented
        label="What to add"
        className="max-sm:flex max-sm:w-full [&>button]:max-sm:flex-1"
        value={tab}
        onChange={setTab}
        items={[
          { id: "cast", name: <>Cast {count(draft.cast.length)}</> },
          { id: "products", name: <>Products {count(draft.products.length)}</> },
          { id: "uploads", name: <>Uploads {count(uploads)}</> },
        ]}
      />
      <div role="tabpanel" aria-label={tab === "cast" ? "Cast" : tab === "products" ? "Products" : "Uploads"} className="flex flex-col gap-3 pt-4 sm:min-h-[400px]">
        {tab === "cast" && (
          <Tiles
            line="The same person in every ad you make"
            items={cast}
            picked={draft.cast}
            onToggle={(id) => draft.toggle("cast", id)}
            add={{ label: "New character", to: `/b/${brandId}/library/characters?new=1` }}
            empty={["No saved characters yet.", "Add a character", "so the same person is in every ad you make."]}
          />
        )}
        {tab === "products" && (
          <Tiles
            line="The real product, shown exactly as given"
            items={products}
            picked={draft.products}
            onToggle={(id) => draft.toggle("products", id)}
            add={{ label: "Add product", to: `/b/${brandId}/library/products?new=1` }}
            empty={["No products yet.", "Add your product", "so every ad shows the real one."]}
          />
        )}
        {tab === "uploads" && (
          <>
            <p className="text-sm font-semibold">Pictures or clips for this video only</p>
            <div>
              <UploadPress files={draft.files} />
            </div>
            {uploads ? <Attached files={draft.files} /> : <p className="text-sm text-muted">A reference, a screenshot or a shot of the product. The director uses them for this video; they aren’t added to the brand.</p>}
          </>
        )}
      </div>
    </Modal>
  );
}

type Saved = ReturnType<typeof useSaved>;

/** Saved items as picture tiles that tick: the "new" tile first, then each with its sheet or first picture and its name. */
function Tiles({ line, items, picked, onToggle, add, empty }: { line: string; items: Saved; picked: number[]; onToggle: (id: number) => void; add: { label: string; to: string }; empty: [string, string, string] }) {
  const rows = items.data ?? [];
  const fresh = { target: "_blank", rel: "noreferrer" };
  return (
    <>
      <p className="text-sm font-semibold">{line}</p>
      {items.isError && (
        <p role="alert" className="flex flex-wrap items-center gap-2 text-sm text-danger">
          Couldn’t load these. Check your connection.
          <Button variant="secondary" dense onClick={() => void items.refetch()}>
            Try again
          </Button>
        </p>
      )}
      {items.data?.length === 0 && (
        <p className="text-sm text-muted">
          {empty[0]}{" "}
          <Link to={add.to} {...fresh} className="font-medium text-accent-text underline-offset-2 hover:underline">
            {empty[1]}
          </Link>{" "}
          {empty[2]}
        </p>
      )}
      <ul className={grid}>
        <li>
          <Link to={add.to} {...fresh} className="flex aspect-[4/5] flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border-strong bg-surface-2 px-2 text-center text-sm font-medium transition-colors duration-(--dur-fast) hover:bg-surface-3">
            <span aria-hidden className="grid size-8 place-items-center rounded-full border border-border-button bg-surface">
              <Plus size={16} strokeWidth={1.75} />
            </span>
            {add.label}
            <span className="text-xs font-normal text-muted">Opens in a new tab</span>
          </Link>
        </li>
        {items.isPending && [0, 1, 2].map((n) => <li key={n}><Skeleton className="aspect-[4/5]" /></li>)}
        {rows.map((i) => {
          const on = picked.includes(i.id);
          return (
            <li key={i.id} className="min-w-0">
              <button type="button" role="checkbox" aria-checked={on} onClick={() => onToggle(i.id)} className="group flex w-full flex-col gap-1.5 rounded-lg text-left">
                <span className={`relative block aspect-[4/5] w-full overflow-hidden rounded-lg border transition-[border-color,box-shadow] duration-(--dur-fast) ${on ? "border-accent ring-2 ring-accent" : "border-border group-hover:border-border-button group-hover:shadow-hover"}`}>
                  <Picture id={cover(i)} alt="" className="size-full rounded-none! border-0!" />
                  <span aria-hidden className={`absolute right-2 top-2 grid size-6 place-items-center rounded-full border ${on ? "border-accent bg-accent text-on-accent" : "border-white/70 bg-black/25 text-transparent"}`}>
                    <Check size={14} strokeWidth={2.5} />
                  </span>
                </span>
                <span className="truncate text-sm font-medium">{i.name}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </>
  );
}
