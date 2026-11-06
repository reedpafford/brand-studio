import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, ChevronLeft, CircleStop, FileText, Paperclip, Upload, WifiOff, X } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl, uploadFile } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Banner, Button, Dialog, Skeleton } from "../components";
import { mmss } from "../freestyle/FromScript";
import { Item, type Said } from "../freestyle/Thread";
import { ReelBlock } from "../scripts/ReelImport";
import { useFreestyle, useFreestyleActions, type Freestyle } from "../freestyle/useFreestyle";
import { refreshJobs } from "../jobs/refresh";
import { useMayManageVideo, useVideoActions } from "../projects/ReleaseVideo";
import { useFreshProject } from "../projects/useFreshProject";
import { useProjectClips, useProjectVideo } from "../projects/useProgress";
import { CastOk } from "../projects/CastOk";
import { letterOf } from "../scripts/status";
import { useScript } from "../scripts/useScript";
import { serverTime } from "../time";
import { useBrands } from "../shell/useBrands";
import { useOnline, useRail } from "../useMedia";
import { plain, useDirectorRun, useMovesRefresh } from "./director";
import { Preview, firstTab, tabFrom, usePanelFacts, type TabId } from "./Preview";
import { AskCard, HeldSend, WaitingBar, isOpen, useAskRefresh, useAsks } from "./AskCard";
import { InsteadCard } from "./InsteadCard";
import { DeliveryNote, Failed, PastNote, RunCard, stoppedParts, useRunProgress, useSeen, type Progress } from "./RunCard";
import { MoveDialog, RenameDialog, VideoHead, VideoMenu, headStatus, mp4, useHead, type Head } from "./VideoHead";

type Project = components["schemas"]["ProjectOut"];
type Run = components["schemas"]["DirectorOut"];
type Status = Head["status"];

/** One video, as the video page reads it. */
export function useVideoProject(id: number) {
  return useQuery({
    queryKey: ["project", id],
    enabled: id > 0,
    queryFn: async () => (await api.GET("/projects/{project_id}", { params: { path: { project_id: id } } })).data ?? null,
  });
}

/** /b/:brandId/videos/:id: the video, one chat with the director and its preview panel (v6 S3). */
export function VideoRoute() {
  const { brandId, projectId } = useParams();
  return <VideoPage projectId={Number(projectId)} brandId={Number(brandId)} />;
}

/** A freestyle's run, in the words the page uses: an editor's send waiting for the owner, a change waiting, or its status. */
function stateOf(fs: Freestyle, running: boolean) {
  if (running) return "working" as const;
  if (fs.status === "waiting") return fs.file_id ? ("change" as const) : ("waiting" as const);
  return fs.status;
}

/** The chat with the director and the preview panel beside it (S3-01, S3-09; P-04, P-05 on a phone). `freestyleId`: an
 *  editor's send before the owner's OK, when its video isn't theirs to read yet (the chat shows; the panel waits). */
