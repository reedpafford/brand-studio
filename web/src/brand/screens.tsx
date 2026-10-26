import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl, uploadFile } from "../api/upload";
import { Button, Field, Sheet, SidePanel } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useRail } from "../useMedia";
import { ChipList } from "./ChipList";

export type Screen = components["schemas"]["ScreenOut"];

/** The brand's real app screens. Products are these same screens grouped by their product field. */
export function useScreens(brandId: number) {
  return useQuery({
    queryKey: ["screens", brandId],
    queryFn: async () => (await api.GET("/brands/{brand_id}/screens", { params: { path: { brand_id: brandId } } })).data ?? [],
  });
}

/** Screens that were deleted and can come back. Only asked for once the brand has the screens tab open. */
export function useDeletedScreens(brandId: number) {
  return useQuery({
    queryKey: ["screens", brandId, "deleted"],
    queryFn: async () => (await api.GET("/brands/{brand_id}/screens", { params: { path: { brand_id: brandId }, query: { deleted: true } } })).data ?? [],
  });
}

/** Bring a deleted screen back, with the toast. */
export function useRestoreScreen(brandId: number) {
  const queryClient = useQueryClient();
  const toast = useToast();
  return async (sc: Pick<Screen, "id" | "name">) => {
    const { error, response } = await api.POST("/brands/{brand_id}/screens/{screen_id}/restore", { params: { path: { brand_id: brandId, screen_id: sc.id } } });
    if (!response.ok) return toast(errorText(error), undefined, "error");
    await queryClient.invalidateQueries({ queryKey: ["screens", brandId] });
    toast(`Restored "${sc.name}".`);
  };
}

/** The server's words when a screen's name is a deleted screen's name. */
export const NAME_TAKEN = "A deleted screen has that name.";

/** Products from the screens' product field, grouped without regard to capitals ("Bag" and "bag" are one product).
 *  The name shown is the spelling most screens use. */
export function groupProducts(screens: Screen[]): { name: string; screens: Screen[] }[] {
  const groups = new Map<string, Screen[]>();
  for (const s of screens) {
    const p = s.product.trim();
    if (p) groups.set(p.toLowerCase(), [...(groups.get(p.toLowerCase()) ?? []), s]);
  }
  return [...groups.values()].map((list) => {
    const count = new Map<string, number>();
    for (const s of list) count.set(s.product.trim(), (count.get(s.product.trim()) ?? 0) + 1);
    const name = [...count].sort((a, b) => b[1] - a[1])[0][0];
    return { name, screens: list };
  });
}

export const slug = (s: string) => s.trim().toLowerCase().replace(/\s+/g, "-");

/** A side panel on desktop, a sheet on a phone. */
export function Panel(props: { title: string; onClose: () => void; children: ReactNode }) {
  return useRail() ? <SidePanel {...props} /> : <Sheet {...props} />;
}

/** Upload a picture and make it a screen. */
export function useAddScreen(brandId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (a: { file?: File; fileId?: number; name: string; product?: string; variant?: string }) => {
      const stored = a.fileId !== undefined ? { id: a.fileId } : await uploadFile(a.file!);
      const { data, error } = await api.POST("/brands/{brand_id}/screens", {
        params: { path: { brand_id: brandId } },
        body: { name: a.name, file_id: stored.id, tags: [], default_for: [], product: a.product ?? "", variant: a.variant ?? "" },
      });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["screens", brandId] }),
  });
}

/** One screen's words: name, tags, product and flavour, and the moments it is always used for. The picture stays. */
export function ScreenEditor({ brandId, screen: sc, onClose }: { brandId: number; screen: Screen; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState(sc.name);
  const [tags, setTags] = useState(sc.tags);
  const [moments, setMoments] = useState(sc.default_for);
  const [product, setProduct] = useState(sc.product);
  const [variant, setVariant] = useState(sc.variant);
  const known = groupProducts(useScreens(brandId).data ?? []).map((g) => g.name);
  const done = () => queryClient.invalidateQueries({ queryKey: ["screens", brandId] });
  const save = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.PATCH("/brands/{brand_id}/screens/{screen_id}", {
        params: { path: { brand_id: brandId, screen_id: sc.id } },
        body: { name, tags, default_for: moments, product: known.find((k) => k.toLowerCase() === product.trim().toLowerCase()) ?? product.trim(), variant: variant.trim() },
      });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: async () => {
      await done();
      toast("Screen saved.");
      onClose();
    },
  });
  const restore = useRestoreScreen(brandId);
  // Deleting can be undone, so there is no dialog: the panel closes and the toast says how to undo it.
  const remove = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.DELETE("/brands/{brand_id}/screens/{screen_id}", { params: { path: { brand_id: brandId, screen_id: sc.id } } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: async () => {
      await done();
      toast(`Deleted "${sc.name}".`, () => void restore(sc).then(() => done()));
      onClose();
    },
  });
  const taken = save.isError && save.error.message.startsWith(NAME_TAKEN);
  const deleted = useDeletedScreens(brandId);
  const clash = taken ? deleted.data?.find((d) => d.name.trim().toLowerCase() === name.trim().toLowerCase()) : undefined;
  return (
    <Panel title={`Edit ${sc.name}`} onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <img src={fileUrl(sc.file_id)} alt="" className="mx-auto max-h-64 rounded-lg border border-border bg-surface-2 object-contain" />
        <div className="space-y-1">
          <Field label="Name" required value={name} onChange={(e) => setName(e.target.value)} error={taken ? save.error?.message : null} />
          {clash && (
            <Button type="button" variant="ghost" onClick={() => void restore(clash).then(onClose)}>
              Restore "{clash.name}"
            </Button>
          )}
        </div>
        <ChipList label="Tags" items={tags} onChange={setTags} normalise={slug} placeholder="e.g. trading, chart-up" hint="What the screen shows. Spaces become dashes." />
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Product" placeholder="e.g. Bag" value={product} onChange={(e) => setProduct(e.target.value)} hint="Optional" />
          <Field label="Flavour" placeholder="e.g. Chicken" value={variant} onChange={(e) => setVariant(e.target.value)} hint="Optional" />
        </div>
        <p className="text-sm text-muted">Product and flavour fill the Products tab and the brief's flavour picker.</p>
        <ChipList label="Always use this screen for" items={moments} onChange={setMoments} normalise={slug} placeholder="e.g. buy-moment" hint="Videos add it when the prompt or a shot mentions the moment." />
        {save.isError && !taken && <p role="alert" className={errorClass}>{save.error.message}</p>}
        {remove.isError && <p role="alert" className={errorClass}>{remove.error.message}</p>}
        <div className="space-y-2">
          <Button type="submit" busy={save.isPending} className="w-full">
            Save screen
          </Button>
          <Button type="button" variant="danger" className="w-full" busy={remove.isPending} onClick={() => remove.mutate()}>
            Delete screen
          </Button>
        </div>
      </form>
    </Panel>
  );
}
