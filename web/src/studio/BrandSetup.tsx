import { useEffect, useRef, useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Plus } from "lucide-react";
import { Link, useBlocker, useNavigate, useParams } from "react-router-dom";
import { api, errorText, must } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { useSaved } from "../home/useDraft";
import type { Item } from "../library/kinds";
import { addPicture } from "../library/products";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { Dialog } from "./Dialog";
import "./settings.css";

type Brand = components["schemas"]["BrandOut"];
type Kit = { name: string; colour: string; tone: string };
/** A product not saved yet: its name, how it works, and the photos picked for it. */
type Draft = { name: string; how: string; files: File[] };

const SWATCHES = [["#EF8A3C", "Orange"], ["#F2707A", "Coral"], ["#D55181", "Pink"], ["#8F92FF", "Violet"], ["#5AA9E6", "Blue"], ["#1F9FB5", "Teal"], ["#58D39B", "Green"], ["#F2B84B", "Yellow"]];
const NO_DRAFT: Draft = { name: "", how: "", files: [] };
const kitOf = (b?: Brand): Kit => ({ name: b?.name ?? "", colour: b ? (b.colours[0] ?? "") : SWATCHES[0][0], tone: b?.tone_notes ?? "" });

/** A new brand (/s/brands/new) and a brand's set-up (/s/b/:brandId/setup), one page in the new look (the redesign,
 *  stage 6): its name and colour, its product (photos, and how it works), its tone and rules, and beside them what the
 *  director has so far. Every save is a request the current site sends: the brand as New brand and the Brand kit send
 *  it, the product as the Library does. */
export function BrandSetup() {
  const id = Number(useParams().brandId) || null;
  const brands = useBrands().data;
  const me = useMe().data;
  const brand = brands?.find((b) => b.id === id);
  if (me && me.role !== "owner") return <p className="none">Only the owner sets up brands.</p>;
  if (id && brands && !brand) return <p className="none">That brand doesn’t exist.</p>;
  if (id && !brand) return null;
  return <Form key={id ?? "new"} brand={brand} />;
}

