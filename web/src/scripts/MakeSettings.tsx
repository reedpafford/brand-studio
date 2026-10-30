import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Settings2 } from "lucide-react";
import { api, must } from "../api/client";
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

/** The row's choices before a video exists, built as the video's own settings are (Next-Lead: no settings route here):
 *  models and prices from the catalogue, looks, the fixed shapes, the brand's flavours. Defaults: the script's look, Auto
 *  models, 9:16, each product's first flavour. */
function useChoices(script: Script, picks: Picks, defaults: Record<string, string>): (SettingsOut & { auto: string[] }) | null {
  const models = useQuery({ queryKey: ["models"], queryFn: async () => (await api.GET("/models")).data ?? [] });
  const screens = useQuery({ queryKey: ["screens", script.brand_id], queryFn: async () => (await api.GET("/brands/{brand_id}/screens", { params: { path: { brand_id: script.brand_id } } })).data ?? [] });
  if (!models.data || !screens.data) return null;
  const flavours: Record<string, string[]> = {};
  for (const s of screens.data) if (s.product && s.variant && !(flavours[s.product] ??= []).includes(s.variant)) flavours[s.product].push(s.variant);
  // The version's default flavours (#968), without the ones the brand has deleted since (#991's flavours_gone): those read
  // Auto, never as current. One rule, the server's, the one Make this version uses.
  const kept = defaults;
  const variants = { ...kept, ...picks.product_variants };
  const rate = (m: (typeof models.data)[number], at: string) => m.credits_per_unit[at] ?? Object.values(m.credits_per_unit)[0] ?? 0;
  return {
    look: picks.look ?? script.look,
    video_model: picks.video_model ?? null,
    image_model: picks.image_model ?? null,
    aspect_ratio: picks.aspect_ratio ?? "9:16",
    product_variants: variants,
    auto: Object.keys(flavours).filter((p) => !(p in kept)), // may go back to Auto (no default to fall back on)
    language: script.language,
    video_models: models.data.filter((m) => m.kind === "video").map((m) => ({ id: m.id, name: m.name, credits_per_second: rate(m, "480p"), lip_sync: m.lip_sync, default: m.default, over_cap: false })),
    image_models: models.data.filter((m) => m.kind === "image").map((m) => ({ id: m.id, name: m.name, credits_per_still: rate(m, "1K"), default: m.default, over_cap: false })),
    shapes: ["9:16", "1:1", "16:9", "4:3", "3:4", "21:9"],
    flavours,
  };
}

/** What the version costs to make with these picks (#965): "about N credits", and the reason when it's held back. */
export function useMakeEstimate(scriptId: number, slot: number, picks: Picks, enabled: boolean) {
  return useQuery({
    enabled,
    queryKey: ["make-estimate", scriptId, slot, picks],
    placeholderData: (was) => was, // the line keeps its number while the new one comes
    queryFn: async () => (await must(api.POST("/scripts/{script_id}/drafts/{slot}/estimate", { params: { path: { script_id: scriptId, slot } }, body: picks }))).data!,
  });
}

/** Make this version's Video settings row (flows VS1, V1): the video's own row, its picks held here until the press. No
 *  confirm or Undo: nothing is made yet, so a pick only changes the price line. On a phone it is one line that opens a sheet. */
export function MakeSettings({ script, defaults, picks, onPick }: { script: Script; defaults: Record<string, string>; picks: Picks; onPick: (p: Picks) => void }) {
  const rail = useRail();
  const owner = useMe().data?.role === "owner";
  const looks = useLooks();
  const settings = useChoices(script, picks, defaults);
  const [sheet, setSheet] = useState(false);
  const [picking, setPicking] = useState<Field | null>(null);
  if (!settings) return null;
  // A product with no flavour (none picked, no default) is Auto: the server picks, as on a video.
  const fields = fieldsOf(settings, looks.data).map((f) => {
    const product = f.key.startsWith("flavour:") ? f.key.slice("flavour:".length) : null;
    if (!product || !settings.auto.includes(product)) return f;
    const picked = product in settings.product_variants;
    return { ...f, current: picked ? f.current : `auto:${product}`, valueLabel: picked ? f.valueLabel : "Auto", choices: [{ id: `auto:${product}`, label: "Auto", body: {} }, ...f.choices] };
  });
  const pick = (c: Choice) => {
    setPicking(null);
    if (c.id.startsWith("auto:")) {
      const rest = { ...picks.product_variants };
      delete rest[c.id.slice("auto:".length)];
      return onPick({ ...picks, product_variants: Object.keys(rest).length ? rest : undefined });
    }
    const { product_variants, ...one } = c.body;
    onPick(product_variants ? { ...picks, product_variants: { ...picks.product_variants, ...product_variants } } : { ...picks, ...one });
  };
  const chip = (f: Field) => (
    <Button key={f.key} variant="ghost" dense trailing={ChevronDown} aria-haspopup="dialog" onClick={() => setPicking(f)}>
      <span className="text-muted">{f.label}:</span> {f.valueLabel}
      {f.price && <>{" "}<span className="text-xs text-muted tabular-nums">· {f.price}</span></>}
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
