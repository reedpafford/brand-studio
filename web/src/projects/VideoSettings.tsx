import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Settings2 } from "lucide-react";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { Badge, Button, Dialog, Panel, Skeleton, useToast, wholeCredits } from "../components";
import { useMe } from "../auth/useMe";
import { LookPicker, useLooks } from "../scripts/Looks";
import { SongSetting } from "../scripts/VideoSong";
import { useRail } from "../useMedia";
import { errorText as errorClass } from "../ui";

type Project = components["schemas"]["ProjectOut"];
type SettingsOut = components["schemas"]["SettingsOut"];
type SettingIn = components["schemas"]["SettingIn"];
type PreviewOut = components["schemas"]["app__routes__video_settings__PreviewOut"];

/** The video's settings, or an error where the server doesn't offer them yet (then the row stays hidden). */
export function useVideoSettings(projectId: number) {
  return useQuery({
    queryKey: ["video-settings", projectId],
    queryFn: () => must(api.GET("/projects/{project_id}/settings", { params: { path: { project_id: projectId } } })).then((r) => r.data!),
    retry: false,
  });
}

/** One choice in a picker, and the one setting it switches (a body with exactly that key; null is Auto). */
export type Choice = { id: string; label: string; price?: string; noLipSync?: boolean; overCap?: boolean; off?: boolean; body: SettingIn };
export type Field = { key: string; label: string; current: string; valueLabel: string; price?: string; choices: Choice[] };

const credits = (x: number) => `${Number(x.toFixed(2))} credit${x === 1 ? "" : "s"}`;
const perSecond = (x: number) => `${credits(x)} a second`;
const perStill = (x: number) => `${credits(x)} a still`;
const n = (k: number, one: string) => `${k} ${one}${k === 1 ? "" : "s"}`;
const cap = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);
export const languageName = (code: string) => {
  try {
    return new Intl.DisplayNames(["en"], { type: "language" }).of(code) ?? code;
  } catch {
    return code;
  }
};

/** The settings as the row shows them: one field per setting, each choice carrying the body that switches to it. */
export function fieldsOf(s: SettingsOut, looks: { id: string; name: string; on: boolean }[] | null | undefined): Field[] {
  const auto = <M extends { name: string; default: boolean }>(ms: M[]) => ms.find((m) => m.default) ?? ms[0];
  const video = auto(s.video_models);
  const image = auto(s.image_models);
  const nowVideo = s.video_model ? s.video_models.find((m) => m.id === s.video_model) : undefined;
  const nowImage = s.image_model ? s.image_models.find((m) => m.id === s.image_model) : undefined;
  const look = looks?.find((l) => l.id === s.look);
  return [
    { key: "aspect_ratio", label: "Shape", current: s.aspect_ratio, valueLabel: s.aspect_ratio, choices: s.shapes.map((x) => ({ id: x, label: x, body: { aspect_ratio: x as SettingIn["aspect_ratio"] } })) },
    ...Object.entries(s.flavours).map(([product, options]) => {
      const now = s.product_variants[product] ?? options[0]; // a product missing from the picks is on its default
      return { key: `flavour:${product}`, label: Object.keys(s.flavours).length > 1 ? `Flavour (${product})` : "Flavour", current: now, valueLabel: now, choices: options.map((o) => ({ id: o, label: o, body: { product_variants: { [product]: o } } })) };
    }),
    ...(looks ? [{ key: "look", label: "Look", current: s.look, valueLabel: look?.name ?? "House", choices: looks.map((l) => ({ id: l.id, label: l.name, off: !l.on, body: { look: l.id } })) }] : []),
    {
      key: "video_model",
      label: "Video model",
      current: s.video_model ?? "auto",
      valueLabel: nowVideo?.name ?? "Auto",
      price: perSecond((nowVideo ?? video)?.credits_per_second ?? 0),
      choices: [
        { id: "auto", label: video ? `Auto (${video.name})` : "Auto", price: video && perSecond(video.credits_per_second), noLipSync: video && !video.lip_sync, body: { video_model: null } },
        ...s.video_models.map((m) => ({ id: m.id, label: m.name, price: perSecond(m.credits_per_second), noLipSync: !m.lip_sync, overCap: m.over_cap, body: { video_model: m.id } })),
      ],
    },
    {
      key: "image_model",
      label: "Picture model",
      current: s.image_model ?? "auto",
      valueLabel: nowImage?.name ?? "Auto",
      price: perStill((nowImage ?? image)?.credits_per_still ?? 0),
      choices: [
        { id: "auto", label: image ? `Auto (${image.name})` : "Auto", price: image && perStill(image.credits_per_still), body: { image_model: null } },
        ...s.image_models.map((m) => ({ id: m.id, label: m.name, price: perStill(m.credits_per_still), overCap: m.over_cap, body: { image_model: m.id } })),
      ],
    },
  ];
}

