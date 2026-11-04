import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useToast } from "../toast";

type LocksIO = components["schemas"]["LocksIO"];
type Flag = "cast" | "look" | "length" | "song";
const FLAGS: { id: Flag; label: string }[] = [
  { id: "cast", label: "Cast" },
  { id: "look", label: "Style" },
  { id: "length", label: "Length" },
  { id: "song", label: "Song" },
];
const chip = "inline-flex min-h-control items-center gap-1.5 rounded-md border px-2.5 text-sm sm:min-h-control-dense";

/** The choices the director builds around (director-chat.md §1). A press locks or unlocks one; unlocking hands the choice
 *  back to it. The screens it must use are picked elsewhere, so that chip only shows whether any are. */
export function LockChips({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const key = ["locks", projectId];
  const locks = useQuery({
    queryKey: key,
    queryFn: async () => (await api.GET("/projects/{project_id}/locks", { params: { path: { project_id: projectId } } })).data ?? null,
  });
  const save = useMutation({
    mutationFn: async (body: LocksIO) => {
      const { data, error } = await api.PUT("/projects/{project_id}/locks", { params: { path: { project_id: projectId } }, body });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => queryClient.setQueryData(key, data),
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const now = locks.data;
  if (!now) return locks.isError ? <p className="text-sm text-muted">Couldn't load the locks.</p> : null;
  const screens = now.locks.screens?.length ?? 0;
  return (
    <ul aria-label="Locked" className="flex flex-wrap gap-1.5">
      {FLAGS.map((f) => {
        const on = !!now.locks[f.id];
        return (
          <li key={f.id}>
            <button
              type="button"
              aria-pressed={on}
              disabled={save.isPending}
              onClick={() => save.mutate({ locks: { ...now.locks, [f.id]: !on }, outfits: now.outfits })}
              className={`${chip} ${on ? "border-border-strong bg-surface-2 text-text" : "border-border text-muted hover:text-text"}`}
            >
              {on && <Lock size={12} strokeWidth={2} aria-hidden />}
              {f.label}
            </button>
          </li>
        );
      })}
      <li>
        <span className={`${chip} ${screens ? "border-border-strong bg-surface-2 text-text" : "border-border text-muted"}`} title="The screens are picked in the plan.">
          {screens > 0 && <Lock size={12} strokeWidth={2} aria-hidden />}
          Screens{screens > 0 && ` · ${screens}`}
        </span>
      </li>
    </ul>
  );
}
