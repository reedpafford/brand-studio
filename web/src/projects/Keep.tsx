import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { Button } from "../components";

type Target = { of: "breakdown" } | { of: "frame"; id: number } | { of: "clip"; id: number };

/** "Keep it anyway" for one piece of advice on the breakdown, a frame or a clip. Advice never blocks; keeping it puts it away. */
export function useKeep(projectId: number, target: Target) {
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  return useMutation({
    mutationFn: async (problem: string) => {
      const body = { problem };
      const { response, error } =
        target.of === "breakdown"
          ? await api.POST("/projects/{project_id}/breakdown/keep", { params: { path }, body })
          : target.of === "frame"
            ? await api.POST("/projects/{project_id}/storyboard/frames/{frame_id}/keep", { params: { path: { ...path, frame_id: target.id } }, body })
            : await api.POST("/projects/{project_id}/clips/{clip_id}/keep", { params: { path: { ...path, clip_id: target.id } }, body });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [{ breakdown: "breakdown", frame: "storyboard", clip: "project-clips" }[target.of], projectId] }),
  });
}

/** Next to a problem: advice can be kept (then it says so); anything that needs fixing shows nothing. */
export function KeepControl({ problem, kept, onKeep, busy }: { problem: string; kept?: string[]; onKeep: (problem: string) => void; busy?: boolean }) {
  if (!problem.startsWith("Advice: ")) return null;
  if (kept?.includes(problem)) return <span className="text-xs text-muted">Kept · Reed will see it</span>;
  return (
    <Button variant="ghost" dense busy={busy} aria-label={`Keep it anyway: ${problem}`} onClick={() => onKeep(problem)}>
      Keep it anyway
    </Button>
  );
}
