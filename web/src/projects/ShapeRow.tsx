import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { Select } from "../components";
import { errorText as errorClass } from "../ui";

const SHAPES = ["9:16", "1:1", "16:9", "4:3", "3:4", "21:9"] as const;
const PLATFORMS = ["TikTok", "Instagram Reels", "YouTube Shorts", "Other"];

/** Shape and where it will be posted, above the shots. Changing the shape after frames exist redraws them, so it asks first. */
export function ShapeRow({ projectId, aspect, platform, hasFrames }: { projectId: number; aspect: string; platform: string; hasFrames: boolean }) {
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: async (body: { aspect_ratio?: (typeof SHAPES)[number]; platform?: string }) => {
      const { response, error } = await api.PATCH("/projects/{project_id}", { params: { path: { project_id: projectId } }, body });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => Promise.all([queryClient.invalidateQueries({ queryKey: ["project", projectId] }), queryClient.invalidateQueries({ queryKey: ["storyboard", projectId] })]),
  });
  const shape = (a: (typeof SHAPES)[number]) => {
    if (a === aspect) return;
    if (hasFrames && !window.confirm(`Frames were drawn for ${aspect}. Changing the shape redraws them.`)) return;
    save.mutate({ aspect_ratio: a });
  };
  return (
    <div className="flex flex-wrap items-end gap-4">
      <fieldset className="space-y-1 text-sm">
        <legend className="font-medium">Shape</legend>
        <div className="flex flex-wrap gap-2">
          {SHAPES.map((a) => (
            <button key={a} type="button" aria-pressed={a === aspect} onClick={() => shape(a)} className={`min-h-control rounded-md border px-3 sm:min-h-control-dense ${a === aspect ? "border-accent bg-accent-soft text-accent-text" : "border-border-strong"}`}>
              {a}
            </button>
          ))}
        </div>
      </fieldset>
      <div className="w-56 max-w-full">
        <Select label="Where will it be posted?" value={PLATFORMS.includes(platform) ? platform : "Other"} onChange={(e) => save.mutate({ platform: e.target.value })}>
          {PLATFORMS.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </Select>
      </div>
      {save.error && <p role="alert" className={errorClass}>{save.error.message}</p>}
    </div>
  );
}