export function VideoPage({ projectId: id, brandId, freestyleId }: { projectId: number; brandId: number; freestyleId?: number }) {
  const me = useMe().data;
  const owner = me?.role === "owner";
  const rail = useRail();
  const online = useOnline();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [editing, setEditing] = useState(false); // the cut editor is open: the chat narrows (S7)
  const [side, setSide] = useState<"chat" | "preview">(params.get("tab") || params.get("step") ? "preview" : "chat"); // the phone's switch
  const [stopping, setStopping] = useState(false);
  const [moving, setMoving] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [opened, setOpened] = useState<TabId | null>(null);
  const [cutSeen, setCutSeen] = useState(false);
  const previewSide = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (side === "chat") previewSide.current?.querySelectorAll("video").forEach((v) => v.pause()); // P-04: the cut stops when you go back to the chat
  }, [side]);
  useFreshProject(id);
  const project = useVideoProject(id);
  const p = project.data ?? null;
  const fsId = p?.freestyle_id ?? freestyleId ?? null;
  const fsQuery = useFreestyle(fsId);
  const fs = fsQuery.data;
  const runQuery = useDirectorRun(id);
  const run = runQuery.data;
  const clips = useProjectClips(id).data ?? [];
  const cut = useProjectVideo(id).data;
  const head = useHead(id, !!p);
  const liveRun = useRunProgress(id, !!p).data;
  const facts = usePanelFacts(p);
  const mayManage = useMayManageVideo();
  const brands = useBrands().data;
  const actions = useFreestyleActions(fsId);
  const video = useVideoActions((kind) => navigate(`/b/${brandId}/${kind === "release" ? "scripts" : "videos"}`));
  useMovesRefresh(id, (fs?.thread.length ?? 0) + (run?.turns.length ?? 0), `${fs?.status}:${run?.status}`);
  const stop = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/director/stop", { params: { path: { project_id: id } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["director", id], data);
      if (fsId) void queryClient.invalidateQueries({ queryKey: ["freestyle", fsId] });
      void queryClient.invalidateQueries({ queryKey: ["idea", id] });
      setStopping(false);
      return refreshJobs(queryClient);
    },
  });

  if (project.isPending || (fsId && fsQuery.isPending) || runQuery.isPending || (p && head.isPending)) return <Loading phone={!rail} />;
  if (!p && !fs)
    return (
      <p className="p-6">
        That video doesn't exist.{" "}
        <Link to={`/b/${brandId}/videos`} className="text-accent-text underline-offset-2 hover:underline">
          Back to the videos
        </Link>
      </p>
    );

  const turns = run?.turns ?? [];
  const running = run?.status === "running" && run.make_it == null && !turns.every((t) => t.status === "needs_owner_approval"); // a start card waiting: nothing runs (S3-02)
  const state = fs ? stateOf(fs, running) : running ? "working" : (run?.status ?? "none");
  const archived = !!p?.archived_at;
  const maker = p ? mayManage(p) : fs?.created_by_name === me?.name;
  const lookOnly = p && !mayManage(p) && !archived ? `Only ${p.created_by_name || "someone else"} or the owner can change this video.` : null;
  const cutFile = cut?.file_id ?? fs?.file_id ?? null;
  // The header's status: the server's for a readable video; before the owner's OK, the send's own.
  const fallback: Status = { kind: "waiting", words: owner ? "Waiting for your OK" : "Waiting for the owner", made: 0, total: 0 };
  const where = running ? (liveRun?.status === "revising" || (turns.some((t) => t.tool) && cutFile) ? "revising" : turns.some((t) => t.tool) ? null : "starting") : null;
  // A run that's going is Working, even between two of its moves (when no job is queued the server reads the last state).
  const read = head.data?.status ?? fallback;
  // "Needs you · Start it" while the first move still runs (no start card open yet) is the server's read lagging: Working.
  const lagging = read.kind === "needs_you" && read.reason === "Start it" && (fs?.make_it ?? run?.make_it) == null;
  const status = headStatus(running && ((read.kind !== "waiting" && read.kind !== "needs_you") || lagging) ? { ...read, kind: "working", words: "Working" } : read, where);
  const title = head.data?.title ?? fs?.title ?? p?.name ?? "";
  // With no tab picked, it opens where the work is and stays there while it fills in (no jumping under the reader).
  if (!opened && !facts.loading && p) setOpened(firstTab(facts.progress));
  // …except when the cut first lands: that's the moment to see it (S3-09), once.
  if (opened && facts.made && !cutSeen) {
    setCutSeen(true);
    if (opened !== "cut" && !tabFrom(params)) setOpened("cut");
  }
  const tab: TabId = tabFrom(params) ?? opened ?? firstTab(facts.progress);
  const pick = (t: TabId) => {
    const next = new URLSearchParams(params);
    next.delete("step");
    next.set("tab", t);
    setParams(next, { replace: true });
    setSide("preview");
  };
  const finished = !!p?.finished_at || facts.made || state === "delivered";
  const target = p && { id, name: title, creditsUsed: p.credits_used, released: p.released };
  const menu = (
    <VideoMenu
      title={title}
      cut={cutFile ? { file: cutFile, name: mp4(title) } : null}
      onStop={!rail && running && maker ? () => setStopping(true) : undefined}
      onMove={p && maker && !archived ? () => setMoving(true) : undefined}
      onRename={p && maker && !archived ? () => setRenaming(true) : undefined}
      onRelease={target && maker && !archived && !finished && p.script_draft_id && !fs ? () => video.release(target) : undefined}
      onArchive={target && maker && !archived && finished ? () => video.archive(target) : undefined}
    />
  );
  const header = head.data ? (
    <VideoHead brand={{ id: brandId, name: brands?.find((b) => b.id === brandId)?.name ?? "" }} projectId={id} head={head.data} status={status} cast={facts.cast.filter((a) => a.kind === "character").map((a) => a.name)} lookOnly={!!lookOnly || archived} phone={!rail} menu={menu} stop={rail && running && maker ? { busy: stop.isPending, onPress: () => setStopping(true) } : null} started={run?.started} />
  ) : (
    <WaitingHead title={title} status={p ? null : status} phone={!rail} brandId={brandId} menu={p && menu} />
  );
  const chat = (
    <Chat p={p} fs={fs ?? null} run={run ?? null} clips={clips} owner={owner} maker={maker} state={state} running={running} online={online} archived={archived} lookOnly={lookOnly} onRestore={target ? () => void video.restore(target) : undefined} onWatch={() => pick("cut")} onSettings={() => pick("plan")} phone={!rail} progress={liveRun ?? null} />
  );
  const preview = <Preview onEditor={setEditing} p={p} head={head.data ?? undefined} run={liveRun ?? null} tab={tab} onTab={pick} toChat={rail ? undefined : () => setSide("chat")} lookOnly={lookOnly ?? (archived ? "It's archived. Restore it to keep working." : null)} phone={!rail} facts={facts} />;
  return (
    <main className={`flex min-h-0 flex-col ${rail ? "h-screen flex-row" : "h-dvh"}`}>
      {rail ? (
        <>
          <section aria-label="Chat" className={`flex min-h-0 shrink-0 flex-col border-r border-border bg-surface ${editing ? "w-[400px]" : "w-[min(600px,50%)]"}`}>
            {header}
            {chat}
          </section>
          {preview}
        </>
      ) : (
        <>
          {header}
          <div className="border-b border-border bg-surface px-3 py-2">
            <div role="tablist" aria-label="Chat or preview" className="flex gap-0.5 rounded-md bg-surface-2 p-0.5">
              {(["chat", "preview"] as const).map((s) => (
                <button key={s} type="button" role="tab" aria-selected={side === s} onClick={() => setSide(s)} className={`flex h-control flex-1 items-center justify-center rounded-[5px] text-sm font-medium ${side === s ? "bg-surface text-text shadow-[0_1px_2px_rgb(28_27_25/0.06),0_2px_8px_rgb(28_27_25/0.04)]" : "text-muted"}`}>
                  {s === "chat" ? "Chat" : "Preview"}
                </button>
              ))}
            </div>
          </div>
          {/* Both stay mounted: a typed note, its files and anything waiting to send survive the switch. */}
          <div className={`min-h-0 flex-1 flex-col ${side === "chat" ? "flex" : "hidden"}`}>{chat}</div>
          <div ref={previewSide} className={`min-h-0 flex-1 flex-col ${side === "preview" ? "flex" : "hidden"}`}>{preview}</div>
        </>
      )}
      {video.dialog}
      {renaming && p && <RenameDialog projectId={id} freestyleId={fs?.id ?? null} title={title} onClose={() => setRenaming(false)} />}
      {moving && p && <MoveDialog brandId={brandId} projectId={id} title={title} now={head.data?.folder?.id ?? p.folder_id ?? null} onClose={() => setMoving(false)} />}
      {stopping && (
        <Dialog title="Stop the director?" actionLabel="Stop" danger busy={stop.isPending || actions.stop.isPending} onCancel={() => setStopping(false)} onConfirm={() => (fs ? actions.stop.mutate(undefined, { onSettled: () => setStopping(false) }) : stop.mutate())}>
          <p>It makes no more moves. What it already started still finishes, and nothing is undone.</p>
        </Dialog>
      )}
    </main>
  );
}

