import { useState } from "react";
import { fileUrl } from "../api/upload";
import { Badge, Button } from "../components";
import { useToast } from "../toast";
import { serverTime } from "../time";
import { errorText as errorClass } from "../ui";

/** OR3 (flows: Preferred and going back; Builder-Server-8's #957). Every Go back / Use this one is free, never refused over
 *  the budget, and has Undo; what later steps made from the one before shows Out of date with its usual redo. */

const when = (iso: string | null | undefined) => (iso ? serverTime(iso).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : null);
type Maker = { id: number; name: string } | null | undefined;
const byline = (at: string | null | undefined, by: Maker) => [when(at), by?.name].filter(Boolean).join(" · ");

/** "Earlier stills · N" under a frame: each one it had, newest first, with Use this one. Undo puts the still in use back. */
export function EarlierStills({ label, current, earlier, onUse }: { label: string; current: number | null; earlier: { file_id: number; made_at?: string | null; made_by?: Maker }[]; onUse: (file: number) => Promise<unknown> }) {
  const toast = useToast();
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (earlier.length === 0) return null;
  const use = async (file: number) => {
    setBusy(file);
    setError(null);
    try {
      await onUse(file);
      const was = current;
      toast(`Clip ${label} uses the earlier still. Its take shows Out of date.`, was !== null ? () => void onUse(was).catch((e: Error) => toast(e.message, undefined, "error")) : undefined);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  return (
    <details className="text-sm">
      <summary className="flex min-h-11 cursor-pointer items-center sm:min-h-8">Earlier stills · {earlier.length}</summary>
      {error && <p role="alert" className={errorClass}>{error}</p>}
      <ul className="mt-2 grid grid-cols-3 gap-2" aria-label={`Earlier stills for clip ${label}`}>
        {[...earlier].reverse().map((e) => (
          <li key={e.file_id} className="space-y-1">
            <img src={fileUrl(e.file_id)} alt={`An earlier still for clip ${label}`} className="aspect-square w-full rounded-sm object-cover" loading="lazy" />
            {byline(e.made_at, e.made_by) && <p className="text-xs text-muted">{byline(e.made_at, e.made_by)}</p>}
            <Button variant="ghost" dense busy={busy === e.file_id} disabled={busy !== null && busy !== e.file_id} onClick={() => void use(e.file_id)}>
              Use this one
            </Button>
          </li>
        ))}
      </ul>
    </details>
  );
}

/** One saved version in a "Versions" list: when, who, and Go back to this (none on the one in use). */
export type Version = { key: string; made_at: string | null; made_by?: Maker; note?: string; current: boolean };

/** "Versions · N" for a storyboard, a clip prompt or a breakdown. Go back to this runs `onUse`; the toast's Undo runs the
 *  undo it returns (the server's own: the one in hand again). */
export function VersionList({ title, versions, onUse, said, hold }: { title: string; versions: Version[]; onUse: (key: string) => Promise<(() => Promise<unknown>) | null>; said: string; hold?: string | null }) {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (versions.length < 2) return null;
  const go = async (key: string) => {
    setBusy(key);
    setError(null);
    try {
      const undo = await onUse(key);
      toast(said, undo ? () => void undo().catch((e: Error) => toast(e.message, undefined, "error")) : undefined);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  return (
    <details className="rounded-lg border border-border bg-surface px-4 text-sm">
      <summary className="flex min-h-11 cursor-pointer items-center py-2 font-medium">
        {title} · {versions.length}
      </summary>
      {error && <p role="alert" className={errorClass}>{error}</p>}
      <ul className="space-y-2 pb-4" aria-label={title}>
        {versions.map((v, i) => (
          <li key={v.key} className="flex flex-wrap items-center gap-2">
            <span className="min-w-0 flex-1">
              {byline(v.made_at, v.made_by) || `Version ${versions.length - i}`}
              {v.note && <span className="text-muted"> · {v.note}</span>}
            </span>
            {v.current ? (
              <Badge tone="success">In use</Badge>
            ) : (
              <Button variant="secondary" dense busy={busy === v.key} disabled={!!hold || (busy !== null && busy !== v.key)} reason={hold} onClick={() => void go(v.key)}>
                Go back to this
              </Button>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}
