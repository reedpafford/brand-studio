import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { Button, useViewOnly } from "../components";
import { errorText as errorClass } from "../ui";
import { Dot } from "./OtherTakes";

type Clip = components["schemas"]["ProjectClipOut"];

/** Sound effects on the picked take, on request (cosmetic, v5's take line): Add sound effects asks what to hear ("slight
 *  footsteps"), at its price first; then it says what's added, with Remove (the take as it was made) or Make again. */
export function TakeSound({ projectId, clip }: { projectId: number; clip: Clip }) {
  const queryClient = useQueryClient();
  const viewOnly = useViewOnly();
  const [asked, setAsked] = useState<string | null>(null);
  const sound = clip.sound;
  const path = { project_id: projectId, clip_id: clip.id };
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["project-clips", projectId] });
  const add = useMutation({
    mutationFn: async (words: string) => {
      const { response, error } = await api.POST("/projects/{project_id}/clips/{clip_id}/sound", { params: { path }, body: { asked: words } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => setAsked(null),
    onSettled: refresh,
  });
  const remove = useMutation({
    mutationFn: async () => {
      const { response, error } = await api.DELETE("/projects/{project_id}/clips/{clip_id}/sound", { params: { path } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSettled: refresh,
  });
  const making = sound?.state === "making";
  useEffect(() => {
    if (!making) return;
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  });
  if (!sound) return null;
  const error = add.error ?? remove.error;
  return (
    <div className="space-y-1">
      {making && <Dot tone="run">Adding sound…</Dot>}
      {sound.state === "ready" && <Dot tone="ok">{`Sound added · ${sound.how}`}</Dot>}
      {sound.state === "failed" && <Dot tone="need">{`Sound didn't finish: ${sound.error || "try again"}`}</Dot>}
      {sound.state === "ready" && (
        <Button variant="ghost" dense disabled={viewOnly} busy={remove.isPending} onClick={() => remove.mutate()}>
          Remove sound
        </Button>
      )}
      {sound.state === "failed" && (
        <Button variant="ghost" dense disabled={viewOnly} busy={add.isPending} price={sound.credits} charge="estimate" onClick={() => add.mutate(sound.asked)}>
          Make again
        </Button>
      )}
      {sound.state === "none" && asked === null && (
        <Button variant="ghost" dense disabled={viewOnly} onClick={() => setAsked("")}>
          Add sound effects
        </Button>
      )}
      {sound.state === "none" && asked !== null && (
        <div className="space-y-1">
          <input className="block min-h-control w-full rounded-md border border-border-strong bg-bg px-2 text-sm text-text placeholder:text-muted lg:min-h-control-dense" aria-label={`Sound effects for ${clip.clip_id}`} placeholder="Slight footsteps, wind…" maxLength={300} value={asked} onChange={(e) => setAsked(e.target.value)} />
          <span className="flex gap-1">
            <Button variant="secondary" dense busy={add.isPending} price={sound.credits} charge="estimate" onClick={() => add.mutate(asked.trim())}>
              Add
            </Button>
            <Button variant="ghost" dense onClick={() => setAsked(null)}>
              Cancel
            </Button>
          </span>
        </div>
      )}
      {error && <p role="alert" className={errorClass}>{error.message}</p>}
    </div>
  );
}
