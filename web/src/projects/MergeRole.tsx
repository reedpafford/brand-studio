import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { Badge, Button, Dialog } from "../components";
import { Sheet } from "./Sheet";
import { useMedia } from "../useMedia";
import { errorText as errorClass } from "../ui";

/** A role as the dialog lists it. */
export type MergeTarget = { id: number; role: string; kind: string; locked: boolean; facts?: string };
/** What a merge moves (the same reply for the preview and the real thing). */
export type Moved = { shots: string[]; lines: { version: string | number; line: number }[]; look_unused: { name: string } | null };
/** The two calls behind the dialog; Cast and Assets each bring their own routes. */
export type MergeAdapter = { preview: (into: number) => Promise<Moved>; merge: (into: number) => Promise<Moved> };

const LETTERS = ["A", "B", "C"];
const versionName = (v: string | number) => (typeof v === "number" ? (LETTERS[v] ?? String(v)) : v);
const and = (l: string[]) => (l.length < 2 ? l.join("") : `${l.slice(0, -1).join(", ")} and ${l.at(-1)}`);
const count = (n: number, noun: string) => `${n} ${noun}${n === 1 ? "" : "s"}`;

/** "A lines 4 and 7, B line 4" from the lines a merge touches. */
export const linesText = (lines: Moved["lines"]) => {
  const by = new Map<string, number[]>();
  for (const l of lines) by.set(versionName(l.version), [...(by.get(versionName(l.version)) ?? []), l.line]);
  return [...by].map(([v, n]) => `${v} ${n.length === 1 ? "line" : "lines"} ${and(n.map(String))}`).join(", ");
};

/** "Merged into Kimchi. 3 shots and 5 lines moved." */
export const mergedText = (into: string, m: Moved) => `Merged into ${into}. ${count(m.shots.length, "shot")} and ${count(m.lines.length, "line")} moved.`;

/** What picking a role would change, in words. Nothing until one is picked. */
function WhatMoves({ role, target, moved }: { role: string; target: MergeTarget; moved: Moved }) {
  return (
    <div className="space-y-1" aria-label={`What moves to ${target.role}`}>
      <h4 className="text-xs font-medium text-faint">What moves to {target.role}</h4>
      <ul className="space-y-1 text-sm">
        <li>{moved.shots.length === 0 ? "No shots." : `${count(moved.shots.length, "shot")}: ${moved.shots.join(", ")}`}</li>
        <li>
          {moved.lines.length === 0 ? (
            "No lines in the script."
          ) : (
            <>
              {count(moved.lines.length, "line")} in the script: {linesText(moved.lines)}
              <span className="block text-muted">The words stay exactly as written; only who says them changes.</span>
            </>
          )}
        </li>
        {target.locked ? <li>{target.role} keeps {target.role}'s look.</li> : moved.look_unused && <li>The look made for {moved.look_unused.name || role} isn't used any more, but it isn't deleted.</li>}
      </ul>
    </div>
  );
}

/** "Merge {role} into…": pick who it is the same person as, see what moves (free), then merge. A sheet on a phone. */
export function MergeRole(props: {
  role: string;
  others: MergeTarget[];
  /** The role the server suggests (from "These may be the same person"). */
  suggested?: number | null;
  /** On Assets: the script's cast stays as it is. */
  videoOnly?: boolean;
  adapter: MergeAdapter;
  onMerged: (into: MergeTarget, moved: Moved) => void;
  onClose: () => void;
}) {
  const phone = useMedia("(max-width: 639px)");
  const [picked, setPicked] = useState<number | null>(props.suggested ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const target = props.others.find((o) => o.id === picked) ?? null;
  const preview = useQuery({ queryKey: ["merge-preview", props.role, picked], enabled: picked !== null, queryFn: () => props.adapter.preview(picked!) });
  const hold = target ? null : "Pick who this is the same person as";
  const go = async () => {
    if (!target || busy) return;
    setBusy(true);
    setError(null);
    try {
      props.onMerged(target, await props.adapter.merge(target.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't merge them.");
      setBusy(false);
    }
  };
  const title = `Merge ${props.role} into…`;
  const body = (
    <div className="space-y-3">
      {props.videoOnly && <p className="text-xs text-muted">This changes this video only.</p>}
      <fieldset className="space-y-1">
        <legend className="mb-1 text-sm font-medium text-text">Who is this the same person as?</legend>
        {props.others.map((o) => (
          <label key={o.id} className={`flex min-h-11 cursor-pointer items-center gap-3 rounded-md border px-3 py-2 sm:min-h-9 ${picked === o.id ? "border-accent bg-accent-soft" : "border-border"}`}>
            <input type="radio" name="merge-into" className="size-5 sm:size-4" checked={picked === o.id} onChange={() => setPicked(o.id)} />
            <span className="min-w-0 flex-1 text-sm">
              <span className="font-medium text-text">{o.role}</span>
              <span className="text-muted"> · {[o.kind, o.facts].filter(Boolean).join(" · ")}</span>
            </span>
            {o.locked && <Badge icon={Lock}>Locked</Badge>}
          </label>
        ))}
      </fieldset>
      {target && preview.data && <WhatMoves role={props.role} target={target} moved={preview.data} />}
      {target && preview.isError && <p role="alert" className={errorClass}>Couldn't check what would move.</p>}
      {error && <p role="alert" className={errorClass}>{error}</p>}
    </div>
  );
  if (phone)
    return (
      <Sheet title={title} onClose={props.onClose} closeLabel="Cancel">
        {body}
        <Button className="w-full" busy={busy} disabled={!!hold} reason={hold} onClick={go}>
          Merge · Free
        </Button>
      </Sheet>
    );
  return (
    <Dialog title={title} cancelLabel="Cancel" actionLabel="Merge · Free" busy={busy} holdReason={hold} onCancel={props.onClose} onConfirm={go}>
      {body}
    </Dialog>
  );
}
