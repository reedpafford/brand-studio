import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Settings2 } from "lucide-react";
import { errorText } from "../api/client";
import type { components } from "../api/schema";
import { Badge, Button, Dialog, Panel, Skeleton, useToast, wholeCredits } from "../components";
import { useMe } from "../auth/useMe";
import { LookPicker, useLooks } from "../scripts/Looks";
import { SongSetting } from "../scripts/VideoSong";
import { useRail } from "../useMedia";
import { errorText as errorClass } from "../ui";

type Project = components["schemas"]["ProjectOut"];
type Choice = { id: string; label: string; price_label?: string | null; on: boolean; no_lip_sync?: boolean; over_cap?: boolean };
type Field = { key: string; label: string; value: string; value_label: string; price_label?: string | null; choices: Choice[] };
type Settings = { fields: Field[]; language: { label: string; from: string } | null };
type Preview = { to_finish_credits: number; was_credits: number; stills_out_of_date: number; clips_out_of_date: number; sung_to_broll: number; over_budget: boolean; over_cap: boolean; reason: string | null };

// Builder-Server-7's n09 routes (flows VS1). Not in the generated schema yet: swap to api.GET/POST after `npm run api`.
async function call<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const res = await fetch(new Request(`${location.origin}/api${path}`, { method, credentials: "include", headers: body ? { "Content-Type": "application/json" } : undefined, body: body ? JSON.stringify(body) : undefined }));
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(errorText(data));
  return data as T;
}

/** The video's settings, or an error where the server doesn't offer them yet (then the row stays hidden). */
export function useVideoSettings(projectId: number) {
  return useQuery({ queryKey: ["video-settings", projectId], queryFn: () => call<Settings>("GET", `/projects/${projectId}/settings`), retry: false });
}

const n = (k: number, one: string) => `${k} ${one}${k === 1 ? "" : "s"}`;

/** What a switch costs and changes, said once: the finished warning first (LW1), Sung → B-roll, what goes out of date, then the new total. */
function confirmText(field: Field, choice: Choice, p: Preview, finished: boolean) {
  const lines: string[] = [];
  const later = [p.stills_out_of_date && n(p.stills_out_of_date, "still"), p.clips_out_of_date && n(p.clips_out_of_date, "clip")].filter(Boolean).join(" and ");
  if (finished) lines.push(`This video is finished.${later ? ` Changing the ${field.label.toLowerCase()} puts ${later} out of date;` : ""} your current final cut stays downloadable until you make a new one.`);
  if (p.sung_to_broll > 0) lines.push(`${choice.label} can't lip-sync. Your ${n(p.sung_to_broll, "Sung shot")} become${p.sung_to_broll === 1 ? "s" : ""} B-roll (picture only).`);
  if (later && !finished) lines.push(`${later[0].toUpperCase()}${later.slice(1)} already made stay as they are and show Out of date.`);
  lines.push(`To finish: about ${wholeCredits(p.to_finish_credits)} credits (was ${wholeCredits(p.was_credits)}).`);
  return lines;
}

/** The Video settings row (flows VS1): Shape · Flavour · Look · Video model · Picture model · Language, and the Song on a song video.
 *  Each setting shows its choice and price; a pick is previewed, confirmed (Not yet / Switch), applied with Undo. On a phone it is one line that opens a sheet. */
