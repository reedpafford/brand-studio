import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { fileUrl } from "../api/upload";
import { Plus, Smartphone, X } from "lucide-react";
import { Button, Sheet, Tabs } from "../components";
import { useMedia } from "../useMedia";

export type Piece = { key: string; type: "character" | "place" | "prop" | "screen"; id: number; name: string; fileId?: number; auto?: string; blocked?: string };

const TABS = ["character", "place", "prop", "screen"] as const;
const LABEL = { character: "Characters", place: "Places", prop: "Props", screen: "Screens" };

/** Everything this brand can put in a clip, one list per tab. */
export function useBrandPieces(brandId: number): { pieces: Piece[]; screens: { key: string; moments: string[] }[]; isPending: boolean } {
  const useLibrary = (kind: "character" | "place" | "prop") =>
    useQuery({
      queryKey: ["library", kind, brandId, false],
      queryFn: async () => (await api.GET("/library/{kind}", { params: { path: { kind }, query: { brand_id: brandId } } })).data ?? [],
    });
  const characters = useLibrary("character");
  const places = useLibrary("place");
  const props = useLibrary("prop");
  const screens = useQuery({
    queryKey: ["screens", brandId],
    queryFn: async () => (await api.GET("/brands/{brand_id}/screens", { params: { path: { brand_id: brandId } } })).data ?? [],
  });
  const lift = (type: Piece["type"], rows: { id: number; name: string; image_file_ids?: number[]; sheet_status?: string }[] = []): Piece[] =>
    rows.map((r) => ({
      key: `${type}-${r.id}`,
      type,
      id: r.id,
      name: r.name,
      fileId: r.image_file_ids?.[0],
      // Videos only use an approved sheet.
      blocked: (type === "character" || type === "place") && r.sheet_status !== "approved" ? "Approve its sheet first" : undefined,
    }));
  const screenPieces: Piece[] = (screens.data ?? []).map((s) => ({ key: `screen-${s.id}`, type: "screen", id: s.id, name: s.name, fileId: s.file_id }));
  return {
    pieces: [...lift("character", characters.data), ...lift("place", places.data), ...lift("prop", props.data), ...screenPieces],
    screens: (screens.data ?? []).map((s) => ({ key: `screen-${s.id}`, moments: s.default_for })),
    isPending: characters.isPending || places.isPending || props.isPending || screens.isPending,
  };
}

export function BrandPieces(props: { all: Piece[]; chosen: Piece[]; max: number; onAdd: (p: Piece) => void; onRemove: (key: string) => void }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<(typeof TABS)[number]>("character");
  const rail = useMedia("(min-width: 1024px)");
  const left = props.all.filter((p) => p.type === tab && !props.chosen.some((c) => c.key === p.key));
  const picker = (
    <div className={rail ? "space-y-3 rounded-lg border border-border bg-surface p-3" : "space-y-3"}>
      <Tabs label="Brand pieces" value={tab} onChange={(id) => setTab(id as (typeof TABS)[number])} tabs={TABS.map((t) => ({ id: t, label: LABEL[t] }))} />
      {left.length === 0 && <p className="text-sm text-muted">Nothing more here for this brand.</p>}
      {left.length > 0 && props.chosen.length >= props.max && <p className="text-sm text-muted">That's the most this model takes ({props.max}). Remove one to add another.</p>}
      <ul className="grid grid-cols-3 gap-2">
        {left.map((p) => (
          <li key={p.key}>
            <button type="button" className="block min-h-control w-full rounded-md p-1 text-left text-sm hover:bg-surface-2 disabled:opacity-60" onClick={() => props.onAdd(p)} disabled={props.chosen.length >= props.max || !!p.blocked}>
              {p.fileId && <img src={fileUrl(p.fileId)} alt="" className="aspect-square w-full rounded-md border border-border object-cover" />}
              {p.name}
              {p.blocked && <span className="block text-xs text-muted">{p.blocked}</span>}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
  return (
    <div className="space-y-2">
      <div className="flex justify-between font-medium">
        <span>Brand pieces</span>
        <span className="text-sm font-normal text-muted">{props.chosen.length} of {props.max}</span>
      </div>
      <ul className="flex flex-wrap gap-2">
        {props.chosen.map((p) => (
          <li key={p.key} className="flex items-center gap-2 rounded-md bg-accent-soft pl-2 text-sm text-accent-text">
            {p.fileId && <img src={fileUrl(p.fileId)} alt="" className="size-6 rounded-sm object-cover" />}
            {p.type === "screen" && !p.fileId && <Smartphone size={16} strokeWidth={1.75} aria-hidden />}
            {p.name}
            <button type="button" className="grid size-control place-items-center rounded-md hover:bg-surface-2" aria-label={`Remove ${p.name}`} onClick={() => props.onRemove(p.key)}>
              <X size={16} strokeWidth={1.75} aria-hidden />
            </button>
          </li>
        ))}
      </ul>
      {props.chosen.filter((p) => p.auto).map((p) => (
        <p key={p.key} className="text-sm text-muted">
          {p.name}: added because you mentioned the {p.auto?.replace(/[-_]+/g, " ")}. Remove it with the X.
        </p>
      ))}
      <Button variant="secondary" icon={Plus} aria-label="Add brand piece" aria-expanded={open} onClick={() => setOpen(!open)}>
        Add
      </Button>
      {open && (rail ? picker : <Sheet title="Add a brand piece" onClose={() => setOpen(false)}>{picker}</Sheet>)}
    </div>
  );
}
