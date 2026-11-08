import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Palette } from "lucide-react";
import { api, errorText, must } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Badge, Button, Card, Dialog, Panel, Skeleton } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { PickLabel, pickClass } from "./ScriptFrame";
import { useFormats } from "./useFormats";

/** A look: how the pictures are drawn (flows ST1; Next-Server's GET /looks, #873). House first, then Reed's order. */
export type Look = components["schemas"]["LookOut"];

// One look per style: GET /looks lists one card per style, each with its lanes ({id, name}: "paper-flat", "Paper · Flat
// Paper"; #1139). A video, brand or sheet may be on a lane; pickers offer the styles only, and a lane is chosen per video.
/** A look's name wherever it's shown: a style's own, or a lane's ("Paper · Flat Paper"); for a lane the list doesn't name,
 *  its style's name and the lane's own words ("Paper · Flat"). Never a raw id like "paper-flat". */
export function lookName(looks: Look[] | null | undefined, id: string | null | undefined): string {
  if (!id || id === "house") return looks?.find((l) => l.id === "house")?.name ?? "House";
  const own = looks?.find((l) => l.id === id);
  if (own) return own.name;
  const lane = looks?.flatMap((l) => l.lanes ?? []).find((x) => x.id === id);
  if (lane) return lane.name;
  const parent = looks?.find((l) => id.startsWith(`${l.id}-`));
  const words = (t: string) => t.split("-").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  return parent ? `${parent.name} · ${words(id.slice(parent.id.length + 1))}` : words(id);
}

/** The style a look belongs to: the card a lane sits in, or the look itself (a picker marks it In use). */
export const styleOf = (looks: Look[] | null | undefined, id: string): string =>
  looks?.find((l) => (l.lanes ?? []).some((x) => x.id === id))?.id ?? looks?.find((l) => id.startsWith(`${l.id}-`))?.id ?? id;

/** Why a style isn't made in this format, or null: "Movie is made only as Dialogue: …", the server's words (QA on #1440). */
export function notMadeAs(l: Look, format: string | null | undefined, formats: { id: string; name: string }[]): string | null {
  if (!l.formats?.length || !format || l.formats.includes(format)) return null;
  const names = l.formats.map((id) => formats.find((f) => f.id === id)?.name ?? id).join(" or ");
  return `${l.name} is made only as ${names}${l.formats_why ? `: ${l.formats_why}` : ""}.`;
}

/** The looks, or null where the server doesn't offer them (the pickers stay hidden: never a press with nothing behind it). */
export function useLooks() {
  return useQuery({
    queryKey: ["looks"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/looks");
      if (response.status === 404) return null;
      if (!response.ok) throw new Error(errorText(error));
      return data ?? null;
    },
    staleTime: 60_000,
  });
}

/** The picker: one card per look with its sample still, name and line. Off looks are greyed for editors; the owner may try one on their own work.
 *  A style not made in the script's `format` (Movie: Dialogue only) is greyed for everyone, with why. */
