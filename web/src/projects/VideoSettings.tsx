import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Lock, RefreshCw, Settings2 } from "lucide-react";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { Badge, Button, creditsText, Dialog, Panel, Skeleton, useToast, wholeCredits } from "../components";
import { useMe } from "../auth/useMe";
import { LookPicker, lookName, useLooks, type Look } from "../scripts/Looks";
import { SongSetting } from "../scripts/VideoSong";
import { useRail } from "../useMedia";
import { errorText as errorClass } from "../ui";
import { useHead } from "../videos/VideoHead";

const setting = "inline-flex h-control lg:h-[30px] shrink-0 items-center gap-[5px] whitespace-nowrap rounded-sm border border-border-button bg-surface px-[9px] text-xs font-medium text-text";
type Money = components["schemas"]["Money"];

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
export type Choice = { id: string; label: string; price?: string; note?: string; noLipSync?: boolean; off?: boolean; body: SettingIn };
/** `locked`: why it can't be changed here (a script-made video keeps its script's style, Reed's walk item 7); shown, never picked. */
export type Field = { key: string; label: string; current: string; valueLabel: string; price?: string; locked?: string; choices: Choice[] };

const credits = creditsText; // a rate: one decimal, rounded up (rule 36)
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

/** How the presenter appears, in L3's words (S-gaps-05): the style picks first; a person or the director can switch it. */
const HOW = {
  talks: { label: "Talks to camera", how: "HeyGen, with B-roll cut in" },
  corner: { label: "In a corner", how: "HeyGen, over the B-roll" },
  acts: { label: "Acts in the story", how: "in the scenes with the cast" },
} as const;

