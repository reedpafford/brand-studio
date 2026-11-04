import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Download } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { Button, buttonClass, creditsLabel, wholeCredits } from "../components";
import { Status } from "../freestyle/Thread";
import type { Freestyle } from "../freestyle/useFreestyle";
import { useRail } from "../useMedia";

/** One video, as the video page reads it. */
export function useVideoProject(id: number) {
  return useQuery({
    enabled: id > 0,
    queryKey: ["project", id],
    queryFn: async () => (await api.GET("/projects/{project_id}", { params: { path: { project_id: id } } })).data ?? null,
  });
}

export const mp4 = (title: string) => `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "video"}.mp4`;

/** A director-made video's top bar (B_Video*): Videos › its title, its status, and the presses for where it is. In the
 *  steps (`steps`, B_VideoSteps) it closes them; else `stepsTo` opens them there (none while it waits or works). */
export function VideoTop({ brandId, fs, title = fs.title, steps, stepsTo, actions }: { brandId: number; fs: Freestyle; title?: string; steps?: boolean; stepsTo?: string | null; actions?: ReactNode }) {
  const [, setParams] = useSearchParams();
  const rail = useRail();
  return (
    <header className="flex min-h-14 items-center justify-between gap-3 border-b border-border px-4 py-2 lg:min-h-[52px] lg:px-6 lg:py-0">
      <div className="flex min-w-0 flex-col lg:flex-row lg:items-center lg:gap-3">
        <p className="min-w-0 truncate">
          <Link to={`/b/${brandId}/videos`} className="hidden text-sm text-muted hover:text-text lg:inline">
            Videos ›{" "}
          </Link>
          <span className="font-semibold lg:text-sm lg:font-medium">{title}</span>
        </p>
        <Status status={fs.status} words={fs.status === "waiting" && fs.file_id ? "Change waiting for approval" : undefined} tail={rail ? undefined : `${creditsLabel(wholeCredits(fs.credits))} spent so far`} />
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {steps ? (
          <Button variant="ghost" dense className="text-muted! hover:text-text!" onClick={() => setParams({})}>
            Close the steps
          </Button>
        ) : (
          stepsTo && (
            <Button variant="ghost" dense className="text-muted! hover:text-text!" onClick={() => setParams({ step: stepsTo })}>
              {rail ? "Open the steps" : "Steps"}
            </Button>
          )
        )}
        {actions}
        {steps && fs.file_id && (
          <a className={buttonClass("primary")} href={fileUrl(fs.file_id)} download={mp4(fs.title)}>
            <Download size={16} strokeWidth={1.75} aria-hidden />
            Download MP4
          </a>
        )}
      </div>
    </header>
  );
}
