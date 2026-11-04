import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../components";
import { useScript } from "../scripts/useScript";
import { SendError, useEstimate, useFreestyleActions, type Freestyle, type Shape } from "./useFreestyle";

/** "0:32" */
export const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
/** A version that can become a video: one with its words finished (any of them; publishing isn't needed, #1190). */
export const finished = (v: { status: string }) => v.status !== "draft";

/** Making a video from one script's version (E_PickInComposer, E_ScriptMakeVideo): the version and shape picked, the
 *  send's "up to" price, the send itself, and a version that already has a video (the Producer: never a dead end; Open it,
 *  or Make another through the usual holds). */
export function useMakeFromScript(scriptId: number | null, onCreated: (fs: Freestyle) => void, start?: number) {
  const script = useScript(scriptId ?? 0);
  const s = scriptId ? script.data : undefined;
  const versions = (s?.versions ?? []).filter(finished);
  const [picked, setPicked] = useState<number | null>(start ?? null);
  const [shape, setShape] = useState<Shape>("9:16");
  const version = versions.find((v) => v.slot === picked) ?? versions[0];
  const source = s && version ? { script_id: s.id, slot: version.slot, shape } : null;
  const estimate = useEstimate(source);
  const create = useFreestyleActions(null).create;
  const refused = create.error instanceof SendError ? create.error.hasVideo : undefined;
  const video = refused?.project_id ?? version?.project_id ?? null;
  const send = (another = false) => source && !create.isPending && create.mutate({ ...source, ...(another ? { make_another: true } : {}) }, { onSuccess: onCreated });
  const pick = (slot: number) => {
    setPicked(slot);
    create.reset();
  };
  return { script: s, loading: !!scriptId && script.isPending, versions, version, pick, shape, setShape: (x: Shape) => (setShape(x), create.reset()), price: refused?.up_to ?? estimate.data, create, video, send, error: create.isError && !refused ? create.error.message : null };
}
export type Making = ReturnType<typeof useMakeFromScript>;

/** The picked version already has a video: open it, or make another (its own price, the usual holds). */
export function HasVideo({ m, brandId }: { m: Making; brandId: number }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3" role="status">
      <p className="text-sm">
        This version already has a video ·{" "}
        <Link to={`/b/${brandId}/videos/${m.video}`} className="text-accent-text underline-offset-2 hover:underline">
          Open it
        </Link>
      </p>
      <Button variant="secondary" dense busy={m.create.isPending} price={m.price} charge="estimate" onClick={() => m.send(true)}>
        Make another
      </Button>
    </div>
  );
}