/** The settings as the row shows them: one field per setting, each choice carrying the body that switches to it. */
export function fieldsOf(s: SettingsOut, looks: { id: string; name: string; on: boolean }[] | null | undefined, lookLocked = false): Field[] {
  const auto = <M extends { name: string; default: boolean }>(ms: M[]) => ms.find((m) => m.default) ?? ms[0];
  const video = auto(s.video_models);
  const image = auto(s.image_models);
  const nowVideo = s.video_model ? s.video_models.find((m) => m.id === s.video_model) : undefined;
  const nowImage = s.image_model ? s.image_models.find((m) => m.id === s.image_model) : undefined;
  return [
    { key: "aspect_ratio", label: "Shape", current: s.aspect_ratio, valueLabel: s.aspect_ratio, choices: s.shapes.map((x) => ({ id: x, label: x, body: { aspect_ratio: x as SettingIn["aspect_ratio"] } })) },
    ...Object.entries(s.flavours).map(([product, options]) => {
      const now = s.product_variants[product] ?? options[0]; // a product missing from the picks is on its default
      return { key: `flavour:${product}`, label: Object.keys(s.flavours).length > 1 ? `Flavour (${product})` : "Flavour", current: now, valueLabel: now, choices: options.map((o) => ({ id: o, label: o, body: { product_variants: { [product]: o } } })) };
    }),
    ...(looks ? [{ key: "look", label: "Style", current: s.look, valueLabel: lookName(looks as Look[], s.look), locked: lookLocked ? "set on the script" : undefined, choices: looks.map((l) => ({ id: l.id, label: l.name, off: !l.on, body: { look: l.id } })) }] : []),
    {
      key: "video_model",
      label: "Video model",
      current: s.video_model ?? "auto",
      valueLabel: nowVideo?.name ?? "Auto",
      price: perSecond((nowVideo ?? video)?.credits_per_second ?? 0),
      choices: [
        { id: "auto", label: video ? `Auto (${video.name})` : "Auto", price: video && perSecond(video.credits_per_second), noLipSync: video && !video.lip_sync, body: { video_model: null } },
        ...s.video_models.map((m) => ({ id: m.id, label: m.name, price: perSecond(m.credits_per_second), noLipSync: !m.lip_sync, body: { video_model: m.id } })),
      ],
    },
    // How a Presenter video's presenter appears (S-gaps-05 V1 and L3); only on a video with a presenter.
    ...(s.presenter_now
      ? [{ key: "presenter", label: "Presenter", current: s.presenter_now, valueLabel: HOW[s.presenter_now].label, choices: (Object.keys(HOW) as (keyof typeof HOW)[]).map((id) => ({ id, label: HOW[id].label, note: HOW[id].how, body: { presenter: id } })) }]
      : []),
    {
      key: "image_model",
      label: "Picture model",
      current: s.image_model ?? "auto",
      valueLabel: nowImage?.name ?? "Auto",
      price: perStill((nowImage ?? image)?.credits_per_still ?? 0),
      choices: [
        { id: "auto", label: image ? `Auto (${image.name})` : "Auto", price: image && perStill(image.credits_per_still), body: { image_model: null } },
        ...s.image_models.map((m) => ({ id: m.id, label: m.name, price: perStill(m.credits_per_still), body: { image_model: m.id } })),
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
  lines.push(`To finish: about ${credits(wholeCredits(p.to_finish_credits))} (planned; was ${wholeCredits(p.was_credits)}).`);
  return lines;
}

/** A setting that can't be changed here, as one plain line: "Style: House · set on the script" (item 7); `chip`: as a
 *  chip in this video's settings row, with that label. */
export function LockedSetting({ field: f, chip }: { field: Field; chip?: string }) {
  if (chip)
    // This video's settings row (S-gaps-05 V1): a lock on the chip, the reason on hover.
    return (
      <span className={setting} title={`${f.label} is ${f.locked}`}>
        <Lock size={12} strokeWidth={1.75} aria-hidden className="text-muted" />
        <span className="font-normal text-muted">{chip}</span> {f.valueLabel}
      </span>
    );
  return (
    <span className="inline-flex min-h-control items-center gap-1.5 px-2 text-sm">
      <Lock size={16} strokeWidth={1.75} aria-hidden className="text-muted" />
      <span>
        <span className="text-muted">Style:</span> {f.valueLabel} <span className="text-muted">· {f.locked}</span>
      </span>
    </span>
  );
}

// The row's own words (S-gaps-05 V1): a presenter's or narrator's clips are its B-roll.
const ROW: Record<string, string> = { video_model: "Video model", image_model: "Pictures" };

/** This video's settings, at the top of its Plan tab (S-gaps-05 V1; flows VS1): Shape · Flavour · Style · Video model ·
 *  Presenter (a presenter's video) · Pictures · Language, and the Song on a song video, for the owner and editors (editors see credits). A pick is previewed,
 *  confirmed (Not yet / Switch) and applied; then a line says the new "up to" and offers Undo. The director keeps what a
 *  person changed. On a phone it is one line that opens a sheet. */
export function VideoSettings({ project: p, finished, song = true, broll, notMade }: { project: Project; finished: boolean; song?: boolean; broll?: boolean; notMade: number }) {
  const rail = useRail();
  const owner = useMe().data?.role === "owner";
  const queryClient = useQueryClient();
  const toast = useToast();
  const looks = useLooks();
  const settings = useVideoSettings(p.id);
  const head = useHead(p.id);
  const [changed, setChanged] = useState<{ label: string; was?: Money | null; now?: Money | null; model: boolean; undo: () => void } | null>(null);
  const [sheet, setSheet] = useState(false);
  const [picking, setPicking] = useState<Field | null>(null);
  const [asking, setAsking] = useState<{ field: Field; choice: Choice } | null>(null);
  const preview = useQuery({
    enabled: !!asking,
    queryKey: ["video-settings-preview", p.id, asking?.choice.body],
    queryFn: () => must(api.POST("/projects/{project_id}/settings/preview", { params: { path: { project_id: p.id } }, body: asking!.choice.body })).then((r) => r.data! as PreviewOut),
  });
  const refresh = () => Promise.all([["video-settings", p.id], ["director", p.id], ["project", p.id], ["project-estimate", p.id], ["storyboard", p.id], ["project-clips", p.id], ["assets", p.id], ["missing-looks", p.id]].map((k) => queryClient.invalidateQueries({ queryKey: k })));
  const apply = useMutation({ mutationFn: (body: SettingIn) => must(api.POST("/projects/{project_id}/settings", { params: { path: { project_id: p.id } }, body })).then((r) => r.data!) });
  const label = (f: Field) => (f.key === "video_model" && broll ? "B-roll model" : (ROW[f.key] ?? f.label));
  const switchTo = (field: Field, choice: Choice) => {
    const before = head.data?.up_to;
    apply.mutate(choice.body, {
      onSuccess: async ({ was }) => {
        setAsking(null);
        setPicking(null);
        setSheet(false); // on a phone the line with the new price and Undo shows under the row
        await refresh();
        const now = (await head.refetch()).data?.up_to;
        // Undo sends `was` back with undo: true, so it is never refused (even over the limit); the old stills and takes become current again.
        const undo = () => apply.mutate({ ...(was as SettingIn), undo: true }, { onSuccess: () => (setChanged(null), void refresh(), void head.refetch()), onError: (e) => toast(e.message, undefined, "error") });
        setChanged({ label: label(field), was: before, now, model: field.key === "video_model", undo });
      },
    });
  };

  if (settings.isPending) return <Skeleton className="h-control" />;
  if (settings.isError || !settings.data) return null; // the server doesn't offer settings yet: nothing to press
  // A video made from a published script keeps its script's style (Next-Server's ProjectOut.look_locked); legacy videos switch.
  const fields = fieldsOf(settings.data, looks.data, p.look_locked);
  const chip = (f: Field) =>
    f.locked ? (
      <LockedSetting key={f.key} field={f} chip={label(f)} />
    ) : (
      <button key={f.key} type="button" className={`${setting} hover:bg-surface-2`} aria-haspopup="dialog" title={f.price} onClick={() => setPicking(f)}>
        <span className="font-normal text-muted">{label(f)}</span> {f.valueLabel}
        <ChevronDown size={12} strokeWidth={1.75} aria-hidden />
      </button>
    );
  const language = (
    <span className={setting} title="From the script">
      <span className="font-normal text-muted">Language</span> {languageName(settings.data.language)}
    </span>
  );
  const items = (
    <>
      {fields.map(chip)}
      {p.song && song && <SongSetting project={p} />}
      {language}
    </>
  );
  const money = (m?: Money | null) => (!m ? "" : m.usd != null ? `up to $${m.usd.toFixed(2)}` : `up to ${Math.ceil(m.credits - 1e-9)} credits`);
  const note = changed && (
    <p role="status" className="flex items-center gap-2 rounded-md bg-accent-soft px-2.5 py-2 text-sm text-accent-text">
      <RefreshCw size={14} strokeWidth={1.75} aria-hidden className="shrink-0" />
      <span>
        {changed.label} changed
        {changed.was && changed.now && money(changed.was) !== money(changed.now) ? (
          <>
            : {money(changed.was)} → <b className="font-semibold">{money(changed.now)}</b>.
          </>
        ) : (
          "."
        )}
        {changed.model && notMade > 0 && ` ${notMade} clip${notMade === 1 ? "" : "s"} not made yet will use it.`}
      </span>
      <button type="button" className="ml-auto shrink-0 font-semibold hover:underline max-lg:min-h-control max-lg:px-2" onClick={changed.undo}>
        Undo
      </button>
    </p>
  );
  const row = rail ? (
    <section aria-label="Video settings" className="flex flex-col gap-2">
      <p className="text-xs font-semibold text-muted">This video’s settings</p>
      <div className="flex flex-wrap gap-2">{items}</div>
      {note}
    </section>
  ) : (
    <Button variant="ghost" spread icon={Settings2} trailing={ChevronDown} aria-haspopup="dialog" onClick={() => setSheet(true)}>
      <span className="block truncate">Settings: {fields.map((f) => f.valueLabel).join(" · ")}</span>
    </Button>
  );

  const pick = (f: Field, c: Choice) => (c.id === f.current ? setPicking(null) : setAsking({ field: f, choice: c }));
  const lookOpen = picking?.key === "look" && looks.data;
  const lines = asking && preview.data ? confirmText(asking.field, asking.choice, preview.data, finished) : null;
  return (
    <>
      {row}
      {!rail && note}
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
          holdReason={preview.isError ? preview.error.message : apply.isError ? apply.error.message : null}
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
                aria-pressed={c.id === field.current}
                onClick={() => onPick(c)}
                className={`flex min-h-control w-full flex-wrap items-center gap-x-2 gap-y-1 rounded-md border px-3 py-2 text-left ${c.id === field.current ? "border-accent bg-accent-soft" : "border-border-strong hover:bg-surface-2"}`}
              >
                <span className="font-medium">{c.label}</span>
                {c.price && <span className="text-sm text-muted tabular-nums">· {c.price}</span>}
                {c.note && <span className="text-sm text-muted">· {c.note}</span>}
                {c.noLipSync && <Badge>No lip-sync</Badge>}
              </button>
            </li>
          ))}
      </ul>
    </Panel>
  );
}
