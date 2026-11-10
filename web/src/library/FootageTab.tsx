import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRightLeft, Film, Pencil, Plus, Trash2, Upload } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Badge, Banner, Button, Select, Skeleton, TextArea, useToast } from "../components";
import { Crumbs, FolderActions, MoveClip, SubFolders, trail, useFootageFolders, type FootageFolder } from "./FootageFolders";
import { LibraryFrame, useSearch } from "./LibraryFrame";
import { upTo, useItems } from "./kinds";

export type Footage = components["schemas"]["FootageOut"];
const path = (brandId: number) => ({ params: { path: { brand_id: brandId } } });

/** The brand's real clips (Reed, 9 Nov): polled while the AI is still describing one. Shared with the tab's count. */
export function useFootage(brandId: number) {
  return useQuery({
    queryKey: ["footage", brandId],
    queryFn: async () => (await must(api.GET("/brands/{brand_id}/footage", path(brandId)))).data!,
    enabled: brandId > 0,
    refetchInterval: (q) => (q.state.data?.some((c) => c.describing) ? 2000 : false),
  });
}

const length = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

/** Footage (Reed, 9 Nov): real clips of the brand's products, added once, each with what it shows and which product. Every
 *  video's director reads the ones that fit; in UGC it may use one as a B-roll shot. In folders, nested as in Reed's Drive
 *  (10 Nov): the open one's folders and clips; a search looks in every folder. */
export function FootageTab({ brandId }: { brandId: number }) {
  const [params, setParams] = useSearchParams();
  const adding = params.get("new") === "1";
  const setAdding = (on: boolean) => setParams((p) => (on ? p.set("new", "1") : p.delete("new"), p), { replace: true });
  const clips = useFootage(brandId);
  const rows = useFootageFolders(brandId).data ?? [];
  const asked = Number(params.get("folder")) || null;
  const at = rows.some((f) => f.id === asked) ? asked : null; // a folder that's gone: the top
  const open = (id: number | null) => setParams((p) => (id ? p.set("folder", String(id)) : p.delete("folder"), p));
  const [q] = useSearch();
  const words = q.trim().toLowerCase();
  const all = clips.data ?? [];
  const shown = words ? all.filter((c) => `${c.description} ${c.folder}`.toLowerCase().includes(words)) : all.filter((c) => (c.folder_id ?? null) === at);
  const here = rows.some((f) => (f.parent_id ?? null) === at);
  const action = !adding && (
    <Button icon={Plus} onClick={() => setAdding(true)}>
      Add a clip
    </Button>
  );
  return (
    <LibraryFrame brandId={brandId} tab="footage" action={action} onAdd={() => setAdding(true)} addLabel="Add a clip">
      <div className="mx-auto flex max-w-content flex-col gap-6">
        {clips.isError && <Banner title="Couldn't load the footage." action={<Button variant="secondary" onClick={() => void clips.refetch()}>Try again</Button>}>Check your connection.</Banner>}
        {adding && <AddClip brandId={brandId} folder={trail(rows, at).map((f) => f.name).join("/")} onClose={() => setAdding(false)} />}
        {clips.isPending ? (
          <Skeleton className="h-48 w-full max-w-[280px]" />
        ) : all.length === 0 && rows.length === 0 && !adding ? (
          <section aria-label="No footage yet" className="flex max-w-[560px] flex-col items-start gap-3 rounded-lg border border-border bg-surface p-6">
            <Film size={20} strokeWidth={1.75} aria-hidden className="text-muted" />
            <h2 className="text-md font-semibold">No footage yet</h2>
            <p className="text-sm text-muted">Add real clips of your products once, each with what it shows. Every video’s director sees how the product looks and works; in UGC it can use a clip as a B-roll shot.</p>
            <Button icon={Upload} onClick={() => setAdding(true)}>Add a clip</Button>
          </section>
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              {words ? <p className="text-sm text-muted">Every folder, searched for “{q}”</p> : <Crumbs rows={rows} at={at} open={open} />}
              <FolderActions brandId={brandId} rows={rows} footage={all} at={at} open={open} />
            </div>
            {!words && <SubFolders rows={rows} footage={all} at={at} open={open} />}
            {shown.length === 0 && (words || !here) && <p className="text-sm text-muted">{words ? `No clip says “${q}”.` : "No clips in this folder yet."}</p>}
            <ul aria-label="Footage" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {shown.map((c) => (
                <ClipCard key={c.id} brandId={brandId} clip={c} rows={rows} where={words ? c.folder : ""} />
              ))}
            </ul>
          </>
        )}
      </div>
    </LibraryFrame>
  );
}

