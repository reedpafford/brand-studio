import { useQuery } from "@tanstack/react-query";
import { Check, FileText, Image, MapPin, Mic, Package, Plus, Users, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { buttonClass } from "../components";
import { groupProducts, useScreens } from "../brand/screens";

type Brand = components["schemas"]["BrandOut"];

/** A colour's everyday name from its hex ("green"), for "Resilia · green". */
function colourName(hex: string | undefined) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex ?? "");
  if (!m) return "";
  const [r, g, b] = m.slice(1).map((x) => parseInt(x, 16) / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  if (max - min < 0.12) return max > 0.85 ? "white" : max < 0.2 ? "black" : "grey";
  const h = 60 * (max === r ? ((g - b) / (max - min) + 6) % 6 : max === g ? (b - r) / (max - min) + 2 : (r - g) / (max - min) + 4);
  const names: [number, string][] = [[15, "red"], [45, "orange"], [70, "yellow"], [165, "green"], [195, "teal"], [255, "blue"], [290, "purple"], [335, "pink"], [360, "red"]];
  return names.find(([top]) => h < top)?.[1] ?? "red";
}

function useCount(kind: "character" | "place", brandId: number) {
  return useQuery({ queryKey: ["library", kind, brandId], queryFn: async () => (await api.GET("/library/{kind}", { params: { path: { kind }, query: { brand_id: brandId } } })).data?.length ?? 0 });
}

/** A brand-new brand (S1-02, S-gaps-02): what the director can use without asking, each ticked from what the brand already
 *  has, with "Add" to that part of the brand or library. Shown only while the brand has no ideas and no folders. */
export function SetUp({ brand, others, owner, newVideo }: { brand: Brand; others: string[]; owner: boolean; newVideo: string }) {
  const b = `/b/${brand.id}`;
  const characters = useCount("character", brand.id).data ?? 0;
  const places = useCount("place", brand.id).data ?? 0;
  const products = groupProducts(useScreens(brand.id).data ?? []).length;
  const tone = brand.dont_list.length + brand.do_list.length > 0 || !!brand.audience;
  // What a brand holds now (S-gaps-05 L1, L4): the kit is name, logo, colours, tone and rules; products are apps or
  // physical things; a brand's own voices are only ones uploaded or cloned on purpose. No import (L2).
  const steps: [LucideIcon, boolean, string, string, string][] = [
    [Image, !!brand.logo_file_id, "Logo", "Shown on products and in endings", `${b}/brand`],
    [FileText, tone, "Tone and rules", "What the brand never says, and how it talks", `${b}/brand?tab=voice`],
    [Users, characters > 0, "Characters", "People the director can cast without asking", `${b}/library/characters`],
    [Package, products > 0, "Products", "An app’s screens, or the real bottle or bag so labels read right", `${b}/brand?tab=products`],
    [MapPin, places > 0, "Places", "Rooms and streets that recur", `${b}/library/places`],
    [Mic, false, "Voices", "Only ones you upload or clone, for narrated and presenter videos", `${b}/brand?tab=voice`],
  ];
  const row = (Icon: LucideIcon, done: boolean, title: string, line: string, to?: string) => (
    <li key={title} className="flex items-center gap-3 border-t border-border px-4 py-3 first:border-t-0">
      <span role="img" aria-label={done ? "Done" : "Not yet"} className={`grid size-4 shrink-0 place-items-center rounded-sm border ${done ? "border-accent bg-accent text-on-accent" : "border-border-strong"}`}>
        {done && <Check size={12} strokeWidth={2.5} aria-hidden />}
      </span>
      <Icon size={16} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="font-semibold">{title}</span>
        <span className="text-sm text-muted">{line}</span>
      </span>
      {!done && to && owner && (
        <Link to={to} className={buttonClass("secondary")}>
          Add
        </Link>
      )}
    </li>
  );
  return (
    <div className="flex justify-center px-4 py-12">
      <div className="flex w-full max-w-[640px] flex-col gap-5">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold">Set up {brand.name}</h1>
          <p className="text-md text-muted">The more the brand knows, the less the director has to ask. You can make a video now and add these later.</p>
        </div>
        <ul className="overflow-hidden rounded-lg border border-border bg-surface">
          {row(Check, true, "Name and colour", [brand.name, colourName(brand.colours?.[0])].filter(Boolean).join(" · "))}
          {steps.map(([Icon, done, title, line, to]) => row(Icon, done, title, line, to))}
        </ul>
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex-1" />
          <Link to={newVideo} className={`${buttonClass("primary")} lg:min-h-9`}>
            <Plus size={16} strokeWidth={1.75} aria-hidden /> Make the first video
          </Link>
        </div>
        {others.length > 0 && <p className="text-sm text-muted">Each brand is separate: nothing saved here shows up in {others.join(" or ")}.</p>}
      </div>
    </div>
  );
}
