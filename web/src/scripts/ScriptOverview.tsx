import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import type { components } from "../api/schema";
import { Button, Dot, wholeCredits } from "../components";
import { useFolders } from "../folders/Projects";
import { useProjectList } from "../projects/LegacyVideos";
import { videoStatus, videoTo } from "../videos/progress";
import { finished } from "../freestyle/FromScript";
import { lookName, useLooks } from "./Looks";
import { useBrands } from "../shell/useBrands";
import { letterOf, statusOf } from "./status";
import type { Script } from "./useScript";

type Version = Script["versions"][number];
type Project = components["schemas"]["ProjectOut"];

// v5 C_ScriptOverview: Version 52 | Its video | Maker 64 | Credits 200 | press 132.
const COLS = "lg:grid lg:grid-cols-[52px_minmax(0,1fr)_64px_200px_132px] lg:items-center lg:gap-x-4";
const KIND: Record<string, string> = { story: "Dialogue", song: "Song", narrated: "Narrated" };

/** A version's credits as the board says them: what its video has spent in all, the director's own time included (so it
 *  matches the video's chat), or what making it is planned to cost. Never "free": nothing spent yet is "0 credits so far". */
const plural = (n: number) => `${n} credit${n === 1 ? "" : "s"}`;
const creditsText = (v: Version, video?: Project) => {
  if (video) {
    const n = wholeCredits(video.credits_used);
    return n > 0 ? `spent ${plural(n)}` : video.finished_at ? "—" : "0 credits so far";
  }
  return v.estimate_credits > 0 ? `about ${plural(wholeCredits(v.estimate_credits))} (planned)` : "—";
};

function VersionRow({ v, video, onMake }: { v: Version; video?: Project; onMake: () => void }) {
  // v5 words: a done video is "Delivered"; nothing made yet is a hollow ring.
  const made = video && videoStatus(video);
  const status = made ? { ...made, label: made.label.replace(/^Finished/, "Delivered") } : finished(v) ? { label: "No video yet", tone: "neutral" as const } : statusOf(v.status);
  const none = !video && (finished(v) || v.status === "draft");
  return (
    <li aria-label={`Version ${letterOf(v.slot)}`} className={`flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border py-2 lg:min-h-13 lg:py-0 ${COLS}`}>
      <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-md bg-surface-2 font-semibold">
        {letterOf(v.slot)}
      </span>
      <span className="text-xs">
        <Dot tone={status.tone} hollow={none}>{status.label}</Dot>
      </span>
      <span className={`text-sm ${v.editor ? "" : "text-muted"}`}>{v.editor?.name ?? "—"}</span>
      <span className={`text-sm tabular-nums ${video ? "" : "text-muted"}`}>{creditsText(v, video)}</span>
      <span className="ml-auto lg:ml-0 lg:justify-self-end">
        {video ? (
          <Link to={videoTo(video)} className="inline-flex min-h-control items-center rounded-md border border-border px-3 text-sm font-medium hover:bg-surface-2 lg:min-h-control-dense">
            Open video
          </Link>
        ) : (
          finished(v) && (
            <Button variant="secondary" dense onClick={onMake}>
              Make a video
            </Button>
          )
        )}
      </span>
    </li>
  );
}

/** A script's first tab (v5 C_ScriptOverview): its versions and their videos as a table, the words of the version to make
 *  next under it, and the script's facts beside it. Each version's Make a video opens the Make a video panel on it. */
export function ScriptOverview({ script: s, brandId, onMake }: { script: Script; brandId: number; /** Opens the Make a video panel (#1194's) on that version. */ onMake: (slot: number) => void }) {
  const videos = useProjectList(brandId);
  const looks = useLooks().data;
  const brand = useBrands().data?.find((b) => b.id === s.brand_id);
  const folders = useFolders(brandId);
  const byId = new Map((videos.data ?? []).map((p) => [p.id, p]));
  const versions = s.versions.filter((v) => v.text.trim() !== "" || v.status !== "draft");
  // The words shown are the next version to make, else the first.
  const shown = versions.find((v) => finished(v) && !v.project_id) ?? versions[0];
  const words = shown ? shown.text.split(/\s+/).filter(Boolean).length : 0;
  const project = folders.data?.find((f) => f.id === s.folder_id)?.name ?? "No project";
  const fact = (label: string, value: ReactNode) => (
    <div className="space-y-1.5">
      <p className="text-xs text-muted">{label}</p>
      <div className="text-sm">{value}</div>
    </div>
  );
  const locked = s.cast.length > 0 && s.cast.every((x) => x.locked);
  return (
    <div className="gap-8 space-y-6 lg:grid lg:grid-cols-[minmax(0,1fr)_360px] lg:space-y-0 lg:pt-3">
      <section aria-label="Versions and their videos" className="min-w-0 space-y-3.5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[15px] font-semibold">Versions</h2>
          <p className="text-xs text-muted">Each version can become its own video.</p>
        </div>
        <div>
          <div aria-hidden className={`hidden h-[34px] border-b border-border text-xs text-muted ${COLS}`}>
            <span>Version</span>
            <span>Its video</span>
            <span>Maker</span>
            <span>Credits</span>
            <span />
          </div>
          <ul>
            {versions.map((v) => (
              <VersionRow key={v.slot} v={v} video={v.project_id ? byId.get(v.project_id) : undefined} onMake={() => onMake(v.slot)} />
            ))}
          </ul>
        </div>
        {shown && (
          <div className="space-y-2 border-t border-border pt-[18px]">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="text-sm font-semibold">Script · version {letterOf(shown.slot)}</h3>
              {words > 0 && <span className="text-xs tabular-nums text-muted">{`${words} words${shown.seconds > 0 ? ` · about ${Math.round(shown.seconds)} s` : ""}`}</span>}
            </div>
            <p className="whitespace-pre-line font-script text-sm leading-[1.6] text-text/85 [overflow-wrap:anywhere]">{shown.text.trim() || "No words yet."}</p>
          </div>
        )}
      </section>
      <aside aria-label="About this script" className="space-y-[18px] border-border lg:border-l lg:pl-6">
        {fact("Type", [KIND[s.kind] ?? s.kind, !s.language || s.language === "en" ? "English" : s.language].join(" · "))}
        {fact("Look", s.look === "house" ? `House style${brand ? ` (${brand.name})` : ""}` : lookName(looks, s.look))}
        {fact("Project", project)}
        {fact(
          "Cast",
          s.cast.length === 0 ? (
            <span className="text-muted">Made at Cast</span>
          ) : (
            <span className="flex flex-wrap items-center gap-x-1.5">
              {s.cast.map((x) => x.role).join(" · ")}
              <Dot tone={locked ? "success" : "neutral"} hollow={!locked}>{locked ? (s.cast.length === 2 ? "Both locked" : "All locked") : "Not all locked"}</Dot>
            </span>
          ),
        )}
        {fact("In the library", <span className="text-xs">{s.published ? <Dot tone="success">Published</Dot> : <Dot hollow>Not published. Publish to let editors find it.</Dot>}</span>)}
      </aside>
    </div>
  );
}
