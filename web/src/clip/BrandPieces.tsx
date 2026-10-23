import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { fileUrl } from "../api/upload";
import { btnSecondary, linkText } from "../ui";

export type Piece = { key: string; type: "character" | "place" | "prop" | "screen"; id: number; name: string; fileId?: number; auto?: boolean };

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
  const lift = (type: Piece["type"], rows: { id: number; name: string; image_file_ids?: number[] }[] = []): Piece[] =>
    rows.map((r) => ({ key: `${type}-${r.id}`, type, id: r.id, name: r.name, fileId: r.image_file_ids?.[0] }));
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
  const left = props.all.filter((p) => p.type === tab && !props.chosen.some((c) => c.key === p.key));
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm font-medium">
        <span>Brand pieces</span>
        <span className="text-muted">{props.chosen.length}/{props.max}</span>
      </div>
      <ul className="flex flex-wrap gap-2">
        {props.chosen.map((p) => (
          <li key={p.key} className="flex items-center gap-1 rounded-sm bg-accent-soft px-2 py-1 text-sm text-accent-text">
            {p.fileId && <img src={fileUrl(p.fileId)} alt="" className="size-5 rounded-sm object-cover" />}
            {p.auto && <span title="Added because your prompt mentions its moment">★</span>}
            {p.name}
            <button type="button" aria-label={`Remove ${p.name}`} onClick={() => props.onRemove(p.key)}>
              ×
            </button>
          </li>
        ))}
      </ul>
      <button type="button" className={btnSecondary} onClick={() => setOpen(!open)} aria-expanded={open}>
        Add brand piece
      </button>
      {open && (
        <div className="space-y-2 rounded-md border border-border bg-surface p-2">
          <div role="tablist" className="flex gap-1 text-sm">
            {TABS.map((t) => (
              <button key={t} role="tab" aria-selected={t === tab} className={`rounded-sm px-2 py-1 ${t === tab ? "bg-accent-soft text-accent-text" : "text-muted"}`} onClick={() => setTab(t)}>
                {LABEL[t]}
              </button>
            ))}
          </div>
          {left.length === 0 && <p className="text-sm text-muted">Nothing more here for this brand.</p>}
          <ul className="grid grid-cols-3 gap-2">
            {left.map((p) => (
              <li key={p.key}>
                <button type="button" className={`${linkText} block w-full text-left text-sm no-underline`} onClick={() => props.onAdd(p)} disabled={props.chosen.length >= props.max}>
                  {p.fileId && <img src={fileUrl(p.fileId)} alt="" className="aspect-square w-full rounded-sm border border-border object-cover" />}
                  {p.name}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
