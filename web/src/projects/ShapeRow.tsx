import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { Dialog, Select, useViewOnly } from "../components";
import { useFrames } from "./StoryboardPane";
import { errorText as errorClass } from "../ui";

const SHAPES = ["9:16", "1:1", "16:9", "4:3", "3:4", "21:9"] as const;
const PLATFORMS = ["TikTok", "Instagram Reels", "YouTube Shorts", "Other"];

/** Shape and where it will be posted, above the shots (the shape moves to the Video settings row once the server offers it). Changing the shape after stills exist asks first: the stills keep their shape (nothing
 *  is redrawn or charged); what's made next uses the new one. */
export function ShapeRow({ projectId, aspect, platform, shape: withShape = true }: { projectId: number; aspect: string; platform: string; shape?: boolean }) {
  const viewOnly = useViewOnly(); // a video only its maker or the owner may change
  const queryClient = useQueryClient();
  const frames = useFrames(projectId);
  const stills = (frames.data ?? []).filter((f) => f.file_id !== null);
  const [asking, setAsking] = useState<(typeof SHAPES)[number] | null>(null);
  const save = useMutation({
    mutationFn: async (body: { aspect_ratio?: (typeof SHAPES)[number]; platform?: string }) => {
      const { response, error } = await api.PATCH("/projects/{project_id}", { params: { path: { project_id: projectId } }, body });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => Promise.all([queryClient.invalidateQueries({ queryKey: ["project", projectId] }), queryClient.invalidateQueries({ queryKey: ["storyboard", projectId] })]),
  });
  const shape = (a: (typeof SHAPES)[number]) => {
    if (a === aspect) return;
    if (stills.length > 0) return setAsking(a);
    save.mutate({ aspect_ratio: a });
  };
  return (
    <div className="flex flex-wrap items-end gap-4">
      {withShape && <fieldset className="space-y-1 text-sm">
        <legend className="font-medium">Shape</legend>
        <div className="flex flex-wrap gap-2">
          {SHAPES.map((a) => (
            <button key={a} type="button" disabled={viewOnly} aria-pressed={a === aspect} onClick={() => shape(a)} className={`min-h-control rounded-md border px-3 sm:min-h-control-dense ${a === aspect ? "border-accent bg-accent-soft text-accent-text" : "border-border-strong"}`}>
              {a}
            </button>
          ))}
        </div>
      </fieldset>}
      <div className="w-56 max-w-full">
        <Select label="Where will it be posted?" value={PLATFORMS.includes(platform) ? platform : "Other"} onChange={(e) => save.mutate({ platform: e.target.value })}>
          {PLATFORMS.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </Select>
      </div>
      {save.error && <p role="alert" className={errorClass}>{save.error.message}</p>}
      {asking && (
        <Dialog
          title={`Change to ${asking}?`}
          cancelLabel="Not yet"
          actionLabel="Change the shape · free"
          onCancel={() => setAsking(null)}
          onConfirm={() => {
            save.mutate({ aspect_ratio: asking });
            setAsking(null);
          }}
        >
          {`The ${stills.length} still${stills.length === 1 ? " was" : "s were"} drawn for ${aspect} and stay${stills.length === 1 ? "s" : ""} that way. New stills and takes are made in ${asking}. To redraw the old ones, use Make the storyboard again on Storyboard.`}
        </Dialog>
      )}
    </div>
  );
}