/** Before the owner's OK an editor can't read the video yet: the title and status only (the title alone if the header
 *  can't be read). */
function WaitingHead({ title, status, phone, brandId, menu }: { title: string; status: Status | null; phone: boolean; brandId: number; menu?: ReactNode }) {
  return (
    <header role="banner" className={`flex items-center gap-3 border-b border-border px-5 ${phone ? "min-h-[52px] px-3" : "py-3"}`}>
      {phone && (
        <Link to={`/b/${brandId}/videos`} aria-label="Back" className="grid size-control place-items-center text-muted">
          <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
        </Link>
      )}
      <h1 className="min-w-0 truncate text-lg font-semibold">{title}</h1>
      {status && <span className="text-xs font-medium text-muted">{status.words}</span>}
      {menu && <span className="ml-auto">{menu}</span>}
    </header>
  );
}

/** The page while it loads (S3-15): the header, three messages and the panel as grey shapes; the box is already there. */
function Loading({ phone }: { phone: boolean }) {
  const thread = (
    <div className="flex flex-1 flex-col gap-4 px-5 py-4" role="status" aria-label="Loading">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex gap-2.5">
          <Skeleton className="size-6 shrink-0 !rounded-full" />
          <div className="flex flex-col gap-2">
            <Skeleton className="h-3 w-[120px]" />
            <Skeleton className="h-3 w-[380px] max-w-[60vw]" />
            <Skeleton className="h-3 w-[300px] max-w-[50vw]" />
          </div>
        </div>
      ))}
    </div>
  );
  const head = (
    <div className="flex flex-col gap-2 border-b border-border px-5 py-2.5">
      <Skeleton className="h-3 w-40" />
      <Skeleton className="h-[18px] w-60" />
      <div className="flex gap-2">
        <Skeleton className="h-[26px] w-[110px]" />
        <Skeleton className="h-[26px] w-[90px]" />
        <Skeleton className="h-[26px] w-20" />
      </div>
    </div>
  );
  const box = <Composer placeholder="Tell the director what to change" disabled upload onSend={() => {}} />;
  if (phone)
    return (
      <div className="flex h-dvh flex-col bg-surface">
        {head}
        {thread}
        {box}
      </div>
    );
  return (
    <div className="flex h-screen">
      <section className="flex w-[min(600px,50%)] shrink-0 flex-col border-r border-border bg-surface">
        {head}
        {thread}
        {box}
      </section>
      <section className="flex flex-1 flex-col bg-bg">
        <div className="flex h-10 items-stretch gap-0.5 border-b border-border bg-surface px-4" aria-hidden>
          {["Cut", "Clips", "Cast", "Plan", "Script"].map((t, i) => (
            <span key={t} className={`-mb-px inline-flex items-center border-b-2 px-2.5 text-sm font-medium ${i === 0 ? "border-text text-text" : "border-transparent text-muted"}`}>{t}</span>
          ))}
        </div>
        <div className="flex gap-5 p-5">
          <Skeleton className="h-[533px] w-[300px] rounded-[10px]" />
          <div className="flex flex-col gap-3">
            <Skeleton className="h-[18px] w-40" />
            <Skeleton className="h-3 w-[200px]" />
            <Skeleton className="h-9 w-[220px]" />
            <Skeleton className="h-9 w-[220px]" />
          </div>
        </div>
      </section>
    </div>
  );
}

