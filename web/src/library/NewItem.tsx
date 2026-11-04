import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, Upload } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, errorText } from "../api/client";
import { uploadFile } from "../api/upload";
import { Button } from "../components";
import { refreshJobs } from "../jobs/refresh";
import { errorText as errorClass } from "../ui";
import { SHEET_MODEL } from "./sheets";
import { KINDS, slugOf, upTo, useNewPrice, type Item, type Kind } from "./kinds";
import { addPicture } from "./products";

const field = "h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-base text-text placeholder:text-muted lg:text-sm";

/** New character / place (S8-07, left) and New product (S-gaps-05 L1): a name and a description, or a photo. A character or place is
 *  drawn as a front, side and back sheet with the price first; the tiles shimmer while it's drawn, then its page opens.
 *  A product is an app (a name and its screens) or a physical thing (a name, what must read right, and its real photo);
 *  saving it is free. */
export function NewItem({ brandId, kind, photo: picked, onClose }: { brandId: number; kind: Kind; photo: File | null; onClose: () => void }) {
  const { one } = KINDS[slugOf(kind)];
  const [name, setName] = useState("");
  const [words, setWords] = useState("");
  const [photo, setPhoto] = useState<File | null>(picked);
  const [more, setMore] = useState<File[]>([]); // an app's other screens
  const [type, setType] = useState<"app" | "physical">("physical");
  const [made, setMade] = useState<number | null>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const price = useNewPrice(kind);
  const cost = upTo(price.data?.credits, price.data?.usd);
  const preview = usePreview(photo);
  const product = kind === "prop";
  const create = useMutation({
    mutationFn: async () => {
      const source = photo && !product ? (await uploadFile(photo)).id : null;
      const { data, error } = await api.POST("/library/{kind}", {
        params: { path: { kind } },
        body: { name: name.trim(), notes: words.trim(), brand_ids: [brandId], image_file_ids: [], outfits: [], source_photo_file_id: source, presenter: false, product_type: product ? type : null },
      });
      if (!data) throw new Error(errorText(error));
      if (product) {
        for (const [n, f] of [photo, ...more].filter((f): f is File => !!f).entries()) {
          await addPicture(brandId, { ...data, pictures: Array(n).fill(null) } as Item, f, "", type === "app" ? screenName(f.name) : undefined);
        }
        return data.id;
      }
      const sheet = await api.POST("/library/{kind}/{item_id}/sheet", { params: { path: { kind, item_id: data.id } }, body: { model_id: SHEET_MODEL, change: "" } });
      if (!sheet.data) throw new Error(errorText(sheet.error));
      return data.id;
    },
    onSuccess: (id) => {
      void queryClient.invalidateQueries({ queryKey: ["library", kind] });
      if (product) return onClose();
      refreshJobs(queryClient);
      setMade(id);
    },
  });
  // The new sheet as it's drawn: its page opens once it's in (or waits for the owner's OK).
  const item = useQuery({
    enabled: made !== null,
    queryKey: ["library", kind, "item", made],
    queryFn: async () => (await api.GET("/library/{kind}/{item_id}", { params: { path: { kind, item_id: made! } } })).data ?? null,
    refetchInterval: (q) => (q.state.data?.sheet_status === "drawing" ? 2000 : false),
  });
  const drawing = create.isPending || (made !== null && (!item.data || item.data.sheet_status === "drawing"));
  useEffect(() => {
    if (made !== null && item.data && item.data.sheet_status !== "drawing") navigate(`/b/${brandId}/library/${slugOf(kind)}/${made}`);
  }, [made, item.data, brandId, kind, navigate]);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (name.trim() && (product || photo || words.trim())) create.mutate();
  };
  const ready = !!name.trim() && (product || !!photo || !!words.trim());
  return (
    <form onSubmit={submit} className="flex w-full max-w-[620px] flex-col gap-3" aria-label={`New ${one}`}>
      <h2 className="text-lg font-semibold">New {one}</h2>
      {!product && (
        <div className="flex gap-3">
          {[0, 1, 2].map((n) =>
            n === 0 && preview && !drawing ? (
              <img key={n} src={preview} alt="The photo" className="h-[190px] w-[140px] rounded-md object-cover" />
            ) : (
              <span key={n} aria-hidden className={`h-[190px] w-[140px] rounded-md ${drawing ? "bg-[linear-gradient(110deg,var(--surface-2)_30%,var(--surface-3)_45%,var(--surface-2)_60%)] motion-safe:animate-pulse" : "bg-surface-2"}`} />
            ),
          )}
        </div>
      )}
      {drawing && !product ? (
        <p className="flex items-center gap-2 text-sm text-muted" role="status">
          <LoaderCircle size={14} strokeWidth={1.75} aria-hidden className="motion-safe:animate-spin" />
          Drawing a front, side and back sheet from your {photo ? "photo" : "description"}{cost && ` · ${cost}`} · about 30 s
        </p>
      ) : (
        <>
          <label className="block text-sm">
            <span className="sr-only">Name</span>
            <input className={field} required placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} data-autofocus />
          </label>
          <label className="block text-sm">
            <span className="sr-only">{product ? "What must read right" : "Description"}</span>
            <input className={field} value={words} onChange={(e) => setWords(e.target.value)} placeholder={product ? (type === "app" ? "Always the real UI; numbers can be made up" : "The label must read right: the brand, the claim, the flavour") : kind === "place" ? "“A small kitchen at night, one warm lamp”" : "“Woman, late 30s, glasses, cardigan, tired but kind”"} />
          </label>
          {product && (
            <div role="radiogroup" aria-label="It's" className="inline-flex gap-0.5 self-start rounded-md bg-surface-2 p-0.5">
              {(["physical", "app"] as const).map((t) => (
                <button key={t} type="button" role="radio" aria-checked={type === t} onClick={() => setType(t)} className={`min-h-control rounded-[5px] px-3 text-sm lg:min-h-8 ${type === t ? "bg-surface font-medium shadow-sm" : "text-muted"}`}>
                  {t === "app" ? "An app" : "A physical thing"}
                </button>
              ))}
            </div>
          )}
          {(product || photo) && (
            <p className="text-sm text-muted">
              {photo ? `${type === "app" && product ? "Screens" : "Photo"}: ${[photo, ...more].map((f) => f.name).join(", ")}` : type === "app" ? "An app holds its screens, shown as given; numbers follow the story." : "No photo yet. The director asks for it when a video needs it."}
            </p>
          )}
          {create.isError && <p role="alert" className={errorClass}>{create.error.message}</p>}
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" disabled={!ready} busy={create.isPending} reason={!ready ? (product ? "Name it first" : "Name it, then describe it or add a photo") : null}>
              {product ? "Save product" : "Make it"}
              {!product && cost && <>{" "}<span className="opacity-80">· {cost}</span></>}
            </Button>
            <label className="inline-flex min-h-control cursor-pointer items-center gap-1.5 rounded-md border border-border-button px-3 text-sm font-medium lg:min-h-control-dense">
              <Upload size={16} strokeWidth={1.75} aria-hidden />
              {product && type === "app" ? "Upload screens" : photo ? "Another photo" : "Upload a photo"}
              <input type="file" accept="image/*" multiple={product && type === "app"} className="sr-only" onChange={(e) => { const fs = [...(e.target.files ?? [])]; if (fs.length) { setPhoto(fs[0]); setMore(fs.slice(1)); } }} />
            </label>
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
          </div>
          {product && <p className="text-sm text-muted">Saving is free.</p>}
        </>
      )}
    </form>
  );
}

/** "order-tracking.png" reads "Order tracking". */
const screenName = (file: string) => {
  const words = file.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
};

/** A picked photo as a picture to show before it's uploaded. */
export function usePreview(file: File | null) {
  const url = useMemo(() => (file && URL.createObjectURL ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => void (url && URL.revokeObjectURL(url)), [url]);
  return url;
}
