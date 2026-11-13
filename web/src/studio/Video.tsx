import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Archive, Download, WifiOff } from "lucide-react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { useAssets } from "../cast/useAssets";
import { useBreakdownOf } from "../clips/useBreakdownOf";
import { useCutEdits } from "../cut/useCutEdits";
import { said } from "../folders/ideas";
import { useFreestyle, useFreestyleActions, type Freestyle } from "../freestyle/useFreestyle";
import { useApproveCast, useCast } from "../projects/CastOk";
import { useVideoActions } from "../projects/ReleaseVideo";
import { useCut, useCutVersions, useMakeCut, useProjectClips } from "../projects/useProgress";
import { Money, money } from "../usage/parts";
import { useVideoSpend } from "../usage/VideoSpend";
import { useOnChange } from "../useOnChange";
import { useOnline } from "../useMedia";
import { isOpen, said as price, useAskActions, useAsks, type Ask } from "../videos/AskCard";
import { useDirectorRun } from "../videos/director";
import { useLive } from "../videos/live";
import { spentAsHeader, upTo } from "../videos/money";
import { onePass } from "../videos/Preview";
import { boxPlaceholder, runGoing, useNoteBox, useRunPresses, useStop } from "../videos/runActions";
import { carryOnLabel, useRunProgress } from "../videos/RunCard";
import { threadOf } from "../videos/thread";
import { stateOf, useRunEnd, useVideoProject } from "../videos/VideoChat";
import { mp4, useHead, type Head } from "../videos/VideoHead";
import { Popover } from "./Popover";
import { Split } from "./Split";
import { DOT } from "./StudioShell";
import { Question } from "./VideoAsk";
import { Cast } from "./VideoCast";
import { Finish } from "./VideoCut";
import { VideoMenu } from "./VideoMenu";
import { Failed, Offers, StopButton, Stopped } from "./VideoRun";
import { useLock } from "./useLock";
import { BOX, Say } from "./VideoSay";
import { Stage } from "./VideoStage";
import { CastCard, PressButton, StartCard } from "./VideoStart";
import { NarrationVoice, useNarrationVoice } from "./VideoVoice";
import { Thread } from "./VideoThread";
import { duration } from "./script";
import { cellsOf, once, openingsIn, planOf, versionFile, type Press } from "./videoData";
import "./video.css";

type Project = components["schemas"]["ProjectOut"];
type Run = components["schemas"]["DirectorOut"];
const SOFAR = "so-far"; // the header's money: the menu's "What it cost" opens it

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

/** /s/b/:brandId/videos/:projectId: one video in the new look (the redesign, stage 3). The chat with the director on
 *  the left, the film on the right, a divider between them, and every press the owner needs to run it: approve and
 *  film, answer a question, send a note, stop and carry on, another take, the clip's editor, the cut. Each press sends
 *  what the current site's page sends for it, through the same hook, once. A script with several openings is one
 *  video with a version for each, the same body after each hook: a switch by the views picks the one on screen. */
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

/** The video is read first. One made by the earlier, step-by-step director (its `engine` isn't the one-pass one), and
 *  anyone but the owner, opens the current site's page for it instead: this page has only the one-pass director's
 *  presses, and only the owner's. A new video the director hasn't started on has no engine yet and stays here. */
function VideoPage({ id, brandId }: { id: number; brandId: number }) {
  const me = useMe();
  const project = useVideoProject(id);
  const p = project.data ?? null;
  useLive(p ? id : 0); // each change on this video, the moment it lands
  const sent = useFreestyle(p?.freestyle_id ?? null, false); // the send it was made from: its first words and moves
  const director = useDirectorRun(id);
  const head = useHead(id);
  if (me.isPending || project.isPending || head.isPending || director.isPending || (p?.freestyle_id != null && sent.isPending))
    return (
      <p className="none" role="status">
        Loading…
      </p>
    );
  if (!p || !head.data) return <Missing brandId={brandId} />;
  const earlier = !onePass(p) && (p.engine != null || (director.data != null && director.data.status !== "none"));
  if (earlier || me.data?.role !== "owner") return <Navigate to={`/b/${brandId}/videos/${id}`} replace />;
  return <Desk id={id} brandId={brandId} p={p} h={head.data} fs={sent.data ?? null} run={director.data ?? null} />;
}

