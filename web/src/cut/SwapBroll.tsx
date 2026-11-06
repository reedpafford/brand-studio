import { fileUrl } from "../api/upload";
import { useToast } from "../components";
import { useCutEdits, useSwaps } from "./useCutEdits";

/** Swap B-roll from the Clips tab (S6-03): the cut editor's own choices for this clip's piece, a press swaps it in the
 *  cut (free, with Undo in the editor); the next cut shows it. */
export function SwapBroll({ projectId, piece, onDone }: { projectId: number; piece: string; onDone: () => void }) {
  const swaps = useSwaps(projectId, piece);
  const { edit } = useCutEdits(projectId);
  const toast = useToast();
  const choices = (swaps.data ?? []).filter((s) => s.kind !== "in_cut");
  if (swaps.isPending) return <p className="text-sm text-muted">Finding takes to swap in…</p>;
  if (!choices.length) return <p className="text-sm text-muted">There’s nothing to swap this B-roll for yet.</p>;
  return (
    <ul aria-label="Swap B-roll for" className="flex flex-wrap gap-2">
      {choices.map((s) => (
        <li key={s.take_id} className="flex w-16 flex-col gap-1">
          <button
            type="button"
            aria-label={`Swap for ${s.label}`}
            disabled={edit.isPending}
            onClick={() => edit.mutate({ kind: "swap", piece, take_id: s.take_id }, { onSuccess: () => (toast(`Swapped for ${s.label}, free. Make the cut in the Cut tab to see it.`), onDone()) })}
            className="h-[114px] w-16 overflow-hidden rounded-md bg-surface-2"
          >
            {s.poster_file_id ? <img src={fileUrl(s.poster_file_id)} alt="" className="h-full w-full object-cover" /> : <video src={`${fileUrl(s.file_id)}#t=0.1`} muted preload="metadata" className="h-full w-full object-cover" />}
          </button>
          <span className="text-xs text-muted">{s.label}</span>
        </li>
      ))}
    </ul>
  );
}