/** What a switch costs and changes, said once: the finished warning first (LW1), Sung → B-roll, what goes out of date, then the new total. */
function confirmText(field: Field, choice: Choice, p: PreviewOut, finished: boolean) {
  const lines: string[] = [];
  const later = [p.stills_out_of_date && n(p.stills_out_of_date, "still"), p.clips_out_of_date && n(p.clips_out_of_date, "clip")].filter(Boolean).join(" and ");
  if (finished) lines.push(`This video is finished.${later ? ` Changing the ${field.label.toLowerCase()} puts ${later} out of date;` : ""} your current final cut stays downloadable until you make a new one.`);
  // A look switch leaves these roles with no look in it yet: they're made in Cast (flows ST1).
  const roles = p.roles_needing_look ?? [];
  if (roles.length > 0) lines.push(`${roles.length > 2 ? `${roles.length} roles` : roles.join(" and ")} need${roles.length === 1 ? "s" : ""} a new look, made in Cast.`);
  if (p.sung_to_broll > 0) lines.push(`${choice.label} can't lip-sync. Your ${n(p.sung_to_broll, "Sung shot")} become${p.sung_to_broll === 1 ? "s" : ""} B-roll (picture only).`);
  if (later && !finished) lines.push(`${cap(later)} already made stay as they are and show Out of date.`);
  lines.push(`To finish: about ${credits(wholeCredits(p.to_finish_credits))} (was ${wholeCredits(p.was_credits)}).`);
  return lines;
}

/** The Video settings row (flows VS1): Shape · Flavour · Look · Video model · Picture model · Language, and the Song on a song video.
 *  Each setting shows its choice and price; a pick is previewed, confirmed (Not yet / Switch), applied with Undo. On a phone it is one line that opens a sheet. */