export function VideoSettings({ project: p, finished }: { project: Project; finished: boolean }) {
  const rail = useRail();
  const owner = useMe().data?.role === "owner";
  const queryClient = useQueryClient();
  const toast = useToast();
  const looks = useLooks();
  const key = ["video-settings", p.id];
  const settings = useVideoSettings(p.id);
  const [sheet, setSheet] = useState(false);
  const [picking, setPicking] = useState<Field | null>(null);
  const [asking, setAsking] = useState<{ field: Field; choice: Choice } | null>(null);
  const preview = useQuery({
    enabled: !!asking,
    queryKey: ["video-settings-preview", p.id, asking?.field.key, asking?.choice.id],
    queryFn: () => call<Preview>("POST", `/projects/${p.id}/settings/preview`, { key: asking!.field.key, value: asking!.choice.id }),
  });
  const refresh = () => Promise.all([key, ["project", p.id], ["project-estimate", p.id], ["storyboard", p.id], ["project-clips", p.id]].map((k) => queryClient.invalidateQueries({ queryKey: k })));
  const apply = useMutation({
    mutationFn: (b: { key: string; value: string }) => call<{ was: string }>("POST", `/projects/${p.id}/settings`, b),
  });
  const switchTo = (field: Field, choice: Choice) =>
    apply.mutate(
      { key: field.key, value: choice.id },
      {
        onSuccess: async ({ was }) => {
          setAsking(null);
          setPicking(null);
          await refresh();
          // Switching back makes the old stills and takes current again (the server kept them).
          toast(`${field.label}: ${choice.label}.`, () => apply.mutate({ key: field.key, value: was }, { onSuccess: () => void refresh(), onError: (e) => toast(e.message, undefined, "error") }));
        },
      },
    );

  if (settings.isPending) return <Skeleton className="h-control" />;
  if (settings.isError || !settings.data) return null; // the server doesn't offer settings yet: nothing to press
  const s = settings.data;
  const shown = (f: Field) => ({ ...f, choices: f.choices.filter((c) => owner || c.on) }); // editors never see choices that are off
  const chip = (f: Field) => (
    <Button key={f.key} variant="ghost" dense trailing={ChevronDown} aria-haspopup="dialog" onClick={() => setPicking(shown(f))}>
      <span className="text-muted">{f.label}:</span> {f.value_label}
      {f.price_label && <span className="text-xs text-muted tabular-nums">· {f.price_label}</span>}
    </Button>
  );
  const language = s.language && <Badge>Language: {s.language.label} (from the {s.language.from})</Badge>;
  const song = p.song ? <SongSetting project={p} /> : null;
  const items = (
    <>
      {s.fields.map(chip)}
      {song}
      {language}
    </>
  );
  const summary = s.fields.map((f) => f.value_label).join(" · ");
  const row = rail ? (
    <section aria-label="Video settings" className="flex flex-wrap items-center gap-1">
      <Settings2 size={20} strokeWidth={1.75} aria-hidden className="text-muted" />
      {items}
    </section>
  ) : (
    <Button variant="ghost" icon={Settings2} trailing={ChevronDown} className="w-full justify-start" aria-haspopup="dialog" onClick={() => setSheet(true)}>
      <span className="min-w-0 truncate">Settings: {summary}</span>
    </Button>
  );

  const pick = (f: Field, c: Choice) => (c.id === f.value ? setPicking(null) : setAsking({ field: f, choice: c }));
  const look = picking?.key === "look" && looks.data;
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
      {picking && look && (
        <LookPicker
          current={picking.value}
          looks={looks.data!.filter((l) => owner || l.on)}
          busy={null}
          error={null}
          onPick={(l) => pick(picking, picking.choices.find((c) => c.id === l.id) ?? { id: l.id, label: l.name, on: l.on })}
          onClose={() => setPicking(null)}
        />
      )}
      {picking && !look && (
        <Panel title={picking.label} onClose={() => setPicking(null)}>
          <ul className="space-y-2">
            {picking.choices.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  disabled={!!c.over_cap}
                  aria-pressed={c.id === picking.value}
                  onClick={() => pick(picking, c)}
                  className={`flex min-h-control w-full flex-wrap items-center gap-x-2 gap-y-1 rounded-md border px-3 py-2 text-left disabled:opacity-60 ${c.id === picking.value ? "border-accent bg-accent-soft" : "border-border-strong hover:bg-surface-2"}`}
                >
                  <span className="font-medium">{c.label}</span>
                  {c.price_label && <span className="text-sm text-muted tabular-nums">· {c.price_label}</span>}
                  {c.no_lip_sync && <Badge>No lip-sync</Badge>}
                  {!c.on && <Badge>Off</Badge>}
                  {c.over_cap && <span className="w-full text-sm text-muted">Over the video limit</span>}
                </button>
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {asking && (
        <Dialog
          title={asking.field.key === "shape" ? `Change to ${asking.choice.label}?` : `Switch to ${asking.choice.label}?`}
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