export function LookPicker({ current, looks, onPick, busy, error, onClose, format }: { current: string; looks: Look[]; onPick: (l: Look) => void; busy: string | null; error: string | null; onClose: () => void; format?: string | null }) {
  const owner = useMe().data?.role === "owner";
  const formats = useFormats().data ?? [];
  return (
    <Panel title="Style" onClose={onClose}>
      <p className="mb-3 text-sm text-muted">How the pictures are drawn.</p>
      {error && <p role="alert" className={`mb-3 ${errorClass}`}>{error}</p>}
      <ul className="grid gap-3 sm:grid-cols-2 [&>li]:min-w-0">
        {looks.map((l) => {
          const inUse = l.id === styleOf(looks, current);
          const why = notMadeAs(l, format, formats);
          const closed = (!l.on && !owner) || !!why;
          return (
            <li key={l.id}>
              <Card className={`h-full space-y-2 ${closed ? "opacity-60" : ""}`}>
                <div className="grid aspect-[9/16] max-h-64 w-full place-items-center overflow-hidden rounded-md bg-surface-2">
                  {l.sample_still_id ? <img src={fileUrl(l.sample_still_id)} alt={`${l.name} sample`} className="h-full w-full object-cover" loading="lazy" /> : <span className="text-sm text-muted">No sample yet</span>}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="type-card">{l.name}</h3>
                  {inUse && <Badge tone="accent">In use</Badge>}
                  {!l.on && <Badge>Off</Badge>}
                </div>
                <p className="text-sm text-muted">{l.blurb}</p>
                {!l.on && owner && <p className="text-sm text-warning">Off for editors: only you can use it.</p>}
                {!inUse && (
                  <Button variant="secondary" disabled={closed} reason={why ?? (closed ? "Not switched on yet" : null)} busy={busy === l.id} onClick={() => onPick(l)}>
                    Use this style
                  </Button>
                )}
              </Card>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

/** What changing a script's look would take (Next-Server's #943), read before the change. */
type LookChange = components["schemas"]["LookChangeOut"];
const lookChange = async (scriptId: number, look: string): Promise<LookChange> =>
  (await must(api.GET("/scripts/{script_id}/look-change", { params: { path: { script_id: scriptId }, query: { look } } }))).data!;

/** "Look: House ▾" for a script or a video: opens the picker, saves at once (free) with Undo. Read only once published. Hidden until the server offers looks. */
export function LookSetting({ value, scriptId, queryKey, readOnly, format }: { value: string | null | undefined; scriptId: number; queryKey: unknown[]; readOnly?: boolean; format?: string | null }) {
  const looks = useLooks();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  // ST1: once roles would need a new look, the change is confirmed with what it takes to finish.
  const [asking, setAsking] = useState<{ look: Look; change: LookChange } | null>(null);
  const check = useMutation({ mutationFn: (look: string) => lookChange(scriptId, look) });
  const save = useMutation({
    mutationFn: (look: string) => must(api.PATCH("/scripts/{script_id}", { params: { path: { script_id: scriptId } }, body: { look } })),
    onSuccess: async (_r, look) => {
      await queryClient.invalidateQueries({ queryKey });
      return look;
    },
  });
  if (looks.isPending) return <Skeleton className="h-control w-32" />;
  if (!looks.data) return null; // the server doesn't offer looks yet
  const id = value ?? looks.data[0]?.id ?? "house";
  const name = lookName(looks.data, id);
  if (readOnly) return <Badge icon={Palette}>Style: {name}</Badge>;
  const change = (l: Look) => {
    const was = id;
    save.mutate(l.id, {
      onSuccess: () => {
        setOpen(false);
        setAsking(null);
        toast(`The style is ${l.name}.`, () => save.mutate(was));
      },
    });
  };
  const pick = (l: Look) =>
    check.mutate(l.id, { onSuccess: (c) => (c.roles.length > 0 ? setAsking({ look: l, change: c }) : change(l)) });
  const refused = (save.error ?? check.error)?.message ?? null;
  const n = asking?.change.roles.length ?? 0;
  return (
    <>
      <Button variant="ghost" dense trailing={ChevronDown} className={pickClass} aria-label={`Style: ${name}`} aria-haspopup="dialog" onClick={() => setOpen(true)}>
        <PickLabel label="Style">{name}</PickLabel>
      </Button>
      {refused && !open && <p role="alert" className={errorClass}>{refused}</p>}
      {open && <LookPicker current={id} looks={looks.data} busy={save.isPending ? (save.variables ?? null) : check.isPending ? (check.variables ?? null) : null} error={refused} onPick={pick} onClose={() => setOpen(false)} format={format} />}
      {asking && (
        <Dialog title={`Change to ${asking.look.name}?`} cancelLabel="Not yet" actionLabel="Change" busy={save.isPending} holdReason={asking.change.over_budget ? asking.change.reason || "That would go over this week's credits." : null} onCancel={() => setAsking(null)} onConfirm={() => change(asking.look)}>
          {n} role{n === 1 ? "" : "s"} need{n === 1 ? "s" : ""} a new look ({asking.change.roles.join(", ")}). To finish: about {asking.change.to_finish_credits} credits (planned; was {asking.change.was_credits}).
        </Dialog>
      )}
    </>
  );
}
