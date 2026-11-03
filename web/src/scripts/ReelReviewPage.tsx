import { useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { buttonClass } from "../components";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import type { components } from "../api/schema";
import { Banner, Button, PageTop, Skeleton, Tabs } from "../components";
import { useBrands } from "../shell/useBrands";
import { ActionBar } from "../shell/ActionBar";
import { useToast } from "../toast";
import { useRail } from "../useMedia";
import { useReelImport } from "./ReelImport";
import { useScript } from "./useScript";

type Shot = components["schemas"]["ShotRow"];
type Show = "all" | "lines";

/** 0.4 → "0:00.4", 45 → "0:45". */
const clock = (s: number) => {
  const m = Math.floor(s / 60);
  const [whole, tenth] = (s - m * 60).toFixed(1).split(".");
  return `${m}:${whole.padStart(2, "0")}${tenth === "0" ? "" : `.${tenth}`}`;
};

/** One shot (v5 G_ReelReview): its time, a still from the reel at that moment, and what happens. Pressing it plays from there. */
function ShotRowView({ shot, videoId, onSeek }: { shot: Shot; videoId: number | null; onSeek: (s: number) => void }) {
  const said = shot.line ? ` "${shot.line}"` : "";
  return (
    <li className={shot.dropped ? "opacity-60" : ""}>
      <button type="button" onClick={() => onSeek(shot.start)} className="grid min-h-14 w-full grid-cols-[48px_72px_minmax(0,1fr)] items-center gap-3 border-t border-border py-2 text-left hover:bg-surface-2" aria-label={`Shot ${shot.n}, ${clock(shot.start)} to ${clock(shot.end)}`}>
        <span className="text-xs tabular-nums text-muted">{clock(shot.start)}</span>
        {videoId != null ? (
          <video aria-hidden muted playsInline preload="metadata" src={`${fileUrl(videoId)}#t=${shot.start + 0.1}`} className="pointer-events-none h-10 w-[72px] rounded-lg bg-surface-2 object-cover" />
        ) : (
          <span aria-hidden className="h-10 w-[72px] rounded-lg bg-surface-2" />
        )}
        {shot.dropped ? (
          <span className="text-xs text-muted">Dropped · live action</span>
        ) : (
          <span className="line-clamp-2 text-sm">
            {shot.action}
            {said}
          </span>
        )}
      </button>
    </li>
  );
}

/** Review the breakdown of an imported reel (v5 G_ReelReview): the reel, its shots, and the script filled from it. Start over
 *  goes back to Import a reel; Use this script opens the Script step to adapt it. Fixes to the read go through Read it again. */
export function ReelReviewPage() {
  const brandId = Number(useParams().brandId);
  const id = Number(useParams().scriptId);
  const rail = useRail();
  const navigate = useNavigate();
  const toast = useToast();
  const brandName = useBrands().data?.find((b) => b.id === brandId)?.name;
  const script = useScript(id);
  const reel = useReelImport(id).data;
  const player = useRef<HTMLVideoElement>(null);
  const [show, setShow] = useState<Show>("all");
  const review = useQuery({
    queryKey: ["reel-breakdown", id],
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/scripts/{script_id}/import/breakdown", { params: { path: { script_id: id } } });
      if (!data) throw new Error(response.status === 409 ? errorText(error) : "We couldn't load the breakdown.");
      return data;
    },
  });
  const back = `/b/${brandId}/scripts/${id}`;
  const seek = (s: number) => {
    if (player.current) player.current.currentTime = s;
  };
  const use = () => {
    toast(`Script filled from the reel. Adapt it${brandName ? ` for ${brandName}` : ""}.`);
    navigate(`${back}?step=script`);
  };

  const r = review.data;
  const shots = r?.shots ?? [];
  const shown = show === "all" ? shots : shots.filter((s) => s.line);
  const inMontage = (n: number) => (show === "all" ? r?.montages.find((m) => n >= m.first && n <= m.last) : undefined);
  const words = script.data?.versions.find((v) => v.slot === 0)?.text.trim() ?? "";
  const from = reel?.source === "link" && reel.url ? reel.url.replace(/^https?:\/\/(www\.)?/, "") : reel?.source === "file" ? "an uploaded video" : null;

  // Montages are one row that opens; everything else is a row of its own.
  const rows: ReactNode[] = [];
  for (const s of shown) {
    const m = inMontage(s.n);
    if (m && s.n === m.first) {
      const inside = shown.filter((x) => x.n >= m.first && x.n <= m.last);
      rows.push(
        <li key={`m${m.first}`}>
          <details className="group border-t border-border">
            <summary className="flex min-h-14 cursor-pointer list-none items-center gap-2 text-sm text-muted [&::-webkit-details-marker]:hidden">
              <ChevronRight size={20} strokeWidth={1.75} aria-hidden className="shrink-0 transition-transform group-open:rotate-90 motion-reduce:transition-none" />
              <span className="tabular-nums">
                {clock(inside[0]?.start ?? 0)} · shots {m.first}–{m.last} · montage · {m.seconds.toFixed(1)} s
              </span>
            </summary>
            <ul>
              {inside.map((x) => (
                <ShotRowView key={x.n} shot={x} videoId={r?.video_file_id ?? null} onSeek={seek} />
              ))}
            </ul>
          </details>
        </li>,
      );
    } else if (!m) {
      rows.push(<ShotRowView key={s.n} shot={s} videoId={r?.video_file_id ?? null} onSeek={seek} />);
    }
  }

  const presses = (
    <>
      <Link to={`/b/${brandId}/scripts/import`} className={buttonClass("ghost")}>
        Start over
      </Link>
      <Button onClick={use} disabled={!r}>
        Use this script
      </Button>
    </>
  );
  return (
    <main className={`space-y-6 p-4 sm:p-6 ${rail ? "" : "pb-28"}`}>
      <PageTop title="Review the breakdown" crumb={{ to: `/b/${brandId}/scripts`, label: "Scripts" }}>
        {rail && presses}
      </PageTop>
      {review.isPending && <Skeleton className="h-64" />}
      {review.isError && <Banner tone="warning" title={review.error.message} />}
      {r && (
        <div className="grid items-start gap-6 sm:px-2 lg:grid-cols-[300px_minmax(0,1fr)] xl:grid-cols-[300px_minmax(0,1fr)_360px]">
          <section aria-label="Reel" className="space-y-2 lg:sticky lg:top-4">
            {r.video_file_id != null ? <video ref={player} controls src={fileUrl(r.video_file_id)} aria-label="The reel" className="mx-auto aspect-[9/16] max-h-[360px] w-full rounded-lg bg-surface-2 object-contain lg:max-h-none" /> : null}
            {from && <p className="break-all text-xs text-muted">From {from}</p>}
          </section>
          <section aria-label="Shots" className="min-w-0">
            <div className="flex flex-wrap items-center justify-between gap-2 pb-2">
              <h2 className="text-sm font-medium">Shots</h2>
              <Tabs label="Show" value={show} onChange={(v) => setShow(v as Show)} tabs={[{ id: "all", label: "All" }, { id: "lines", label: "Lines only" }]} />
            </div>
            {rows.length === 0 ? <p className="border-t border-border py-4 text-muted">No shots to show.</p> : <ul>{rows}</ul>}
          </section>
          <section aria-label="Script filled from the reel" className="min-w-0 space-y-3 rounded-lg border border-border bg-surface p-4 lg:col-start-2 xl:col-start-auto">
            <h2 className="text-sm font-medium">Script filled from the reel</h2>
            <p className="text-xs text-muted">Adapt it{brandName ? ` to ${brandName}` : ""} before you go on.</p>
            {words ? <p className="type-script whitespace-pre-line text-sm">{words}</p> : <Skeleton className="h-24" />}
          </section>
        </div>
      )}
      {!rail && r && <ActionBar phone>{presses}</ActionBar>}
    </main>
  );
}