export function VideoSettings({ project: p, finished, song = true }: { project: Project; finished: boolean; song?: boolean }) {
  const rail = useRail();
  const owner = useMe().data?.role === "owner";
  const queryClient = useQueryClient();
  const toast = useToast();
  const looks = useLooks();
  const settings = useVideoSettings(p.id);
  const [sheet, setSheet] = useState(false);
  const [picking, setPicking] = useState<Field | null>(null);
  const [asking, setAsking] = useState<{ field: Field; choice: Choice } | null>(null);
  const preview = useQuery({
    enabled: !!asking,
    queryKey: ["video-settings-preview", p.id, asking?.choice.body],
    queryFn: () => must(api.POST("/projects/{project_id}/settings/preview", { params: { path: { project_id: p.id } }, body: asking!.choice.body })).then((r) => r.data! as PreviewOut),
  });
  const refresh = () => Promise.all([["video-settings", p.id], ["project", p.id], ["project-estimate", p.id], ["storyboard", p.id], ["project-clips", p.id], ["assets", p.id], ["missing-looks", p.id]].map((k) => queryClient.invalidateQueries({ queryKey: k })));
  const apply = useMutation({ mutationFn: (body: SettingIn) => must(api.POST("/projects/{project_id}/settings", { params: { path: { project_id: p.id } }, body })).then((r) => r.data!) });
  const switchTo = (field: Field, choice: Choice) =>
    apply.mutate(choice.body, {
      onSuccess: async ({ was }) => {
        setAsking(null);
        setPicking(null);
        await refresh();
        // Undo sends `was` back with undo: true, so it is never refused (even over the limit); the old stills and takes become current again.
        toast(`${field.label}: ${choice.label}.`, () => apply.mutate({ ...(was as SettingIn), undo: true }, { onSuccess: () => void refresh(), onError: (e) => toast(e.message, undefined, "error") }));
      },
    });

  if (settings.isPending) return <Skeleton className="h-control" />;
  if (settings.isError || !settings.data) return null; // the server doesn't offer settings yet: nothing to press
  const fields = fieldsOf(settings.data, looks.data);
  const chip = (f: Field) => (
    <Button key={f.key} variant="ghost" dense trailing={ChevronDown} aria-haspopup="dialog" onClick={() => setPicking(f)}>
      <span className="text-muted">{f.label}:</span> {f.valueLabel}
      {f.price && <span className="text-xs text-muted tabular-nums">· {f.price}</span>}
    </Button>
  );
  const language = <Badge>Language: {languageName(settings.data.language)} (from the script)</Badge>;
  const items = (
    <>
      {fields.map(chip)}
      {p.song && song && <SongSetting project={p} />}
      {language}
    </>
  );
  const row = rail ? (
    <section aria-label="Video settings" className="flex flex-wrap items-center gap-1">
      <Settings2 size={20} strokeWidth={1.75} aria-hidden className="text-muted" />
      {items}
    </section>
  ) : (
    <Button variant="ghost" spread icon={Settings2} trailing={ChevronDown} aria-haspopup="dialog" onClick={() => setSheet(true)}>
      <span className="block truncate">Settings: {fields.map((f) => f.valueLabel).join(" · ")}</span>
    </Button>
  );

  const pick = (f: Field, c: Choice) => (c.id === f.current ? setPicking(null) : setAsking({ field: f, choice: c }));
  const lookOpen = picking?.key === "look" && looks.data;
  const lines = asking && preview.data ? confirmText(asking.field, asking.choice, preview.data, finished) : null;
  const hold = preview.data ? (preview.data.reason ?? (preview.data.over_budget ? "That's more than this video's budget." : preview.data.over_cap ? "Over the video limit." : null)) : null;
  return (
    <>
      {row}
      {sheet && !picking && (
        <Panel title="Video settings" onClose={() => setSheet(false)}>
          <div className="flex flex-col items-stretch gap-2 [&>*]:justify-start">{items}</div>
        </Panel>
      )}
      {picking && lookOpen && (
        // The existing look picker, wrapped: off looks are greyed for editors there.
        <LookPicker current={picking.current} looks={looks.data!} busy={null} error={null} onPick={(l) => pick(picking, picking.choices.find((c) => c.id === l.id)!)} onClose={() => setPicking(null)} />
      )}
      {picking && !lookOpen && <ChoicePanel field={picking} owner={owner} onPick={(c) => pick(picking, c)} onClose={() => setPicking(null)} />}
      {asking && (
        <Dialog
          title={asking.field.key === "aspect_ratio" ? `Change to ${asking.choice.label}?` : `Switch to ${asking.choice.label}?`}
          cancelLabel="Not yet"
          actionLabel="Switch"
          busy={apply.isPending || preview.isPending}
          holdReason={preview.isError ? preview.error.message : apply.isError ? apply.error.message : hold}
          onCancel={() => {
            setAsking(null);
            apply.reset();
          }}
          onConfirm={() => switchTo(asking.field, asking.choice)}
        >
          {lines ? lines.map((l) => <p key={l}>{l}</p>) : <p className="text-muted" role="status">Working out what changes…</p>}
        </Dialog>
      )}
      {apply.isError && !asking && <p role="alert" className={errorClass}>{apply.error.message}</p>}
    </>
  );
}

/** One setting's choices, each with its price and "No lip-sync"; the one in use is marked. Shared with Make this version's row. */
export function ChoicePanel({ field, owner, onPick, onClose }: { field: Field; owner: boolean; onPick: (c: Choice) => void; onClose: () => void }) {
  return (
    <Panel title={field.label} onClose={onClose}>
      <ul className="space-y-2">
        {field.choices
          .filter((c) => owner || !c.off)
          .map((c) => (
            <li key={c.id}>
              <button
                type="button"
                disabled={!!c.overCap}
                aria-pressed={c.id === field.current}
                onClick={() => onPick(c)}
                className={`flex min-h-control w-full flex-wrap items-center gap-x-2 gap-y-1 rounded-md border px-3 py-2 text-left disabled:opacity-60 ${c.id === field.current ? "border-accent bg-accent-soft" : "border-border-strong hover:bg-surface-2"}`}
              >
                <span className="font-medium">{c.label}</span>
                {c.price && <span className="text-sm text-muted tabular-nums">· {c.price}</span>}
                {c.noLipSync && <Badge>No lip-sync</Badge>}
                {c.overCap && <span className="w-full text-sm text-muted">Over the video limit</span>}
              </button>
            </li>
          ))}
      </ul>
    </Panel>
  );
}
