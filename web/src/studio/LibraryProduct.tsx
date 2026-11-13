import { useRef, useState, type ReactNode } from "react";
import { Film, Package, Plus, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { useFootage, type Footage } from "../library/FootageTab";
import { useAddPicture, useCreateItem, useRemovePicture } from "../library/itemActions";
import { useItems, type Item } from "../library/kinds";
import { useBrands } from "../shell/useBrands";
import { Dialog } from "./Dialog";
import { HowItWorks } from "./HowItWorks";
import { AddClip, ClipOpen, ClipTile, Failed, FileRow, Head, Hold, ICON, Loading, usePick } from "./libraryParts";

/** Library › Product: the brand's product as the director is given it. Left: its real pictures, what it is, and "How
 *  it works". Right: the brand's clips of it, by the folder each is in; one opens larger. */
export function ProductTab({ brandId }: { brandId: number }) {
  const products = useItems("prop", brandId);
  const footage = useFootage(brandId);
  const brand = useBrands().data?.find((b) => b.id === brandId)?.name ?? "this brand";
  const [picked, pick] = usePick();
  const [asking, setAsking] = useState<"clip" | "product" | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const list = products.data ?? [];
  const product = list.find((p) => p.id === picked) ?? list[0];
  const clips = (footage.data ?? []).filter((c) => product && c.product_id === product.id);
  const shown = clips.find((c) => c.id === open);
  const newProduct = (
    <button type="button" className={product ? "btn ghost" : "btn go"} onClick={() => setAsking("product")}>
      <Plus {...ICON} />
      {product ? "Another product" : "New product"}
    </button>
  );
  return (
    <>
      <Head
        action={
          product && (
            <button type="button" className="btn go" onClick={() => setAsking("clip")}>
              <Plus {...ICON} />
              Add clips
            </button>
          )
        }
      />
      <div className="view">
        <div className="page lib">
          {products.isPending ? (
            <Loading />
          ) : products.isError ? (
            <Failed icon={Package} what="the product" error={products.error} again={() => void products.refetch()} />
          ) : !product ? (
            <Hold icon={Package} title={`No product saved for ${brand} yet`} action={newProduct}>
              Add the product with a real photo. Videos show it exactly as it is, and the director reads how it works.
            </Hold>
          ) : (
            <>
              {list.length > 1 && (
                <div className="products" role="group" aria-label="Products">
                  {list.map((p) => (
                    <button key={p.id} type="button" className="pill" aria-pressed={p === product} onClick={() => pick(p.id)}>
                      {p.name}
                    </button>
                  ))}
                </div>
              )}
              <div className="pboard">
                <About key={product.id} brandId={brandId} product={product} more={newProduct} />
                <div className="pacts">
                  {footage.isError ? (
                    <Failed icon={Film} what="its clips" error={footage.error} again={() => void footage.refetch()} />
                  ) : footage.isSuccess && clips.length === 0 ? (
                    <Hold icon={Film} title={`No clips of ${product.name} yet`}>
                      Add real clips of it in use. The director sees how it looks and works, and can cut one in.
                    </Hold>
                  ) : (
                    byFolder(clips).map(([folder, inIt]) => (
                      <section key={folder} aria-labelledby={`pf-${inIt[0].id}`}>
                        <h3 id={`pf-${inIt[0].id}`}>{folder.replaceAll("/", " › ") || "Not in a folder"}</h3>
                        <div className="clips4">
                          {inIt.map((c) => (
                            <ClipTile key={c.id} clip={c} onOpen={() => setOpen(c.id)} />
                          ))}
                        </div>
                      </section>
                    ))
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
      {asking === "clip" && product && <AddClip brandId={brandId} folder="" productId={product.id} onClose={() => setAsking(null)} />}
      {asking === "product" && <NewProduct brandId={brandId} onMade={pick} onClose={() => setAsking(null)} />}
      {shown && <ClipOpen brandId={brandId} clip={shown} onClose={() => setOpen(null)} />}
    </>
  );
}

/** The clips grouped by the folder each is in, in the order the server lists them. */
function byFolder(clips: Footage[]): [string, Footage[]][] {
  const groups = new Map<string, Footage[]>();
  for (const c of clips) groups.set(c.folder, [...(groups.get(c.folder) ?? []), c]);
  return [...groups];
}

/** The product itself: its pictures (one shown large, whole), its name and what the server holds about it, a photo
 *  to add (free), and "How it works". */
function About({ brandId, product, more }: { brandId: number; product: Item; more: ReactNode }) {
  const [shown, setShown] = useState<number | null>(null);
  const add = useAddPicture(brandId, product);
  const remove = useRemovePicture(brandId, product);
  const photo = useRef<HTMLInputElement>(null);
  const pictures = product.pictures ?? [];
  const big = pictures.find((p) => p.file_id === shown) ?? pictures[0];
  const app = product.product_type === "app";
  const onSite = `/b/${brandId}/library/products/${product.id}`;
  return (
    <aside className="phero" aria-label="The product">
      <div className="hero">{big ? <img src={fileUrl(big.file_id)} alt={`${product.name}: ${big.variant || big.name}`} /> : <span>No {app ? "screens" : "photo"} yet</span>}</div>
      {pictures.length > 1 && (
        <div className="thumbs" role="group" aria-label={app ? "Its screens" : "Its photos"}>
          {pictures.map((p) => (
            <button key={p.screen_id} type="button" aria-label={p.variant || p.name} aria-pressed={p === big} onClick={() => setShown(p.file_id)}>
              <img src={fileUrl(p.file_id)} alt="" loading="lazy" />
            </button>
          ))}
        </div>
      )}
      <h2>{product.name}</h2>
      {product.short_description && <p className="line">{product.short_description}</p>}
      {product.main_claim && (
        <p className="line">
          <em>Main claim</em> {product.main_claim}
        </p>
      )}
      {!app && (
        <div className="offers">
          <button type="button" className="btn soft" disabled={add.isPending} onClick={() => photo.current?.click()}>
            <Plus {...ICON} size={14} />
            {add.isPending ? "Adding…" : "Add a photo"}
          </button>
          {big && (
            <button type="button" className="btn ghost" disabled={remove.isPending} onClick={() => remove.mutate(big)}>
              <Trash2 {...ICON} size={14} />
              Remove this photo
            </button>
          )}
        </div>
      )}
      <input ref={photo} type="file" hidden aria-label={`Add a photo of ${product.name}`} accept="image/*" onChange={(e) => (e.target.files?.[0] && add.mutate(e.target.files[0]), (e.target.value = ""))} />
      {(add.error ?? remove.error) && (
        <p className="hint bad" role="alert">
          {(add.error ?? remove.error)!.message}
        </p>
      )}
      <HowItWorks item={product} />
      {app && (
        <p className="hint also">
          Adding and naming its screens is on <Link to={onSite}>the current site</Link>.
        </p>
      )}
      {more}
    </aside>
  );
}

/** New product (free): its name, whether it is a thing or an app, and its real photo or screens. */
function NewProduct({ brandId, onMade, onClose }: { brandId: number; onMade: (id: number) => void; onClose: () => void }) {
  const [name, setName] = useState("");
  const [type, setType] = useState<"physical" | "app">("physical");
  const [files, setFiles] = useState<File[]>([]);
  const { create, locked } = useCreateItem(brandId, "prop", (id) => (onMade(id), onClose()));
  return (
    <Dialog title="New product" confirm="Save product" busy={!name.trim() || create.isPending} onClose={onClose} onConfirm={() => create.mutate({ name, words: "", photo: files[0] ?? null, more: files.slice(1), type })}>
      <label className="dlab">
        Name
        <input data-autofocus value={name} maxLength={120} disabled={locked} onChange={(e) => setName(e.target.value)} />
      </label>
      <div className="drow">
        <span>It is</span>
        <div className="seg" role="group" aria-label="It is">
          {(["physical", "app"] as const).map((t) => (
            <button key={t} type="button" aria-pressed={t === type} disabled={locked} onClick={() => (setType(t), setFiles(files.slice(0, 1)))}>
              {t === "app" ? "An app" : "A physical thing"}
            </button>
          ))}
        </div>
      </div>
      <FileRow label={type === "app" ? "Upload its screens" : "Upload its photo"} note={type === "app" ? "Shown as given; numbers follow the story." : "Shown exactly as it is. You can add it later."} accept="image/*" multiple={type === "app"} file={files.map((f) => f.name).join(", ")} onPick={setFiles} />
      <p className="hint">Saving is free.</p>
      {create.isError && (
        <p className="dsub bad" role="alert">
          {create.error.message}
        </p>
      )}
    </Dialog>
  );
}