function Form({ brand }: { brand?: Brand }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [saved, setSaved] = useState(() => kitOf(brand));
  const [kit, setKit] = useState(saved);
  const [draft, setDraft] = useState(NO_DRAFT);
  const [notes, setNotes] = useState<Record<number, string>>({}); // "How it works" as typed, by product, until it is saved
  const [made, setMade] = useState<Brand | null>(null); // a new brand already made, when its product then failed
  const saving = useRef<{ item: Item | null; pictures: number }>({ item: null, pictures: 0 }); // a retry goes on from here
  const leaving = useRef(false);
  const list = useSaved("prop", brand?.id ?? 0);
  const products = list.data ?? [];
  const fresh = (...keys: string[][]) => Promise.all(keys.map((queryKey) => queryClient.invalidateQueries({ queryKey })));

  const changed = JSON.stringify(kit) !== JSON.stringify(saved);
  const named = kit.name.trim() !== "";
  const nameless = !draft.name.trim() && (draft.how.trim() !== "" || draft.files.length > 0); // a product with no name can't be saved
  const dirty = (brand ? changed : kit.name !== "" || kit.tone !== "") || draft.name !== "" || draft.how !== "" || draft.files.length > 0 || Object.keys(notes).length > 0;
  // Leaving with something typed and not saved asks first, as the Brand kit does.
  const away = useBlocker(({ currentLocation, nextLocation }) => dirty && !leaving.current && currentLocation.pathname !== nextLocation.pathname);

  /** The product as the Library's New product saves it (a physical thing), then each photo as one of its pictures. */
  const saveProduct = async (brandId: number) => {
    if (!draft.name.trim()) return;
    const at = saving.current;
    if (!at.item) {
      const sent = await api.POST("/library/{kind}", { params: { path: { kind: "prop" } }, body: { name: draft.name.trim(), notes: draft.how, brand_ids: [brandId], image_file_ids: [], outfits: [], source_photo_file_id: null, presenter: false, product_type: "physical" } });
      if (!sent.data) throw new Error(errorText(sent.error));
      at.item = sent.data;
    }
    for (let n = at.pictures; n < draft.files.length; n++) {
      await addPicture(brandId, { ...at.item, pictures: Array(n).fill(null) } as Item, draft.files[n]);
      at.pictures = n + 1;
    }
  };
  /** The brand as the current New brand page sends it, with the tone typed here. */
  const newBrand = async () => {
    const sent = await api.POST("/brands", { body: { name: kit.name.trim(), logo_file_id: null, colours: [kit.colour], tone_notes: kit.tone } });
    if (!sent.data) throw new Error(errorText(sent.error));
    setMade(sent.data);
    return sent.data;
  };
  const create = useMutation({
    mutationFn: async () => {
      const b = made ?? (await newBrand());
      await saveProduct(b.id).catch((e: Error) => Promise.reject(new Error(`${b.name} is made, but its product is not saved yet. ${e.message}`)));
      return b;
    },
    onSuccess: async (b) => {
      await fresh(["brands"], ["usage"]);
      leaving.current = true;
      navigate(`/s/b/${b.id}`);
      toast(`${b.name} is ready. Paste a script to make its first video.`);
    },
  });
  const write = async (k: Kit) => {
    await must(api.PATCH("/brands/{brand_id}", { params: { path: { brand_id: brand!.id } }, body: { name: k.name, logo_file_id: brand!.logo_file_id ?? null, colours: [k.colour, ...brand!.colours.slice(1)].filter(Boolean), tone_notes: k.tone } }));
    await fresh(["brands"]);
    setSaved(k);
    setKit(k);
  };
  const saveKit = useMutation({
    mutationFn: async () => {
      await write({ ...kit, name: kit.name.trim() });
      return saved;
    },
    onSuccess: (before) => toast("Saved.", () => void write(before).catch((e: Error) => toast(e.message, undefined, "error"))),
  });
  const addProduct = useMutation({
    mutationFn: () => saveProduct(brand!.id),
    onSuccess: async () => {
      await fresh(["library", "prop"]);
      saving.current = { item: null, pictures: 0 };
      setDraft(NO_DRAFT);
      toast("Saved.");
    },
  });
  const addPhoto = useMutation({ mutationFn: (a: { item: Item; file: File }) => addPicture(brand!.id, a.item, a.file), onSuccess: () => fresh(["library", "prop"]) });
  /** "How it works" is the product's own notes field, sent exactly as typed and only on this press; the rest of the
   *  body is the product as it stands, as the Library's own form sends it. */
  const saveNotes = useMutation({
    mutationFn: (p: Item) => must(api.PATCH("/library/{kind}/{item_id}", { params: { path: { kind: "prop", item_id: p.id } }, body: { name: p.name, notes: notes[p.id], brand_ids: p.brand_ids, short_description: p.short_description ?? "", main_claim: p.main_claim ?? "" } })),
    onSuccess: async (_sent, p) => {
      await fresh(["library", "prop"]);
      setNotes((was) => Object.fromEntries(Object.entries(was).filter(([id]) => Number(id) !== p.id)));
      toast("Saved.");
    },
  });

  const colours = SWATCHES.some(([hex]) => hex.toLowerCase() === saved.colour.toLowerCase()) || !saved.colour ? SWATCHES : [[saved.colour, "The colour it has now"], ...SWATCHES];
  const has: [string, boolean][] = [
    ["Name and colour", named],
    ["The product", products.length > 0 || draft.name.trim() !== ""],
    ["A photo of it", products.some((p) => p.pictures.length > 0) || draft.files.length > 0],
    ["How it works", products.some((p) => (notes[p.id] ?? p.notes).trim() !== "") || draft.how.trim() !== ""],
    ["Tone and rules", kit.tone.trim() !== ""],
  ];
  const why = !named ? "Give the brand a name first." : nameless ? "Give the product a name first." : null;
  const productProblem = [addProduct, addPhoto, saveNotes].find((m) => m.isError)?.error?.message;
  const kitProblem = (brand ? saveKit : create).error?.message;
  const add = (label: string, many: boolean, onFiles: (files: File[]) => void) => (
    <label className="addt">
      <Plus size={16} strokeWidth={1.75} aria-hidden />
      <span>Photo</span>
      <input type="file" accept="image/*" multiple={many} className="vh" aria-label={label} onChange={(e) => (onFiles([...(e.target.files ?? [])]), (e.target.value = ""))} />
    </label>
  );
  const how = (id: string, value: string, onChange: (text: string) => void) => (
    <>
      <label className="lab2" htmlFor={id}>
        How it works
      </label>
      <textarea id={id} rows={4} value={value} onChange={(e) => onChange(e.target.value)} placeholder="In your own words. “You pull the pin out of the top and it screams.”" />
      <p className="hint">The director reads this whenever the product is on screen. It is kept exactly as you type it.</p>
    </>
  );

  return (
    <>
      <header className="head">
        <Link className="crumb" to="/s/settings">
          Settings
        </Link>
        <span aria-hidden className="slash">
          /
        </span>
        <h1 className="clip">{brand ? `Set up ${brand.name}` : "New brand"}</h1>
      </header>
      <div className="view">
        <div className="page nbpage">
          <div className="nbform">
            <Part title="Name and colour" why="Everything you make is kept under the brand. Nothing saved here shows up in another brand.">
              <input className="field wide" aria-label="Brand name" placeholder="Brand name" maxLength={80} disabled={!!made} value={kit.name} onChange={(e) => setKit({ ...kit, name: e.target.value })} />
              <div className="swatches" role="group" aria-label="Colour">
                {colours.map(([hex, name]) => (
                  <button key={hex} type="button" aria-label={name} title={name} aria-pressed={kit.colour.toLowerCase() === hex.toLowerCase()} disabled={!!made} style={{ background: hex }} onClick={() => setKit({ ...kit, colour: hex })} />
                ))}
              </div>
            </Part>
            <Part title="The product" why="The real thing, shown exactly as it is whenever a shot shows it.">
              {products.map((p) => (
                <div key={p.id} className="prod">
                  <h3>{p.name}</h3>
                  <div className="addrow">
                    {p.pictures.map((x) => (
                      <img key={x.screen_id} className="addt" src={fileUrl(x.file_id)} alt={x.name} />
                    ))}
                    {add(`Add a photo of ${p.name}`, false, ([file]) => file && addPhoto.mutate({ item: p, file }))}
                  </div>
                  {how(`how-${p.id}`, notes[p.id] ?? p.notes, (text) => setNotes({ ...notes, [p.id]: text }))}
                  <button type="button" className="btn soft" disabled={notes[p.id] === undefined || notes[p.id] === p.notes || saveNotes.isPending} onClick={() => saveNotes.mutate(p)}>
                    Save how it works
                  </button>
                </div>
              ))}
              {(!brand || (list.isSuccess && products.length === 0)) && (
                <div className="prod">
                  <input className="field wide" aria-label="Product name" placeholder="What the product is called" maxLength={120} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
                  <div className="addrow">
                    {draft.files.map((f, n) => (
                      <Picked key={n} file={f} onRemove={() => setDraft({ ...draft, files: draft.files.filter((_, k) => k !== n) })} />
                    ))}
                    {add("Add photos of the product", true, (files) => setDraft({ ...draft, files: [...draft.files, ...files] }))}
                  </div>
                  {how("how-new", draft.how, (text) => setDraft({ ...draft, how: text }))}
                  {brand && (
                    <button type="button" className="btn soft" disabled={!draft.name.trim() || addProduct.isPending} onClick={() => addProduct.mutate()}>
                      Save the product
                    </button>
                  )}
                </div>
              )}
              {productProblem && (
                <p role="alert" className="hint bad">
                  {productProblem}
                </p>
              )}
            </Part>
            <Part title="Tone and rules" why="How the brand talks, and anything it never does.">
              <textarea aria-label="Tone and rules" rows={3} disabled={!!made} value={kit.tone} onChange={(e) => setKit({ ...kit, tone: e.target.value })} placeholder="Plain and urgent. Never jokes about safety." />
            </Part>
            <p className="quiet why">People, voices and clips of the product in use are kept in the {brand ? <Link to={`/s/b/${brand.id}/library`}>Library</Link> : "Library, once the brand is made"}.</p>
          </div>
          <aside className="nbcard" aria-label="What the director has">
            <span className="lab">How it will look</span>
            <div className="chip">
              <i aria-hidden className="sq" style={{ background: kit.colour || "var(--accent)" }} />
              <b className="clip">{kit.name.trim() || "Brand name"}</b>
            </div>
            <span className="lab">What the director has</span>
            <ul className="ready">
              {has.map(([name, ok]) => (
                <li key={name} className={ok ? "ok" : undefined}>
                  <i aria-hidden>
                    <Check size={14} strokeWidth={2} />
                  </i>
                  {name}
                  {ok && <span className="vh">, added</span>}
                </li>
              ))}
            </ul>
            <p className="hint">A name is enough to make a video. Each thing you add is one less question from the director.</p>
            {brand ? (
              <button type="button" className="btn go" disabled={!changed || !named || saveKit.isPending} onClick={() => saveKit.mutate()}>
                Save changes
              </button>
            ) : (
              <button type="button" className="btn go" disabled={!!why || create.isPending || create.isSuccess} onClick={() => create.mutate()}>
                {made ? "Try again" : "Create brand"}
              </button>
            )}
            {!brand && why && <p className="hint">{why}</p>}
            {kitProblem && (
              <p role="alert" className="hint bad">
                {kitProblem}
              </p>
            )}
          </aside>
        </div>
      </div>
      {away.state === "blocked" && (
        <Dialog title="Leave without saving?" confirm="Leave" onConfirm={() => away.proceed()} onClose={() => away.reset()}>
          <p className="dsub">What you typed here isn’t saved. Leaving drops it.</p>
        </Dialog>
      )}
    </>
  );
}

function Part({ title, why, children }: { title: string; why: string; children: ReactNode }) {
  return (
    <section aria-label={title}>
      <h2>{title}</h2>
      <p className="why">{why}</p>
      {children}
    </section>
  );
}

/** A photo picked for a product that isn't saved yet: a press takes it out again. */
function Picked({ file, onRemove }: { file: File; onRemove: () => void }) {
  const img = useRef<HTMLImageElement>(null);
  useEffect(() => {
    const url = URL.createObjectURL(file);
    if (img.current) img.current.src = url;
    return () => URL.revokeObjectURL(url);
  }, [file]);
  return (
    <button type="button" className="addt" aria-label={`Remove ${file.name}`} title="Remove" onClick={onRemove}>
      <img ref={img} alt="" />
    </button>
  );
}
