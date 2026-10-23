import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl, uploadFile } from "../api/upload";
import { btnPrimary, errorText as errorClass, input, linkText, pageTitle } from "../ui";

const ASPECTS = ["9:16", "1:1", "16:9", "4:3", "3:4", "21:9"] as const;
const PLATFORMS = ["TikTok", "Instagram Reels", "YouTube Shorts", "Other"];

/** The brief: a few lines is enough. Claude turns it into a script in the next step. */
export function NewProjectPage() {
  const brandId = Number(useParams().brandId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: "", goal: "", platform: PLATFORMS[0], aspect: "9:16" as (typeof ASPECTS)[number], format: "", seconds: 30 });
  const [cast, setCast] = useState<number[]>([]);
  const [picks, setPicks] = useState<Record<string, string>>({});
  const [reference, setReference] = useState<number | null>(null);
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm({ ...form, [k]: v });

  const characters = useQuery({
    queryKey: ["library", "character", brandId, false],
    queryFn: async () => (await api.GET("/library/{kind}", { params: { path: { kind: "character" }, query: { brand_id: brandId } } })).data ?? [],
  });
  const screens = useQuery({
    queryKey: ["screens", brandId],
    queryFn: async () => (await api.GET("/brands/{brand_id}/screens", { params: { path: { brand_id: brandId } } })).data ?? [],
  });
  // Screens that are one flavour of a product (a bag that comes in Chicken or Peanut butter) are picked here.
  const products = new Map<string, NonNullable<typeof screens.data>>();
  for (const s of screens.data ?? []) if (s.product && s.variant) products.set(s.product, [...(products.get(s.product) ?? []), s]);
  // A flavour has to be chosen; a product with only one is chosen for you.
  const chosen = (product: string) => picks[product] ?? (products.get(product)?.length === 1 ? products.get(product)![0].variant : undefined);
  const unchosen = [...products.keys()].find((p) => !chosen(p));
  const limits = useQuery({ queryKey: ["limits"], queryFn: async () => (await api.GET("/credits/limits")).data ?? null });
  const longest = limits.data ? Math.floor(limits.data.per_video_max_credits / 2) : 170; // budget is 2x the 480p seconds

  const upload = useMutation({ mutationFn: uploadFile, onSuccess: (f) => setReference(f.id) });
  const create = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects", {
        body: {
          brand_id: brandId,
          name: form.name,
          planned_seconds: form.seconds,
          goal: form.goal,
          platform: form.platform,
          aspect_ratio: form.aspect,
          format: form.format,
          cast_ids: cast,
          reference_file_id: reference,
          product_variants: Object.fromEntries([...products.keys()].map((p) => [p, chosen(p)!])),
        },
      });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (p) => {
      await queryClient.invalidateQueries({ queryKey: ["projects", brandId] });
      navigate(`/b/${brandId}/projects/${p.id}`);
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  const seg = (on: boolean) => `min-h-11 rounded-sm border px-3 sm:min-h-9 ${on ? "border-accent bg-accent-soft text-accent-text" : "border-border-strong bg-surface"}`;

  return (
    <main className="mx-auto max-w-2xl space-y-4 p-4 sm:p-6">
      <Link to={`/b/${brandId}/projects`} className={linkText}>
        ← Projects
      </Link>
      <h1 className={pageTitle}>New video</h1>
      <p className="text-muted">What's this video for? A few lines is enough. Claude turns it into a script.</p>
      <form onSubmit={submit} className="space-y-5">
        <label className="block text-sm">
          Title
          <input className={input} required maxLength={120} value={form.name} onChange={(e) => set("name", e.target.value)} />
        </label>
        <label className="block text-sm">
          What's it for?
          <textarea className={input} rows={4} value={form.goal} onChange={(e) => set("goal", e.target.value)} />
        </label>
        <label className="block text-sm">
          Where will it be posted?
          <select className={input} value={form.platform} onChange={(e) => set("platform", e.target.value)}>
            {PLATFORMS.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <fieldset className="space-y-1 text-sm">
          <legend className="font-medium">Shape</legend>
          <div className="flex flex-wrap gap-2">
            {ASPECTS.map((a) => (
              <button key={a} type="button" aria-pressed={a === form.aspect} className={seg(a === form.aspect)} onClick={() => set("aspect", a)}>
                {a}
              </button>
            ))}
          </div>
        </fieldset>
        <label className="block text-sm">
          Kind of video (optional)
          <input className={input} list="formats" placeholder="e.g. story, product ad" value={form.format} onChange={(e) => set("format", e.target.value)} />
          <datalist id="formats">
            {["Story", "Product ad", "Explainer", "Meme"].map((f) => (
              <option key={f} value={f} />
            ))}
          </datalist>
        </label>
        <label className="block text-sm">
          Planned length (seconds)
          <input className={input} type="number" required min={1} max={longest} value={form.seconds} onChange={(e) => set("seconds", Number(e.target.value))} />
          <span className="block text-muted">Budget: {form.seconds * 2} credits (twice the length).</span>
        </label>
        <fieldset className="space-y-1 text-sm">
          <legend className="font-medium">Who's in it</legend>
          {characters.data?.length === 0 && <p className="text-muted">No characters for this brand yet. Add them in the Library.</p>}
          {characters.data?.map((c) => (
            <label key={c.id} className="mr-4 inline-flex items-center gap-2">
              <input type="checkbox" checked={cast.includes(c.id)} onChange={() => setCast(cast.includes(c.id) ? cast.filter((x) => x !== c.id) : [...cast, c.id])} />
              {c.name}
            </label>
          ))}
        </fieldset>
        {[...products].map(([product, list]) => (
          <fieldset key={product} className="space-y-1 text-sm">
            <legend className="font-medium">{product.charAt(0).toUpperCase() + product.slice(1)}</legend>
            <div className="flex flex-wrap gap-3">
              {list.map((s) => {
                const on = chosen(product) === s.variant;
                return (
                  <button
                    key={s.id}
                    type="button"
                    aria-pressed={on}
                    className={`w-28 overflow-hidden rounded-md bg-surface text-left ${on ? "border-2 border-accent" : "border border-border-strong"}`}
                    onClick={() => setPicks({ ...picks, [product]: s.variant })}
                  >
                    <img src={fileUrl(s.file_id)} alt="" className="aspect-square w-full object-cover" />
                    <span className="block min-h-11 p-2 sm:min-h-0">{s.variant}</span>
                  </button>
                );
              })}
            </div>
          </fieldset>
        ))}
        <div className="space-y-1 text-sm">
          <div className="font-medium">Reference video (optional)</div>
          {reference && <video controls src={fileUrl(reference)} className="max-h-48 rounded-sm" />}
          <div className="flex gap-3">
            <label className={`cursor-pointer ${linkText}`}>
              {reference ? "Replace" : "Add a video"}
              <input type="file" accept="video/*" className="sr-only" aria-label="Reference video file" onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])} />
            </label>
            {reference && (
              <button type="button" className={linkText} onClick={() => setReference(null)}>
                Remove
              </button>
            )}
            {upload.isPending && <span className="text-muted">Uploading…</span>}
          </div>
          {upload.isError && <p role="alert" className={errorClass}>{upload.error.message}</p>}
        </div>
        {create.isError && <p role="alert" className={errorClass}>{create.error.message}</p>}
        <button className={btnPrimary} disabled={create.isPending || !!unchosen}>
          Create project
        </button>
        {unchosen && <p className="text-sm text-muted">Pick which {unchosen} first.</p>}
      </form>
    </main>
  );
}