function ProductPicker({ brandId, value, onChange }: { brandId: number; value: number | null; onChange: (id: number | null) => void }) {
  const products = useItems("prop", brandId).data ?? [];
  return (
    <Select label="Product" hint="Which of the brand’s products it shows." value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
      <option value="">No product</option>
      {products.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name}
        </option>
      ))}
    </Select>
  );
}

/** Add a clip: the file, then what it shows (left empty, the AI describes it from two of its frames, at the price shown) and
 *  its product. Media's checks: an MP4 or WebM of up to 3 minutes. */
function AddClip({ brandId, folder, onClose }: { brandId: number; folder: string; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [words, setWords] = useState("");
  const [product, setProduct] = useState<number | null>(null);
  const price = useQuery({ queryKey: ["footage", "price", brandId], queryFn: async () => (await api.GET("/brands/{brand_id}/footage/price", path(brandId))).data ?? null });
  const queryClient = useQueryClient();
  const toast = useToast();
  const add = useMutation({
    mutationFn: async () => {
      const form = new FormData();
      form.append("upload", file!);
      form.append("description", words.trim());
      form.append("folder", folder);
      if (product !== null) form.append("product_id", String(product));
      return must(api.POST("/brands/{brand_id}/footage", { ...path(brandId), body: { upload: "", description: "", product: "", folder, ai_describe: true }, bodySerializer: () => form })).then((r) => r.data!);
    },
    onSuccess: async (c) => {
      await queryClient.invalidateQueries({ queryKey: ["footage", brandId] });
      void queryClient.invalidateQueries({ queryKey: ["media"] });
      toast(c.describing ? "Clip added. Describing what it shows…" : "Clip added.");
      onClose();
    },
  });
  const ai = !words.trim();
  return (
    <section aria-label="Add a clip" className="flex max-w-[560px] flex-col gap-4 rounded-lg border border-border bg-surface p-4 sm:p-6">
      <div>
        <h2 className="text-md font-semibold">Add a clip</h2>
        <p className="text-sm text-muted">To {folder || "All footage (the top)"}</p>
      </div>
      <label className="inline-flex min-h-control w-fit cursor-pointer items-center gap-2 rounded-md border border-border-button px-3 text-sm font-medium focus-within:ring-2 focus-within:ring-accent lg:min-h-control-dense">
        <Upload size={16} strokeWidth={1.75} aria-hidden />
        <span className="max-w-[240px] truncate">{file ? file.name : "Choose a clip"}</span>
        <input type="file" accept="video/mp4,video/webm" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
      <TextArea label="What it shows" rows={3} maxLength={500} value={words} onChange={(e) => setWords(e.target.value)} placeholder="The small alarm opens, beeps and flashes red." hint={ai ? `Leave it empty and the AI describes it from two of its frames · ${upTo(price.data?.credits, price.data?.usd) || "…"}` : "Your words, as the director reads them."} />
      <ProductPicker brandId={brandId} value={product} onChange={setProduct} />
      {add.isError && <p role="alert" className="text-sm text-danger">{add.error.message}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <Button disabled={!file} reason={file ? null : "Choose a clip first"} busy={add.isPending} onClick={() => add.mutate()}>
          Add clip
        </Button>
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </section>
  );
}

function ClipCard({ brandId, clip, rows, where }: { brandId: number; clip: Footage; rows: FootageFolder[]; where: string }) {
  const [editing, setEditing] = useState(false);
  const [moving, setMoving] = useState(false);
  const [words, setWords] = useState(clip.description);
  const [product, setProduct] = useState<number | null>(clip.product_id ?? null);
  const products = useItems("prop", brandId).data ?? [];
  const queryClient = useQueryClient();
  const toast = useToast();
  const url = { params: { path: { brand_id: brandId, footage_id: clip.id } } };
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["footage", brandId] });
  const save = useMutation({
    mutationFn: () => must(api.PATCH("/brands/{brand_id}/footage/{footage_id}", { ...url, body: { description: words.trim(), product_id: product, no_product: product === null } })),
    onSuccess: () => (setEditing(false), refresh()),
  });
  const remove = useMutation({
    mutationFn: () => must(api.DELETE("/brands/{brand_id}/footage/{footage_id}", url)),
    onSuccess: () => {
      toast("Clip deleted.", () => void must(api.POST("/brands/{brand_id}/footage/{footage_id}/restore", url)).then(refresh, (e: Error) => toast(e.message, undefined, "error")));
      return refresh();
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const name = products.find((p) => p.id === clip.product_id)?.name;
  return (
    <li className="flex flex-col overflow-hidden rounded-lg border border-border bg-surface">
      <div className="relative aspect-video overflow-hidden bg-surface-2">
        <video src={fileUrl(clip.file_id)} poster={clip.thumb_file_id ? fileUrl(clip.thumb_file_id) : undefined} controls preload="none" aria-label={clip.description || "A clip of the brand’s footage"} className="absolute inset-0 size-full object-cover" />
        <span className="pointer-events-none absolute left-2 top-2">
          <Badge tone="media">{length(clip.seconds)}</Badge>
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-4">
        {editing ? (
          <>
            <TextArea label="What it shows" rows={3} maxLength={500} value={words} onChange={(e) => setWords(e.target.value)} />
            <ProductPicker brandId={brandId} value={product} onChange={setProduct} />
            {save.isError && <p role="alert" className="text-sm text-danger">{save.error.message}</p>}
            <div className="flex flex-wrap gap-2">
              <Button disabled={!words.trim()} reason={words.trim() ? null : "Say what it shows"} busy={save.isPending} onClick={() => save.mutate()}>
                Save
              </Button>
              <Button variant="ghost" onClick={() => (setEditing(false), setWords(clip.description), setProduct(clip.product_id ?? null))}>
                Cancel
              </Button>
            </div>
          </>
        ) : (
          <>
            <p className="text-xs font-medium text-muted">
              {name ?? "No product"}
              {where && ` · in ${where}`}
            </p>
            {clip.describing ? (
              <p className="text-sm text-muted" role="status">Describing what it shows…</p>
            ) : clip.description ? (
              <p className="text-sm">{clip.description}</p>
            ) : (
              <p className="text-sm text-warning">{clip.note || "Not described yet. Edit it to say what it shows; the director skips it until then."}</p>
            )}
            <div className="mt-auto flex flex-wrap gap-2">
              {/* as the server has it now: the AI's words may have come in since the card first drew */}
              <Button variant="secondary" icon={Pencil} onClick={() => (setWords(clip.description), setProduct(clip.product_id ?? null), setEditing(true))}>
                Edit
              </Button>
              <Button variant="ghost" icon={ArrowRightLeft} onClick={() => setMoving(true)}>
                Move to…
              </Button>
              <Button variant="ghost" icon={Trash2} busy={remove.isPending} onClick={() => remove.mutate()}>
                Delete
              </Button>
            </div>
            {moving && <MoveClip brandId={brandId} clip={clip} rows={rows} onClose={() => setMoving(false)} />}
          </>
        )}
      </div>
    </li>
  );
}