/** The conversation (oldest first, newest at the bottom), and the box under it. A freestyle's thread is its first words,
 *  moves and held sends, with the notes saved on its video; a video made from a script reads its director's thread. */
function Chat({ p, fs, run, clips, owner, maker, state, running, online, archived, lookOnly, onRestore, onWatch, onSettings, phone, progress }: { p: Project | null; fs: Freestyle | null; run: Run | null; clips: components["schemas"]["ProjectClipOut"][]; owner: boolean; maker: boolean; state: string; running: boolean; online: boolean; archived: boolean; lookOnly: string | null; onRestore?: () => void; onWatch: () => void; onSettings: () => void; phone: boolean; progress: Progress | null }) {
  const queryClient = useQueryClient();
  const id = p?.id ?? fs?.project_id ?? 0;
  const actions = useFreestyleActions(fs?.id ?? null);
  const script = useScript(fs?.script_id ?? 0).data;
  const scroller = useRef<HTMLDivElement>(null);
  const said = run?.thread ?? [];
  const turns = run?.turns ?? [];
  const known = (t: Said) => said.find((x) => x.kind === "message" && x.who === t.who && x.text === t.text);
  const byId = new Map(said.map((x) => [x.id, x]));
  // A freestyle's thread is its first words, its held sends and the director's moves in its words; each move keeps the run
  // card or the delivery note it is (v6 piece C and D), from the video's own thread.
  const items: Said[] = (fs
    ? [...fs.thread.map((t) => (t.kind === "message" ? { ...t, answered: known(t)?.answered } : { ...t, run: byId.get(t.id)?.run ?? null, note: byId.get(t.id)?.note ?? null })), ...said.filter((x) => x.kind === "message" && !fs.thread.some((t) => t.kind === "message" && t.who === x.who && t.text === x.text)).map((x) => ({ ...x, id: `note-${x.id}` })), ...said.filter((x) => x.kind === "ask")].sort((a, b) => serverTime(a.at).getTime() - serverTime(b.at).getTime())
    : [...said]);
  // The live card sits after its run's other moves (the treatment, a held step), as the newest thing it says (S3-03).
  const live = items.findIndex((t) => t.run && t.run === progress?.run);
  if (live >= 0) {
    const [card] = items.splice(live, 1);
    const next = items.findIndex((t, i) => i >= live && (t.kind === "message" || t.note || t.run));
    items.splice(next < 0 ? items.length : next, 0, card);
  }
  const seen = useSeen(id);
  // The newest note opens in full; once a later run starts (a revision), it folds to its line too (S3-12).
  const lastIndex = items.map((t) => !!t.note).lastIndexOf(true);
  const lastNote = lastIndex >= 0 && !items.slice(lastIndex + 1).some((t) => t.run) ? items[lastIndex].id : undefined;
  const unwatched = (progress?.changed ?? []).filter((c) => !c.watched && c.take_id != null).map((c) => c.take_id!);
  const watch = () => (seen.mutate(unwatched), onWatch());
  const heldMove = [...items].reverse().find((t) => t.kind === "move" && t.status === "held")?.id;
  const refreshAsks = useAskRefresh(id);
  const cards = useAsks(id, running || (run?.waiting?.length ?? 0) > 0).data ?? [];
  // The pinned bar reads the run's waiting questions: a card answered or closed anywhere (here, in Needs you, by the
  // director's own pick) leaves it at once, and the run is read again so a new question joins it.
  const asked = (run?.waiting ?? []).filter((w) => { const c = cards.find((a) => a.id === w.id); return !c || isOpen(c); });
  const states = cards.map((a) => `${a.id}:${a.state}`).join(",");
  const lastStates = useRef(states);
  useEffect(() => {
    if (lastStates.current === states) return;
    lastStates.current = states;
    void queryClient.invalidateQueries({ queryKey: ["director", id] });
  }, [states, id, queryClient]);
  const newest = `${items.length}:${items.at(-1)?.id}:${progress?.run}:${progress?.status}:${progress?.failed ? 1 : 0}:${cards.length}`; // a card's own changes don't pull the chat down
  useEffect(() => {
    scroller.current?.scrollTo?.({ top: scroller.current.scrollHeight });
  }, [newest]);

  // Saved notes and the presses that make them (today's; the start card and the progress card replace them, screens 4–5).
  const noted = !running && (run?.unread ?? 0) > 0 && run?.status !== "none";
  const again = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/director", { params: { path: { project_id: id } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["director", id], data);
      if (fs) void queryClient.invalidateQueries({ queryKey: ["freestyle", fs.id] });
      void queryClient.invalidateQueries({ queryKey: ["idea", id] });
      return refreshJobs(queryClient);
    },
  });
  // "Start the plan again" (S3-08): a new run, as Carry on starts one, that plans the whole video again after Make it.
  const planAgain = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/director/plan-again", { params: { path: { project_id: id } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["director", id], data);
      if (fs) void queryClient.invalidateQueries({ queryKey: ["freestyle", fs.id] });
      void queryClient.invalidateQueries({ queryKey: ["idea", id] });
      return refreshJobs(queryClient);
    },
  });
  // A start card waiting for Make it is the press, as are a stopped or failed run's own (Carry on, its fixes): the general
  // one stands aside (S3-02, S3-08, S3-11).
  const startOpen = cards.some((a) => a.kind === "start" && isOpen(a));
  const moneyOpen = cards.some((a) => ["start", "budget", "own", "plan"].includes(a.kind) && isOpen(a));
  // A delivered video's next run starts by talking (S3-12): no press of its own under the note (#1318's was temporary).
  const ended = ["stopped", "failed", "declined", "withdrawn", "ended", "none"].includes(state) && !moneyOpen && !progress?.stopped && !progress?.failed;
  const mayStart = fs ? owner : maker; // a freestyle's run is the owner's to start again; a script video's, its maker's
  const blocked = run?.start_blocked || null;
  const startLabel = state === "none" ? "Make it" : (state === "stopped" || state === "ended") && noted ? "Start again with this note" : "Make it again";
  const stopped = progress?.stopped ? stoppedParts({ progress, onCarryOn: () => (planAgain.reset(), again.mutate()), onPlanAgain: () => (again.reset(), planAgain.mutate()), busy: again.isPending, planBusy: planAgain.isPending, blocked, error: (again.error ?? planAgain.error)?.message ?? null }) : null;
  const presses = !archived && !lookOnly && (
    <>
      {ended && mayStart && p && (
        <Button variant={noted || state === "none" ? "primary" : "secondary"} dense busy={again.isPending} disabled={!!blocked} reason={blocked} price={run?.run_price || undefined} charge="estimate" onClick={() => again.mutate()}>
          {startLabel}
        </Button>
      )}
    </>
  );

  // The box: a note while it works is read on its next move; after a stop or a delivery the owner's is saved for Make it
  // again (a note never starts a run by itself, the Producer); an editor's change on a freestyle goes to the owner first.
  const [queued, setQueued] = useState<{ text: string; files: number[] }[]>([]);
  const saveNote = useMutation({
    mutationFn: async ({ text, files }: { text: string; files: number[] }) => {
      const { data, error } = await api.POST("/projects/{project_id}/director/messages", { params: { path: { project_id: id } }, body: { text, ...(files.length ? { files } : {}) } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["director", id], data);
      if (fs) void queryClient.invalidateQueries({ queryKey: ["freestyle", fs.id] });
      void queryClient.invalidateQueries({ queryKey: ["asks", id] }); // a locked line's answer comes at once (S3-14)
      return refreshJobs(queryClient);
    },
  });
  // An editor's change with nothing running is a new run, held for the owner: it goes through the freestyle. Every other
  // note (any while it runs, the owner's after it) is the director's own, with pictures or clips if any.
  const viaFreestyle = !!fs && !running && !owner;
  const send = viaFreestyle ? actions.change : saveNote;
  const go = (text: string, files: number[], done: () => void) => {
    if (!online) return (setQueued((q) => [...q, { text, files }]), done());
    const after = { onSuccess: done };
    return viaFreestyle ? actions.change.mutate(text, after) : saveNote.mutate({ text, files }, after);
  };
  // Typed while offline: it sends once the page is back (S3-16).
  // Each note leaves the queue only once it's sent: one that fails stays, and says why.
  const sendingQueue = useRef(false); // one pass at a time: a second "online" while it sends doesn't send twice
  useEffect(() => {
    if (!queued.length) return;
    const back = async () => {
      if (sendingQueue.current) return;
      sendingQueue.current = true;
      for (const n of queued) {
        try {
          await (viaFreestyle ? actions.change.mutateAsync(n.text) : saveNote.mutateAsync(n));
          setQueued((q) => q.filter((x) => x !== n));
        } catch {
          break; // its error shows under the box; it stays queued for the next try
        }
      }
      sendingQueue.current = false;
    };
    window.addEventListener("online", back);
    return () => window.removeEventListener("online", back);
  }, [queued, viaFreestyle]); // eslint-disable-line react-hooks/exhaustive-deps

  const waiting = state === "waiting";
  const fromScript = !!script && !!fs && serverTime(script.created_at) < serverTime(fs.created_at);
  const placeholder = !online ? "You can type; it sends when you’re back" : run?.status === "delivered" || state === "delivered" ? "Say what to change: “warmer light in scene 2”, “swap the B-roll at 0:14”…" : running && !turns.some((t) => t.tool) ? "Add anything the director should know" : "Tell the director what to change";
  const note = queued.length ? (queued.length === 1 ? "Sends when you’re back." : `${queued.length} notes send when you’re back.`) : running && items.at(-1)?.kind === "message" ? "The director will read this on its next move." : noted ? (state === "stopped" || state === "ended" ? "Saved. Press Start again with this note to make it." : null) : viaFreestyle && !owner && !running ? "Each change goes to the owner first. Nothing is spent until they say yes." : null;
  const closed = archived ? "It's archived. Restore it to keep working." : lookOnly ? lookOnly : waiting && !owner ? (fromScript ? "Opens once the owner approves" : "You can change it once the owner approves it, or withdraw it now.") : null;
  const first = fromScript && script && fs ? <ScriptCard fs={fs} script={script} pid={id} brandId={p?.brand_id ?? fs.brand_id ?? 0} /> : null;
  const opening = items.find((t) => t.kind === "message")?.id;
  // A freestyle's send held before its video has a card for it: the same held card, with Withdraw the request (S3-07).
  const changeUpTo = useHeldChange(fs, state === "change");
  // Its own card when the video has one but its thread isn't open yet (a send before the owner's OK); else one drawn the same.
  const shown = new Set(items.filter((t) => t.kind === "ask").map((t) => t.ask_id));
  const orphan = cards.find((a) => ["start", "budget", "own", "plan"].includes(a.kind) && isOpen(a) && !shown.has(a.id));
  // A freestyle's start card withdraws through the freestyle (its frozen send goes too); every other card withdraws itself.
  const withdraw = fs && maker ? () => actions.withdraw.mutate(undefined, { onSuccess: () => void refreshAsks() }) : undefined;
  const withdrawFor = (a: { kind: string }) => (a.kind === "start" ? withdraw : undefined);
  const heldSend = (t: Said) =>
    !fs || t.id !== heldMove ? null : orphan ? ( // the owner answers on the cards themselves: never "the owner has been asked" to him
      <AskCard ask={orphan} owner={owner} onWithdraw={withdrawFor(orphan)} />
    ) : !owner && (waiting || state === "change") && !cards.some((a) => shown.has(a.id) && isOpen(a) && a.can.includes("withdraw")) ? (
      <HeldSend projectId={id} change={state === "change"} upTo={state === "change" ? changeUpTo : (fs.make_it_up_to ?? fs.up_to)} sentAt={t.at} owner={owner} onWithdraw={withdraw ?? (() => actions.withdraw.mutate())} />
    ) : null;
  // "Change the plan first" (S3-02): the message box, ready for the change.
  const focusBox = () => document.getElementById("director-box")?.focus();
  return (
    <>
      {!online && (
        <div role="status" className="flex items-center gap-2 border-b border-border bg-surface-2 px-5 py-2 text-sm text-muted">
          <WifiOff size={14} strokeWidth={1.75} aria-hidden className="shrink-0" />
          <span>You’re offline. The director keeps working on the server; this page catches up when you’re back.</span>
          <button type="button" className="ml-auto min-h-control shrink-0 px-2 font-medium hover:text-text lg:min-h-0 lg:px-0" onClick={() => void queryClient.refetchQueries({ type: "active" })}>
            Retry
          </button>
        </div>
      )}
      {lookOnly && p && (
        <div className="border-b border-border px-5 py-2">
          <Banner tone="info" title={`This is ${p.created_by_name ? `${p.created_by_name}'s` : "someone else's"} video. You can look, but only ${p.created_by_name || "someone else"} or the owner can change it.`} />
        </div>
      )}
      {archived && (
        <div className="border-b border-border px-5 py-2">
          <Banner tone="info" title="Archived" action={onRestore && maker ? <Button variant="secondary" dense onClick={onRestore}>Restore</Button> : undefined}>
            It's out of the lists. Its clips and downloads are kept. Restore it to keep working.
          </Banner>
        </div>
      )}
      <div ref={scroller} className="flex min-h-0 flex-1 flex-col overflow-y-auto px-5 pb-2 pt-4 [mask-image:linear-gradient(to_bottom,transparent_0,#000_36px)]">
        <ol aria-label="Conversation with the director" className="mt-auto flex flex-col gap-4">
          {items.map((t) =>
            t.kind === "ask" ? (
              <Item key={t.id} t={t} owner={owner} words={cards.some((a) => a.id === t.ask_id) ? null : t.text}>
                {(() => {
                  const a = cards.find((x) => x.id === t.ask_id);
                  if (a?.kind === "instead") return <InsteadCard ask={a} />; // S3-14: what can change instead of a locked line
                  return a && <AskCard ask={a} owner={owner} onChangePlan={a.kind === "start" ? focusBox : undefined} onWithdraw={withdrawFor(a)} />;
                })()}
              </Item>
            ) : t.kind === "message" ? (
              <Item key={t.id} t={t} words={t.id === opening && first ? null : t.text} first={t.id === opening ? first : undefined} excerpt={t.id === opening} />
            ) : t.run && progress && t.run === progress.run && startOpen && !progress.made ? (
              // Its start card is the newest thing it says: nothing runs until Make it (S3-02).
              heldSend(t) && (
                <Item key={t.id} t={t} owner={owner} words={null}>
                  {heldSend(t)}
                </Item>
              )
            ) : t.run && progress && t.run === progress.run ? (
              // The newest run: its one live card (S3-03…S3-13), then what stopped it, if anything.
              <Fragment key={t.id}>
                <Item t={t} owner={owner} words={null}>
                  <RunCard progress={progress} phone={phone} />
                  {heldSend(t)}
                </Item>
                {progress.stopped && (
                  <>
                    <li className="flex items-center gap-2 pl-[34px] text-xs text-muted">
                      <CircleStop size={12} strokeWidth={1.75} aria-hidden className="shrink-0 text-faint" />
                      {stopped!.line}
                    </li>
                    <Item t={{ ...t, id: `${t.id}-stopped`, status: "done", at: progress.stopped.at }} owner={owner} words={null}>
                      {stopped!.reply}
                    </Item>
                  </>
                )}
                {progress.failed && p && (
                  <Item t={{ ...t, id: `${t.id}-failed`, status: "done" }} owner={owner} words={null}>
                    <Failed progress={progress} projectId={p.id} onSettings={onSettings} onCarryOn={() => again.mutate()} busy={again.isPending} blocked={blocked} />
                  </Item>
                )}
              </Fragment>
            ) : t.run ? (
              // An earlier run: its card in a line.
              <Item key={t.id} t={t} owner={owner} words={<span className="text-[13px] text-muted">{plain(t.text, clips)}</span>}>
                {heldSend(t)}
              </Item>
            ) : t.note ? (
              <Item key={t.id} t={t} owner={owner} words={t.id === lastNote ? "Here’s the cut." : null}>
                {t.id === lastNote ? <DeliveryNote note={t.note} changes={unwatched.length} onWatch={p ? watch : undefined} /> : <PastNote note={t.note} />}
              </Item>
            ) : (
              <Item key={t.id} t={t} owner={owner} words={plain(t.text, clips) || "Deciding what to do next."} why={plain(t.why ?? "", clips)}>
                {heldSend(t)}
              </Item>
            ),
          )}
        </ol>
        {id > 0 && <CastOk projectId={id} />}
        {fs?.reel_script_id && !items.length && <ReelBlock scriptId={fs.reel_script_id} published={false} /> /* Use a reel: its read, before the script is written */}
        {again.isError && <p role="alert" className="mt-2 text-sm text-danger">{again.error.message}</p>}
        {actions.withdraw.isError && <p role="alert" className="mt-2 text-sm text-danger">{actions.withdraw.error.message}</p>}
      </div>
      {presses && <div className="flex flex-wrap items-center justify-end gap-2 px-5 pb-1 empty:hidden">{presses}</div>}
      <WaitingBar waiting={asked} />
      <Composer placeholder={placeholder} closed={closed} note={note} error={send.isError ? send.error.message : null} busy={send.isPending} onSend={go} upload={!viaFreestyle} />
    </>
  );
}

/** A held change's own price, "up to", from its held job (JobOut.freestyle.up_to, the figure its Needs you row shows): the
 *  director's `run_price` is 0 while a run is going, and a change's held first turn counts as going (QA on #1194). */
function useHeldChange(fs: Freestyle | null | undefined, on: boolean) {
  const held = useQuery({
    queryKey: ["held-jobs"],
    enabled: !!fs && on,
    refetchInterval: 15_000,
    queryFn: async () => (await api.GET("/jobs", { params: { query: { status: "needs_owner_approval" } } })).data ?? [],
  });
  return held.data?.find((j) => j.status === "needs_owner_approval" && j.freestyle?.id === fs?.id && j.freestyle?.change)?.freestyle?.up_to;
}

/** The script a video was made from (E_EditorSent), in place of pasted words. */
function ScriptCard({ fs, script, pid, brandId }: { fs: Freestyle; script: NonNullable<ReturnType<typeof useScript>["data"]>; pid: number; brandId: number }) {
  const opening = fs.thread.find((t) => t.kind === "message")?.text;
  const slot = script.versions.find((v) => v.project_id === pid) ?? script.versions.find((v) => v.text === opening);
  const lines = (slot?.text ?? "").split("\n").filter((l) => l.trim()).length;
  return (
    <div className="flex items-center gap-3 rounded-md border border-border bg-surface px-3 py-2.5">
      <FileText size={16} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{`From script ${script.title} · version ${letterOf(slot?.slot ?? 0)}`}</p>
        <p className="text-sm text-muted">{[slot?.seconds && mmss(slot.seconds), `${lines} line${lines === 1 ? "" : "s"}`].filter(Boolean).join(" · ")}</p>
      </div>
      <Link to={`/b/${brandId}/scripts/${script.id}`} className="inline-flex min-h-control shrink-0 items-center text-sm text-muted hover:text-text lg:min-h-0">
        Open script
      </Link>
    </div>
  );
}

/** The message box (S3): "Tell the director what to change", the upload and the send. Enter sends, Shift+Enter is a new
 *  line. Pictures or clips sent with a note are for this video only (rule 12). `closed`: why it can't be used now. */
function Composer({ placeholder, closed, note, error, busy, upload, disabled, onSend }: { placeholder: string; closed?: string | null; note?: string | null; error?: string | null; busy?: boolean; upload?: boolean; disabled?: boolean; onSend: (text: string, files: number[], done: () => void) => void }) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<{ id: number; name: string }[]>([]);
  const [adding, setAdding] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const sending = useRef(false); // one press, one note: a second click before the first returns does nothing
  useEffect(() => {
    if (!busy) sending.current = false;
  }, [busy]);
  const off = disabled || !!closed;
  const ready = !!text.trim() && !busy && !adding && !off;
  const go = () => {
    if (!ready || sending.current) return;
    sending.current = true;
    onSend(text.trim(), files.map((f) => f.id), () => ((sending.current = false), setText(""), setFiles([])));
  };
  const add = async (list: FileList | null) => {
    setProblem(null);
    setAdding(true);
    try {
      for (const f of Array.from(list ?? []).slice(0, 6 - files.length)) {
        const stored = await uploadFile(f);
        setFiles((now) => [...now, { id: stored.id, name: f.name }]);
      }
    } catch (e) {
      setProblem((e as Error).message);
    } finally {
      setAdding(false);
    }
  };
  return (
    <form
      aria-label="Your message"
      className="mx-5 mb-4 mt-1 flex flex-col gap-2 rounded-xl border border-border-strong bg-surface py-2 pl-3 pr-2.5 focus-within:border-focus max-lg:mx-3 max-lg:mb-3"
      onSubmit={(e) => {
        e.preventDefault();
        go();
      }}
    >
      <label htmlFor="director-box" className="sr-only">
        Tell the director what to change
      </label>
      <textarea
        id="director-box"
        rows={1}
        maxLength={2000}
        value={text}
        disabled={off}
        placeholder={closed ?? placeholder}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            go();
          }
        }}
        className="mt-0.5 min-h-5 resize-none bg-transparent text-base leading-5 outline-none! placeholder:text-[#6f727a] disabled:cursor-not-allowed lg:text-sm"
      />
      {files.length > 0 && (
        <ul aria-label="Sent with it, for this video only" className="flex flex-wrap gap-1.5">
          {files.map((f) => (
            <li key={f.id} className="inline-flex min-h-7 items-center gap-1.5 rounded-md border border-border bg-surface px-2 text-xs">
              <Paperclip size={12} strokeWidth={1.75} aria-hidden className="text-muted" />
              <a href={fileUrl(f.id)} target="_blank" rel="noreferrer" className="max-w-40 truncate">{f.name}</a>
              <button type="button" aria-label={`Take off ${f.name}`} onClick={() => setFiles((now) => now.filter((x) => x.id !== f.id))} className="-mr-1 grid size-control place-items-center text-muted hover:text-text lg:size-5">
                <X size={12} strokeWidth={1.75} aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex items-center gap-1.5">
        {upload && (
          <>
            <input ref={picker} type="file" accept="image/*,video/*" multiple hidden onChange={(e) => (void add(e.target.files), (e.target.value = ""))} />
            <button type="button" aria-label="Add pictures or clips for this video" title="Pictures or clips, for this video only" disabled={off || adding || files.length >= 6} onClick={() => picker.current?.click()} className="grid size-8 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-text disabled:opacity-50 max-lg:size-control">
              <Upload size={14} strokeWidth={1.75} aria-hidden />
            </button>
          </>
        )}
        <span className={`min-w-0 flex-1 text-xs ${error || problem ? "text-danger" : "text-muted"}`} role="status">
          {error ?? problem ?? (adding ? "Adding…" : note)}
        </span>
        <button type="submit" aria-label="Send to the director" disabled={!ready} className={`grid size-8 shrink-0 place-items-center rounded-lg max-lg:size-control ${ready ? "bg-ink text-white" : "bg-surface-3 text-faint"}`}>
          <ArrowUp size={14} strokeWidth={1.75} aria-hidden />
        </button>
      </div>
    </form>
  );
}
