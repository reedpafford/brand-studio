import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Settings2 } from "lucide-react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { useMe } from "../auth/useMe";
import { Badge, Button, Panel } from "../components";
import { ChoicePanel, fieldsOf, languageName, type Choice, type Field } from "../projects/VideoSettings";
import { useRail } from "../useMedia";
import { LookPicker, useLooks } from "./Looks";
import type { Script } from "./useScript";

type SettingsOut = components["schemas"]["SettingsOut"];
/** What Make this version sends (#956's VideoSettingsIn): only what was picked; anything left out is the default. */
export type Picks = Omit<components["schemas"]["SettingIn"], "undo">;
export type MakeEstimate = { credits: number; over_cap: boolean; reason: string | null };

/** The row's choices before a video exists, built as the video's own settings are (Next-Lead: no settings route here):
 *  models and prices from the catalogue, looks, the fixed shapes, the brand's flavours. Defaults: the script's look, Auto
 *  models, 9:16, each product's first flavour. */
function useChoices(script: Script, picks: Picks): SettingsOut | null {
  const models = useQuery({ queryKey: ["models"], queryFn: async () => (await api.GET("/models")).data ?? [] });
  const screens = useQuery({ queryKey: ["screens", script.brand_id], queryFn: async () => (await api.GET("/brands/{brand_id}/screens", { params: { path: { brand_id: script.brand_id } } })).data ?? [] });
  if (!models.data || !screens.data) return null;
  const flavours: Record<string, string[]> = {};
  for (const s of screens.data) if (s.product && s.variant && !(flavours[s.product] ??= []).includes(s.variant)) flavours[s.product].push(s.variant);
  const rate = (m: (typeof models.data)[number], at: string) => m.credits_per_unit[at] ?? Object.values(m.credits_per_unit)[0] ?? 0;
  const lipSync = (m: object) => (m as { lip_sync?: boolean }).lip_sync ?? true; // in the catalogue's output with #956
  return {
    look: picks.look ?? script.look,
    video_model: picks.video_model ?? null,
    image_model: picks.image_model ?? null,
    aspect_ratio: picks.aspect_ratio ?? "9:16",
    product_variants: picks.product_variants ?? {},
    language: script.language,
    video_models: models.data.filter((m) => m.kind === "video").map((m) => ({ id: m.id, name: m.name, credits_per_second: rate(m, "480p"), lip_sync: lipSync(m), default: m.default, over_cap: false })),
    image_models: models.data.filter((m) => m.kind === "image").map((m) => ({ id: m.id, name: m.name, credits_per_still: rate(m, "1K"), default: m.default, over_cap: false })),
    shapes: ["9:16", "1:1", "16:9", "4:3", "3:4", "21:9"],
    flavours,
  };
}

/** What the version costs to make with these picks (#956: POST …/estimate), or null where the server doesn't offer it yet. */
export function useMakeEstimate(scriptId: number, slot: number, picks: Picks, enabled: boolean) {
  return useQuery({
    enabled,
    queryKey: ["make-estimate", scriptId, slot, picks],
    placeholderData: (was) => was, // the line keeps its number while the new one comes
    queryFn: async () => {
      const r = await fetch(`${location.origin}/api/scripts/${scriptId}/drafts/${slot}/estimate`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(picks) });
      if (r.status === 404 || r.status === 405) return null;
      const body = await r.json().catch(() => null);
      if (!r.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Couldn't work out the price. Try again.");
      return body as MakeEstimate;
    },
  });
}

/** Make this version's Video settings row (flows VS1, V1): the video's own row, its picks held here until the press. No
 *  confirm or Undo: nothing is made yet, so a pick only changes the price line. On a phone it is one line that opens a sheet. */
export function MakeSettings({ script, picks, onPick }: { script: Script; picks: Picks; onPick: (p: Picks) => void }) {
  const rail = useRail();
  const owner = useMe().data?.role === "owner";
  const looks = useLooks();
  const settings = useChoices(script, picks);
  const [sheet, setSheet] = useState(false);
  const [picking, setPicking] = useState<Field | null>(null);
  if (!settings) return null;
  const fields = fieldsOf(settings, looks.data);
  const pick = (c: Choice) => {
    setPicking(null);
    const { product_variants, ...one } = c.body;
    onPick(product_variants ? { ...picks, product_variants: { ...picks.product_variants, ...product_variants } } : { ...picks, ...one });
  };
  const chip = (f: Field) => (
    <Button key={f.key} variant="ghost" dense trailing={ChevronDown} aria-haspopup="dialog" onClick={() => setPicking(f)}>
      <span className="text-muted">{f.label}:</span> {f.valueLabel}
      {f.price && <span className="text-xs text-muted tabular-nums">· {f.price}</span>}
    </Button>
  );
  const items = (
    <>
      {fields.map(chip)}
      <Badge>Language: {languageName(settings.language)} (from the script)</Badge>
    </>
  );
  return (
    <>
      {rail ? (
        <section aria-label="Video settings" className="flex flex-wrap items-center gap-1">
          <Settings2 size={20} strokeWidth={1.75} aria-hidden className="text-muted" />
          {items}
        </section>
      ) : (
        <Button variant="ghost" spread icon={Settings2} trailing={ChevronDown} aria-haspopup="dialog" onClick={() => setSheet(true)}>
          <span className="block truncate">Settings: {fields.map((f) => f.valueLabel).join(" · ")}</span>
        </Button>
      )}
      {sheet && !picking && (
        <Panel title="Video settings" onClose={() => setSheet(false)}>
          <div className="flex flex-col items-stretch gap-2 [&>*]:justify-start">{items}</div>
        </Panel>
      )}
      {picking?.key === "look" && looks.data ? (
        <LookPicker current={picking.current} looks={looks.data} busy={null} error={null} onPick={(l) => pick(picking.choices.find((c) => c.id === l.id)!)} onClose={() => setPicking(null)} />
      ) : (
        picking && <ChoicePanel field={picking} owner={owner} onPick={(c) => (c.id === picking.current ? setPicking(null) : pick(c))} onClose={() => setPicking(null)} />
      )}
    </>
  );
}