function Desk({ id, brandId, p, h, fs, run }: { id: number; brandId: number; p: Project; h: Head; fs: Freestyle | null; run: Run | null }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const online = useOnline();
  const progress = useRunProgress(id).data ?? null;
  const asksRead = useAsks(id);
  const asks = asksRead.data ?? [];
  const clips = useProjectClips(id).data ?? [];
  const breakdown = useBreakdownOf(id).data?.breakdown;
  const first = useCut(id).data ?? null; // the cut itself: the first version's, and the one every edit acts on
  // The versions: the server's list, else the openings the clips are marked with. The one on screen is kept in the
  // address (?v=2), so a reload keeps it; a further version's cut is its own read.
  const [params, setParams] = useSearchParams();
  const versions = useCutVersions(id).data ?? [];
  const hooks = versions.length > 1 ? versions.map((x) => x.opening) : openingsIn(clips);
  const many = hooks.length > 1;
  const v = many && hooks.includes(Number(params.get("v"))) ? Number(params.get("v")) : 1;
  const further = useCut(id, v).data ?? null;
  const cut = v > 1 ? further : first;
  const gateRead = useCast(id).data;
  const cast = gateRead?.items ?? [];
  const assets = useAssets(id).data ?? [];
  const [restoring, setRestoring] = useState(false);

  // Where the run stands, read as the current site's page reads it.
  const running = runGoing(run);
  const state = fs ? stateOf(fs, running) : running ? "working" : (run?.status ?? "none");
  const archived = !!p.archived_at;
  const items = threadOf(fs, run?.thread ?? [], progress?.run);
  const start = asks.find((a) => a.kind === "start" && isOpen(a));
  const moneyOpen = asks.some((a) => ["start", "budget", "own", "plan"].includes(a.kind) && isOpen(a));
  const ended = ["stopped", "failed", "declined", "withdrawn", "ended", "none"].includes(state) && !moneyOpen && !progress?.stopped && !progress?.failed;
  const noted = !running && (run?.unread ?? 0) > 0 && run?.status !== "none";
  const blocked = run?.start_blocked || null;
  const film = cut?.file_id ?? null; // the version on screen
  const made = first?.file_id != null; // the video has a cut
  const target = { id, name: h.title, creditsUsed: p.credits_used, released: p.released };

  // The presses, each the current site's own hook. One press, one request: each is off while its request is in flight.
  const stop = useStop(id, fs?.id);
  const sentActs = useFreestyleActions(fs?.id ?? null);
  const { again, carry, planAgain, saveNote } = useRunPresses(id, fs?.id);
  const answer = useAskActions(start ?? ({ id: 0, project_id: id } as Ask));
  const approve = useApproveCast(id);
  const edits = useCutEdits(id);
  const makeCut = useMakeCut(id);
  const video = useVideoActions(() => navigate(`/s/b/${brandId}/videos`));
  const voice = useNarrationVoice(id, fs?.id, p.brand_id, start?.id); // a narrated video's voice, and swapping it (./VideoVoice)
  const startLock = useLock(answer.isPending); // the paid presses: one request each, however fast they are pressed (./useLock)
  const runLock = useLock(again.isPending || carry.isPending || planAgain.isPending);
  const box = useNoteBox({ busy: saveNote.isPending, off: archived || !online, onSend: (text, files, done, refused) => saveNote.mutate({ text, files }, { onSuccess: done, onError: refused }) });
  const inFlight = saveNote.isPending ? saveNote.variables : undefined;
  const sending = inFlight && [...items].reverse().find((t) => t.kind === "message")?.text !== inFlight.text ? { text: inFlight.text, files: inFlight.files.length } : null;
  const toBox = (words = "") => {
    if (words && !box.text.trim()) box.setText(words);
    document.getElementById(BOX)?.focus();
  };

  // What the current site's page reads again by itself, and when (reads only).
  useRunEnd(id, progress?.status, run?.status, h.status.kind);
  const updating = !!start?.money?.updating; // a note is being read into the plan: once it is in, the plan is read again
  useOnChange(asksRead.isPending ? undefined : updating, () => {
    if (!updating) for (const queryKey of [["breakdown", id], ["project-clips", id], ["cast", id], ["idea", id]]) void queryClient.invalidateQueries({ queryKey });
  });
  const unread = items.flatMap((t) => (t.kind === "ask" && t.ask_id != null && !asks.some((a) => a.id === t.ask_id) ? [t.ask_id] : [])).join(",");
  useEffect(() => {
    if (unread && !asksRead.isFetching) void asksRead.refetch(); // a card the chat names is read at once, not on the next poll
  }, [unread]); // eslint-disable-line react-hooks/exhaustive-deps
  useOnChange(asksRead.isPending ? undefined : asks.map((a) => `${a.id}:${a.state}`).join(","), () => void queryClient.invalidateQueries({ queryKey: ["director", id] }));

  // An edit, a pick or a new cut answers with the cut itself: the versions and a further version's cut are read again.
  const stamp = first && [first.number, first.changes, first.out_of_date, first.making?.number, ...first.edits.map((e) => `${e.id}${e.undone ? "u" : ""}`)].join();
  useOnChange((many && stamp) || undefined, () => void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[1] === id && (q.queryKey[0] === "cut-versions" || (q.queryKey[0] === "project-cut" && q.queryKey.length > 2)) }));

  const plan = planOf(breakdown, clips, progress);
  const planned = plan.flatMap((s) => s.clips);
  const here = many ? planned.filter((c) => !c.opening || c.opening === v) : planned; // this version's clips: its hook's and the body's
  // The versions whose cut is being made (`cutting`), is behind their clips (`behind`) or isn't made yet (`uncut`). While the director works, or
  // a round waits for his OK, the cuts are the director's to make.
  const his = many && made && !running && !start ? versions : [];
  const cutting = his.filter((x) => x.making).map((x) => x.opening); // being cut now: nothing to press
  const behind = his.filter((x) => x.out_of_date && !x.making).map((x) => x.opening);
  const uncut = his.filter((x) => x.file_id == null && !x.making).map((x) => x.opening);
  const round = 1 + items.filter((t) => t.note).length; // each delivery ends a round; a note after it starts the next
  const going = ["working", "waiting", "needs_you"].includes(h.status.kind); // else an estimate is for the next run
  const toGo = going && progress?.expected_usd != null && progress.actual_usd != null ? Math.max(0, progress.expected_usd - progress.actual_usd) : null;

  // The one main press: the start card's (never while the plan is being updated for a note), else the cast's own OK.
  const gate = !start && gateRead?.state === "ready" && gateRead.can_approve ? gateRead : null;
  const wrong = !!gate?.items.some((i) => i.approval !== "approved" && i.look_fit); // the look check objects: only "anyway" approves
  const main: Press | null =
    start && !updating && start.can.includes("make_it")
      ? { label: round > 1 ? `Make round ${round}` : "Approve and film", price: start.money ? `${start.money.expected ? "about" : "up to"} ${price(start.money.up_to)}` : undefined, busy: answer.isPending, onPress: () => startLock((done) => answer.mutate({ body: { how: "make_it" } }, { onSettled: done })) }
      : gate
        ? { label: wrong ? "Approve anyway" : "Approve cast and places", busy: approve.isPending, onPress: () => approve.mutate({ seen: Object.fromEntries(gate.items.map((i) => [i.ref, i.sig])), anyway: wrong }) }
        : null;
  // A finished video whose cast changed afterwards: the OK stays on its card in the chat, and the header keeps Download.
  const quiet = !!gate && !gate.asked && made && !running;
  const startCard = (a: Ask) => <StartCard ask={a} round={round} press={main} error={answer.isError ? answer.error.message : null} cast={cast} plan={planned} finish={first && <Finish cut={first} edits={edits} />} voice={voice?.set?.name} onChange={() => toBox()} />;

  // A run that isn't going: his Stop, a run that needs him, or one that ended.
  const pressing = carry.isPending || planAgain.isPending;
  const carryOn: Press = { label: "Carry on", busy: pressing, why: blocked, onPress: () => runLock((done) => (planAgain.reset(), carry.mutate(undefined, { onSettled: done }))) };
  const s = progress?.stopped;
  const stopped = s && <Stopped stopped={s} error={(carry.error ?? planAgain.error)?.message ?? null} presses={[...(s.carry_on || s.free ? [{ ...carryOn, label: carryOnLabel(s) }] : []), { label: "Start the plan again", busy: pressing, why: blocked, onPress: () => runLock((done) => (carry.reset(), planAgain.mutate(undefined, { onSettled: done }))) }]} />;
  const failed = progress?.failed && <Failed failed={progress.failed} projectId={id} carry={carryOn} current={`/b/${brandId}/videos/${id}`} />;
  const startLabel = state === "none" ? "Make it" : (state === "stopped" || state === "ended") && noted ? "Start again with this note" : "Make it again";
  const offers: Press[] = [
    ...(ended && !progress && run?.carry_on != null ? [{ ...carryOn, price: run.carry_on ? `up to ${run.carry_on}` : undefined }] : []),
    ...(ended ? [{ label: startLabel, price: run?.run_expected_usd != null ? `about $${run.run_expected_usd.toFixed(2)}` : run?.run_price ? upTo(h, run.run_price) : undefined, busy: again.isPending, why: blocked, onPress: () => runLock((done) => again.mutate(undefined, { onSettled: done })) }] : []),
  ];
  const named = new Set(items.flatMap((t) => (t.kind === "ask" ? [t.ask_id] : [])));
  const waiting = (run?.waiting ?? []).filter((w) => asks.every((a) => a.id !== w.id || isOpen(a)));

  const spent = (
    <>
      <b>{spentAsHeader(h, p.credits_used)}</b>
      {going && h.expected?.usd != null ? ` so far · this run about ${money(h.expected.usd)}` : h.status.kind !== "delivered" ? " so far" : film != null ? ` · ${duration(Math.floor(cut!.timeline.length))}${many ? ` · ${hooks.length} versions` : ""}` : ""}
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
              <button type="button" id={SOFAR} className="spend" title="What it has cost so far" {...b}>
                {spent}
              </button>
            )}
          >
            {() => <SoFar id={id} toGo={toGo} />}
          </Popover>
        ) : (
          <span className="spend">{spent}</span>
        )}
        {!archived && running && <StopButton busy={stop.isPending || sentActs.stop.isPending} onStop={() => (fs ? sentActs.stop.mutate() : stop.mutate())} />}
        {archived ? null : main && !quiet ? (
          <PressButton press={main} />
        ) : (
          !running &&
          film != null && (
            <a className="btn go" href={fileUrl(film)} download={versionFile(h.title, v)}>
              <Download size={14} strokeWidth={1.75} aria-hidden />
              Download
            </a>
          )
        )}
        <VideoMenu target={target} brandId={brandId} fsId={fs?.id ?? null} folder={h.folder?.id ?? p.folder_id ?? null} films={many ? versions.flatMap((x) => (x.file_id != null ? [{ label: `Download hook ${x.opening} (MP4)`, file: x.file_id, name: versionFile(h.title, x.opening) }] : [])) : film != null ? [{ label: "Download MP4", file: film, name: mp4(h.title) }] : []} video={video} onCost={h.spent.usd != null ? () => document.getElementById(SOFAR)?.click() : undefined} may={{ change: !archived, variations: !archived && !running && h.status.kind === "delivered", zip: clips.some((c) => c.picked_take_id != null), archive: !archived && (!running || made) }} />
      </header>
      <Split
        first={asks.some(isOpen) || (gate && !quiet) ? "chat" : "film"}
        chat={
          <Thread
            items={items}
            sending={sending}
            progress={progress}
            asks={asks}
            clips={clips}
            projectId={id}
            start={startCard}
            stopped={stopped}
            failed={failed}
            banner={
              archived ? (
                <p className="banner">
                  <Archive size={16} strokeWidth={1.75} aria-hidden />
                  <span>
                    <b>Archived.</b> It’s out of the lists. Its clips and downloads are kept.
                  </span>
                  <button type="button" className="btn soft" disabled={restoring} onClick={once(() => (setRestoring(true), void video.restore(target).finally(() => setRestoring(false))))}>
                    Restore
                  </button>
                </p>
              ) : (
                !online && (
                  <p className="banner" role="status">
                    <WifiOff size={16} strokeWidth={1.75} aria-hidden />
                    <span>
                      <b>You’re offline.</b> The director keeps working. This page catches up when you’re back.
                    </span>
                  </p>
                )
              )
            }
            after={
              !archived && (
                <>
                  {asks.filter((a) => isOpen(a) && !named.has(a.id)).map((a) => (
                    <div key={a.id} className="msg">
                      {a.kind === "start" ? startCard(a) : <Question ask={a} />}
                    </div>
                  ))}
                  {gate && main && (
                    <div className="msg">
                      <CastCard cast={gate.items} asked={gate.asked} press={main} error={approve.isError ? approve.error.message : null} />
                    </div>
                  )}
                  <Offers presses={offers} error={(again.error ?? stop.error ?? sentActs.stop.error ?? (s ? null : carry.error))?.message ?? null} />
                </>
              )
            }
            foot={
              <Say
                box={box}
                waiting={waiting}
                closed={archived ? "It’s archived. Restore it to keep working." : null}
                placeholder={online ? boxPlaceholder(true, run?.status === "delivered" || state === "delivered", running && !run?.turns.some((t) => t.tool)) : "You’re offline. You can type; send it when you’re back."}
                note={running && items.at(-1)?.kind === "message" ? "The director will read this on its next move." : noted && (state === "stopped" || state === "ended") ? "Saved. Press Start again with this note to make it." : null}
                error={saveNote.isError ? saveNote.error.message : null}
              />
            }
          />
        }
        film={<Stage projectId={id} plan={plan} cells={cellsOf(here, cut?.timeline.pieces ?? [])} cut={cut} first={first} versions={many ? { on: v, list: hooks.map((k) => ({ opening: k, name: versions.find((x) => x.opening === k)?.name ?? "" })), behind, uncut, cutting, show: (k) => setParams((was) => (k > 1 ? was.set("v", String(k)) : was.delete("v"), was), { replace: true }) } : undefined} rows={clips} head={h} aspect={p.aspect_ratio} edits={edits} make={makeCut} cast={<Cast cast={cast} assets={assets} voice={voice && <NarrationVoice voice={voice} change={!archived && !running && !start && h.status.kind === "delivered"} undo={!archived && !running} />} />} onTell={toBox} />}
      />
    </>
  );
}
