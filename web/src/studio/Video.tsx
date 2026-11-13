import { Link, useParams } from "react-router-dom";
import { useAssets } from "../cast/useAssets";
import { useBreakdownOf } from "../clips/useBreakdownOf";
import { said } from "../folders/ideas";
import { useFreestyle } from "../freestyle/useFreestyle";
import { useCast } from "../projects/CastOk";
import { useCut, useProjectClips } from "../projects/useProgress";
import { Money, money } from "../usage/parts";
import { useVideoSpend } from "../usage/VideoSpend";
import { isOpen, useAsks } from "../videos/AskCard";
import { useDirectorRun } from "../videos/director";
import { useLive } from "../videos/live";
import { spentAsHeader } from "../videos/money";
import { useRunProgress } from "../videos/RunCard";
import { threadOf } from "../videos/thread";
import { useVideoProject } from "../videos/VideoChat";
import { useHead } from "../videos/VideoHead";
import { Popover } from "./Popover";
import { Split } from "./Split";
import { DOT } from "./StudioShell";
import { Cast } from "./VideoCast";
import { Stage } from "./VideoStage";
import { Thread } from "./VideoThread";
import { duration } from "./script";
import { cellsOf, planOf } from "./videoData";
import "./video.css";

/** "So far": what the video has cost by part, from the server's own split (the one the current site's "What it cost"
 *  reads, read when this opens), the total, and what is still to go while a run with an estimate is going. */
function SoFar({ id, toGo }: { id: number; toGo: number | null }) {
  const spend = useVideoSpend(id);
  const v = spend.data;
  if (!v)
    return (
      <p className="pe" role={spend.isError ? "alert" : "status"}>
        {spend.isError ? "Couldn’t load what it cost." : "Loading…"}
      </p>
    );
  return (
    <>
      <h6>So far</h6>
      <dl className="money">
      {v.kinds.map((k) => (
        <div key={k.name}>
          <dt>{k.name}</dt>
          <dd>
            <Money value={k.usd} estimated={k.estimated} />
          </dd>
        </div>
      ))}
      <div className="sum">
        <dt>Total</dt>
        <dd>
          <Money value={v.spend_usd} estimated={v.spend_estimated} />
        </dd>
      </div>
      {toGo != null && (
        <div className="q">
          <dt>Still to go</dt>
          <dd>about {money(toGo)}</dd>
        </div>
      )}
      </dl>
    </>
  );
}

/** /s/b/:brandId/videos/:projectId: one video in the new look (the redesign, stage 2), to read and watch. The chat with
 *  the director on the left, the film on the right, a divider between them. It reads what the current site's page
 *  reads, through the same hooks and no more often, and sends nothing: every action is on the current site, a link away. */
export function Video() {
  const { brandId, projectId } = useParams();
  const id = Number(projectId);
  return id > 0 ? <VideoPage key={id} id={id} brandId={Number(brandId)} /> : <Missing brandId={Number(brandId)} />;
}

const Missing = ({ brandId }: { brandId: number }) => (
  <p className="none quiet">
    That video doesn’t exist. <Link to={`/s/b/${brandId}/videos`}>Back to the videos</Link>
  </p>
);

function VideoPage({ id, brandId }: { id: number; brandId: number }) {
  const project = useVideoProject(id);
  const p = project.data ?? null;
  useLive(p ? id : 0); // each change on this video, the moment it lands
  const sent = useFreestyle(p?.freestyle_id ?? null, false); // the send it was made from: its first words and moves
  const director = useDirectorRun(id);
  const head = useHead(id);
  const progress = useRunProgress(id).data ?? null;
  const asks = useAsks(id).data ?? [];
  const clips = useProjectClips(id).data ?? [];
  const breakdown = useBreakdownOf(id).data?.breakdown;
  const cut = useCut(id).data ?? null;
  const cast = useCast(id).data?.items ?? [];
  const assets = useAssets(id).data ?? [];
  const h = head.data;
  if (project.isPending || head.isPending || director.isPending || (p?.freestyle_id != null && sent.isPending))
    return (
      <p className="none" role="status">
        Loading…
      </p>
    );
  if (!p || !h) return <Missing brandId={brandId} />;

  const plan = planOf(breakdown, clips, progress);
  const planned = plan.flatMap((s) => s.clips);
  const going = ["working", "waiting", "needs_you"].includes(h.status.kind); // else an estimate is for the next run
  const toGo = going && progress?.expected_usd != null && progress.actual_usd != null ? Math.max(0, progress.expected_usd - progress.actual_usd) : null;
  const spent = (
    <>
      <b>{spentAsHeader(h, p.credits_used)}</b>
      {going && h.expected?.usd != null ? ` so far · this run about ${money(h.expected.usd)}` : h.status.kind !== "delivered" ? " so far" : cut?.file_id != null ? ` · ${duration(Math.floor(cut.timeline.length))}` : ""}
    </>
  );
  return (
    <>
      <header className="head vhead">
        <Link className="crumb" to={`/s/b/${brandId}/videos`}>
          Videos
        </Link>
        <span className="slash" aria-hidden>
          /
        </span>
        <h1 className="clip">{h.title}</h1>
        <span className="lookt">{[h.style, h.format].filter(Boolean).join(" · ")}</span>
        <span className="tag">
          <i aria-hidden className={`dot ${DOT[h.status.kind] ?? ""}`} />
          <span className="clip">{said(h.status)}</span>
        </span>
        <span className="grow" />
        {h.spent.usd != null ? ( // the owner's dollars open what it cost, by part
          <Popover
            label="So far"
            end
            facts
            button={(b) => (
              <button type="button" className="spend" title="What it has cost so far" {...b}>
                {spent}
              </button>
            )}
          >
            {() => <SoFar id={id} toGo={toGo} />}
          </Popover>
        ) : (
          <span className="spend">{spent}</span>
        )}
      </header>
      <Split
        first={asks.some(isOpen) ? "chat" : "film"}
        chat={<Thread items={threadOf(sent.data ?? null, director.data?.thread ?? [], progress?.run)} progress={progress} asks={asks} clips={clips} cast={cast} planned={{ clips: planned.length, seconds: Math.round(planned.reduce((sum, c) => sum + c.seconds, 0)) }} projectId={id} current={`/b/${brandId}/videos/${id}`} />}
        film={<Stage plan={plan} cells={cellsOf(planned, cut?.timeline.pieces ?? [])} film={cut?.file_id ?? null} length={cut?.timeline.length ?? 0} speed={cut?.timeline.speed || 1} aspect={p.aspect_ratio} finish={cut && { captions: cut.timeline.captions, cards: cut.timeline.cards }} cast={<Cast cast={cast} assets={assets} />} />}
      />
    </>
  );
}
