import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorText, must } from "../api/client";
import { useToast } from "../components";
import { refreshJobs } from "../jobs/refresh";

/** Why a pick's cut didn't start, said with what happens to the pick: a cut already being made takes it next. */
export function recutRefused(why: string): string {
  const making = /^Cut (\d+) is being made/.exec(why);
  return making ? `Cut ${making[1]} is being made; your pick goes in the next cut. Make it from the Cut tab once Cut ${making[1]} is ready.` : `Your pick is kept, but the cut wasn’t made: ${why}`;
}

/** One clip's presses (S6-02): another take, with the director's own fix note when a flagged take is remade; a take
 *  put in use, after which the cut that uses the clip is made again by itself, free (S-gaps-08 5, S7-05); its sound
 *  effects taken off. One press at a time (`run`), and the clip is read again however a press ends. `hasCut`: whether
 *  the video has a cut to make again (by default, the stitched video the page has read). */
export function useClipActions(projectId: number, clipId: number, hasCut?: () => boolean) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [recut, setRecut] = useState(false);
  const path = { project_id: projectId, clip_id: clipId };
  const refresh = async () => {
    await refreshJobs(queryClient);
    await Promise.all([["project-clips", projectId], ["storyboard", projectId], ["run-progress", projectId], ["project-video", projectId], ["idea", projectId], ["project", projectId]].map((queryKey) => queryClient.invalidateQueries({ queryKey })));
  };
  // Read again however a press ends: one that stops midway (a still picked, its take refused) shows where it got to.
  const run = useMutation({ mutationFn: (f: () => Promise<unknown>) => f(), onSettled: refresh, onError: (e: Error) => toast(e.message, undefined, "error") });
  const go = (f: () => Promise<unknown>) => run.mutate(f);
  const take = (note = "") => go(() => must(api.POST("/projects/{project_id}/clips/{clip_id}/generate", { params: { path }, body: { note } })));
  // A person's pick is their OK; the cut that uses this clip is made again by itself, free.
  const pickTake = (t: { id: number }, keep = false) =>
    go(async () => {
      const route = keep ? "/projects/{project_id}/clips/{clip_id}/takes/{take_id}/keep" : "/projects/{project_id}/clips/{clip_id}/takes/{take_id}/use";
      await must(api.POST(route, { params: { path: { ...path, take_id: t.id } } }));
      if (!(hasCut ? hasCut() : queryClient.getQueryData(["project-video", projectId]))) return;
      setRecut(true);
      try {
        const made = await api.POST("/projects/{project_id}/cut", { params: { path: { project_id: projectId } } }); // the next cut (#1299)
        if (made.data) queryClient.setQueryData(["project-cut", projectId], made.data);
        else toast(recutRefused(errorText(made.error)), undefined, "error"); // the pick stays; say why and what next (rule 22)
      } finally {
        setRecut(false);
      }
    });
  const unsound = () => go(() => must(api.DELETE("/projects/{project_id}/clips/{clip_id}/sound", { params: { path } })));
  return { run, go, refresh, take, pickTake, unsound, recut };
}
