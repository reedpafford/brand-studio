import { useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CircleHelp, Clock, LoaderCircle, MessageSquare, Pause, Play, RefreshCw, TriangleAlert, Upload, WandSparkles, X } from "lucide-react";
import { api, errorText, polled } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl, uploadFile } from "../api/upload";
import { Link } from "react-router-dom";
import { Button } from "../components";
import { refreshJobs } from "../jobs/refresh";
import { serverTime } from "../time";
import { useRail } from "../useMedia";
import { Direction } from "./Direction";
import { VoiceAudition } from "./VoiceAudition";

export type Ask = components["schemas"]["AskOut"];
type Price = components["schemas"]["AskPrice"];
type Saved = components["schemas"]["SavedOption"];

const OPEN = ["open", "uploading", "generating", "ready", "failed", "held"];

/** Every card on the video (v6 piece B), read again the moment one is asked, answered or made (./live.ts). */
export function useAsks(projectId: number) {
  return useQuery({
    queryKey: ["asks", projectId],
    enabled: projectId > 0,
    queryFn: () => polled(api.GET("/projects/{project_id}/asks", { params: { path: { project_id: projectId } } }), []),
  });
}

/** After any answer: the cards, the run (its waiting bar and start card), the header, Needs you and the jobs. */
export function useAskRefresh(projectId: number) {
  const queryClient = useQueryClient();
  // The press waits for its card only; the rest refresh behind it, so a slow read elsewhere never keeps the card busy.
  return () => {
    for (const queryKey of [["director", projectId], ["idea", projectId], ["run-progress", projectId], ["needs-you"], ["freestyle"]]) void queryClient.invalidateQueries({ queryKey });
    void refreshJobs(queryClient);
    return queryClient.invalidateQueries({ queryKey: ["asks", projectId] });
  };
}

/** "$0.24" to the owner, "3 credits" to an editor (rule 4). */
export const said = (p: Price | null | undefined) => (!p ? "" : p.usd != null ? `$${p.usd.toFixed(2)}` : `${Math.ceil(p.credits - 1e-9)} credit${Math.ceil(p.credits - 1e-9) === 1 ? "" : "s"}`);
const clock = (iso: string) => serverTime(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const NOUN: Record<string, string> = { cast: "looks", presenter: "avatars", place: "places", brand_item: "options", voice: "voices", product: "options" };

/** The card's presses: each posts its answer and refreshes what it changes. */
export function useAskActions(ask: Ask) {
  const refresh = useAskRefresh(ask.project_id);
  const call = async (path: "answer" | "generate" | "cancel" | "uploading", body: object) => {
    const url = `/asks/{ask_id}/${path}` as "/asks/{ask_id}/answer";
    const { data, error } = await api.POST(url, { params: { path: { ask_id: ask.id } }, body: body as never });
    if (!data) throw new Error(errorText(error));
    return data;
  };
  return useMutation({
    mutationFn: ({ path = "answer", body }: { path?: "answer" | "generate" | "cancel" | "uploading"; body: object }) => call(path, body),
    onSettled: () => refresh(),
  });
}

/** A tile: a saved item or a made option, its picture, name and note; the picked one is outlined. */
function Tile({ file, name, note, on, onPick, drawing }: { file?: number | null; name: string; note?: string; on?: boolean; onPick?: () => void; drawing?: boolean }) {
  const pic = file != null ? <img src={fileUrl(file)} alt="" className="size-full object-cover" /> : <span className={`block size-full ${drawing ? "bg-[linear-gradient(110deg,#ececf0_30%,#f6f6f8_45%,#ececf0_60%)]" : "bg-surface-2"}`} />;
  return (
    <button type="button" disabled={!onPick} aria-pressed={on} onClick={onPick} className="flex w-24 flex-col gap-1 text-left text-xs max-lg:w-[86px]">
      <span className={`block h-32 w-24 overflow-hidden rounded-md max-lg:h-[114px] max-lg:w-[86px] ${on ? "outline outline-2 outline-offset-2 outline-accent" : ""}`}>{pic}</span>
      <span className="font-medium">{name}</span>
      {note && <span className="text-muted">{note}</span>}
    </button>
  );
}

/** A voice row (S4-01): play its free sample, pick it. */
function VoiceRow({ o, on, onPick }: { o: Saved; on: boolean; onPick: () => void }) {
  const [playing, setPlaying] = useState(false);
  const audio = useRef<HTMLAudioElement>(null);
  const src = o.sample_file_id != null ? fileUrl(o.sample_file_id) : o.sample_url ? `/api${o.sample_url}` : null;
  return (
    <div className={`flex items-center gap-3 rounded-md border px-3 py-2 ${on ? "border-accent-line bg-accent-soft" : "border-border"}`}>
      {src && (
        <button type="button" aria-label={`${playing ? "Pause" : "Play"} ${o.name}'s sample`} onClick={() => (playing ? audio.current?.pause() : void audio.current?.play()?.catch(() => {}))} className="grid size-8 shrink-0 place-items-center rounded-md border border-border-button bg-surface max-lg:size-control">
          {playing ? <Pause size={14} strokeWidth={1.75} aria-hidden /> : <Play size={14} strokeWidth={1.75} aria-hidden />}
          <audio ref={audio} src={src} preload="none" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />
        </button>
      )}
      <button type="button" aria-pressed={on} onClick={onPick} className="min-w-0 flex-1 text-left max-lg:min-h-control">
        <span className="block text-sm font-medium">{o.name}</span>
        <span className="block truncate text-xs text-muted">{[o.note, o.used_in ? `used in ${o.used_in} video${o.used_in === 1 ? "" : "s"}` : ""].filter(Boolean).join(" · ")}</span>
      </button>
    </div>
  );
}

/** A way to answer that isn't a saved item: Upload, Reply, Generate options (S4-01). */
function Way({ icon: Icon, title, note, dashed, onPress, busy }: { icon: typeof Upload; title: string; note: string; dashed?: boolean; onPress: () => void; busy?: boolean }) {
  return (
    <button type="button" onClick={onPress} disabled={busy} className={`flex min-w-0 flex-1 items-start gap-2 rounded-md border px-2.5 py-2 text-left text-[13px] max-lg:flex-col max-lg:gap-1 ${dashed ? "border-dashed border-border-strong" : "border-border-button"} hover:bg-surface-2 disabled:opacity-60`}>
      {busy ? <LoaderCircle size={14} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0 animate-spin" /> : <Icon size={14} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />}
      <span className="min-w-0">
        <span className="block font-semibold">{title}</span>
        <span className="block text-xs leading-4 text-muted">{note}</span>
      </span>
    </button>
  );
}

const HEAD = {
  ask: ["bg-accent-soft text-accent-text", CircleHelp],
  wait: ["bg-warning-soft text-warning", Clock],
  done: ["bg-surface-2 text-muted", Check],
  gone: ["bg-surface-2 text-muted", X],
} as const;

/** One card the director asks with (S4-01 to S4-04; S3-02, S3-05 to S3-07; P-06, P-07, P-15): the question and why, the
 *  brand's saved items first, then Upload, Reply or Generate options (price first; made for this video only), a story's
 *  two choices with the director's pick and its time, or a money card: Make it, Approve or Keep it, or Withdraw. Answered
 *  cards fold to a line and can be changed; one no longer needed says why. `onChangePlan`: the message box, for "Change the
 *  plan first". `onWithdraw`: a freestyle's own Withdraw (it lets its send go too). */
export function AskCard({ ask: a, owner, onChangePlan, onWithdraw, onDone }: { ask: Ask; owner: boolean; onChangePlan?: () => void; onWithdraw?: () => void; onDone?: () => void }) {
  const act = useAskActions(a);
  const [pick, setPick] = useState<string | number | null>(null);
  const [replying, setReplying] = useState(false);
  const [text, setText] = useState("");
  const [voiceName, setVoiceName] = useState(""); // Describe it: the brand's name for the voice
  const [changing, setChanging] = useState<"" | "options" | "answer">("");
  const [every, setEvery] = useState(false); // a voice card lists its first few; the rest a press away
  const [upload, setUpload] = useState<{ name: string; file?: string } | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const can = (how: string) => a.can.includes(how);
  const money = ["start", "budget", "own", "plan"].includes(a.kind);
  const voice = a.kind === "voice";
  const brand = a.saved_in.replace(/^Saved in /, "") || "the brand";
  // Where a clone goes, said before the paid press (Reed, 5 Nov; #1346's `clone_to`).
  const cloneTo = (a.clone_to || `Saved to ${brand}’s voices`).replace(/^Saved/, "saved");
  const [failedUpload, setFailedUpload] = useState("");
  const go = (body: object, path?: "answer" | "generate" | "cancel" | "uploading") => act.mutate({ path, body }, { onSuccess: () => (setReplying(false), setText(""), setVoiceName(""), setChanging(""), setFailedUpload(""), onDone?.()) });
  const error = act.isError || failedUpload ? <p role="alert" className="text-sm text-danger">{failedUpload || act.error?.message}</p> : null;
  const audition = <VoiceAudition ask={a} who={a.subject || "the presenter"} owner={owner} busy={act.isPending} onPick={(option) => go({ how: "voice", option })} onAgain={() => go({ how: "again" })} />;

  // Folded: answered (by you or the owner), or no longer needed (S4-03).
  if ((a.state === "answered" || a.state === "not_needed") && changing !== "answer") {
    const gone = a.state === "not_needed";
    const [cls, Icon] = HEAD[gone ? "gone" : "done"];
    const ans = a.answer as { name?: string; text?: string; file_id?: number | null; how?: string; reused?: boolean; uses?: string; unused?: string } | null;
    const what = money ? (ans?.how === "withdraw" ? "Withdrawn" : ans?.how === "keep" || ans?.how === "decline" ? "Kept as it is. Nothing was charged for it." : "Approved") : ans?.name ?? ans?.text ?? "";
    const described = ans?.how === "describe" ? `Described: “${ans.text}” · ${ans.uses}’s voice · saved to ${brand}’s voices. Nothing was charged.` : "";
    const who = described ? [described, a.answered_by && a.answered_at && `picked by ${a.answered_by}, ${clock(a.answered_at)}`].filter(Boolean).join(" · ") : ans?.how === "clone" && ans.reused ? `Using ${ans.name ?? "that voice"}, already in ${brand}’s voices. Nothing was charged.` : a.answered_by && a.answered_at ? (a.by_owner ? `${a.answered_by} answered this for you at ${clock(a.answered_at)}. The video carried on.` : [ans?.how === "saved" && a.saved_in, `${money ? "by" : "picked by"} ${a.answered_by}, ${clock(a.answered_at)}`].filter(Boolean).join(" · ")) : ans && "reused" in (ans as object) ? `${a.saved_in}, used again` : "";
    return (
      <section id={`ask-${a.id}`} aria-label={a.question} className="overflow-hidden rounded-lg border border-border bg-surface">
        <p className={`flex items-center gap-2 px-3.5 py-2.5 text-xs font-semibold ${cls}`}>
          <Icon size={14} strokeWidth={1.75} aria-hidden />
          {gone ? "No longer needed" : a.by_owner ? "Answered by the owner" : "Answered"}
          {!gone && !money && a.can.length > 0 && (
            <button type="button" aria-label={`Change your answer: ${a.topic || a.question}`} onClick={() => setChanging("answer")} className="ml-auto font-medium text-muted hover:text-text max-lg:min-h-control">
              Change
            </button>
          )}
        </p>
        <div className="flex items-center gap-3 px-3.5 py-3 text-sm">
          {ans?.file_id != null && !voice && <img src={fileUrl(ans.file_id)} alt="" onError={(e) => (e.currentTarget.hidden = true)} className="h-[54px] w-10 shrink-0 rounded-md object-cover" />}
          <p className="min-w-0">
            {gone ? (
              <>
                <span className="font-medium">{a.question}</span> <span className="text-muted">{a.closed}</span>
              </>
            ) : (
              <>
                <span className="block font-medium">{money ? `${a.question} ${what}` : `${a.topic ? `${a.topic}: ` : ""}${what}`}</span>
                {who && <span className="block text-xs text-muted">{who}</span>}
                {a.money?.since && <span className="block text-xs text-muted">{a.money.since}</span>}
                {ans?.unused && <span className="block text-xs text-warning">{ans.unused}</span>}
              </>
            )}
          </p>
        </div>
        {!gone && a.audition.length > 0 && (
          <div className="flex flex-col gap-2 px-3.5 pb-3 max-lg:px-3">
            {audition}
            {error}
          </div>
        )}
      </section>
    );
  }

  const held = a.state === "held" || (money && a.state === "open" && !owner && !can("make_it"));
  const [cls, Icon] = HEAD[held ? "wait" : "ask"];
  const label = held ? (owner ? "Waiting for your OK" : "Waiting for the owner’s OK") : a.kind === "start" ? (a.money?.updating ? "Updating the plan for your note…" : "Ready to start") : money ? `${a.kind === "budget" ? (a.money?.over && a.money.over !== "the budget" ? "Past this run’s price" : "Past the budget") : a.kind === "own" ? "My own limit" : "Planning"} · needs your OK` : "The director needs you";
  const saved = a.saved ?? [];
  const made = a.options ?? [];
  const chosen = pick ?? (a.state === "ready" ? (made.find((o) => o.file_id != null)?.index ?? null) : a.pick); // ready: the first option, as drawn
  const name = (id: string | number | null) => (typeof id === "number" ? `option ${id + 1}` : saved.find((o) => o.id === id)?.name ?? "");
  const generating = a.state === "generating";

  const doUpload = async (list: FileList | null) => {
    const f = list?.[0];
    if (!f) return;
    setFailedUpload("");
    setUpload({ name: f.name, file: f.type.startsWith("image/") ? URL.createObjectURL(f) : undefined });
    try {
      await act.mutateAsync({ path: "uploading", body: { on: true } });
      const stored = await uploadFile(f);
      await act.mutateAsync({ body: a.kind === "voice" && f.type.startsWith("audio/") ? { how: "clone", file_id: stored.id } : { how: "upload", file_id: stored.id } });
      onDone?.();
    } catch (e) {
      setFailedUpload(e instanceof Error && e.message ? e.message : "The upload didn’t go through. Try again.");
      await act.mutateAsync({ path: "uploading", body: { on: false } }).catch(() => {});
    } finally {
      setUpload(null);
    }
  };
  const input = <input ref={picker} type="file" hidden accept={a.kind === "voice" ? "audio/*" : "image/*,video/*"} onChange={(e) => (void doUpload(e.target.files), (e.target.value = ""))} />;

  let body: ReactNode;
  let foot: ReactNode;
  if (money) {
    const m = a.money!;
    const clips = m.clips.length > 0 && (
      <div className="flex items-end gap-2">
        {m.clips.map((c) => (c.still_file_id != null ? <img key={c.clip} src={fileUrl(c.still_file_id)} alt="" className="h-24 w-[54px] rounded-md object-cover outline outline-[1.5px] outline-offset-1 outline-need-dot" /> : null))}
        <span className="text-xs text-muted">{m.clips.map((c) => `Clip ${c.clip}`).join(" · ")}</span>
      </div>
    );
    body = a.kind === "start" && !held && !m.carry ? <Direction projectId={a.project_id} /> : clips; // the direction card
    foot = held ? (
      <>
        {can("withdraw") && (
          <Button variant="secondary" busy={act.isPending} onClick={() => (onWithdraw ? onWithdraw() : go({ how: "withdraw" }))}>
            Withdraw the request
          </Button>
        )}
        {owner && (
          <Link to="/approvals" className="text-sm text-accent-text underline-offset-2 hover:underline max-lg:inline-flex max-lg:min-h-control max-lg:items-center">
            Answer it in Needs you
          </Link>
        )}
        {!owner && <span className="ml-auto min-w-[120px] flex-1 text-right text-xs text-muted">{`Sent ${clock(m.sent_at)} · you’ll see the answer here`}</span>}
      </>
    ) : a.kind === "start" ? (
      <>
        {can("make_it") && (
          <Button busy={act.isPending} onClick={() => go({ how: "make_it" })}>
            {m.expected ? `Make it · about ${said(m.up_to)}` : `Make it · up to ${said(m.up_to)}`}
          </Button>
        )}
        {onChangePlan && (
          <Button variant="secondary" onClick={onChangePlan}>
            Change the plan first
          </Button>
        )}
        {can("decline") && (
          <Button variant="secondary" busy={act.isPending} onClick={() => go({ how: "decline" })}>
            Decline
          </Button>
        )}
        <span className="ml-auto min-w-[120px] flex-1 text-right text-xs text-muted">No stills or clips are made until you press.</span>
      </>
    ) : (
      <>
        {can("approve") && (
          <Button busy={act.isPending} onClick={() => go({ how: "approve" })}>
            {`Approve · up to ${said(m.up_to)} more`}
          </Button>
        )}
        {can("keep") && (
          <Button variant="secondary" busy={act.isPending} onClick={() => go({ how: "keep" })}>
            {a.kind === "budget" ? "Keep the cut as it is" : a.kind === "plan" ? "Keep the plan" : "Stop here"}
          </Button>
        )}
      </>
    );
  } else if (held) {
    // An editor’s Generate options past their allowance, or clone, waits for the owner (S4-03, flow.md): Withdraw it (the card opens again), or upload instead of options.
    body = <p className="text-[13px]">{voice ? `You asked to clone this voice (up to ${said(a.clone)}, ${cloneTo}). The owner has been asked; nothing is charged while it waits.` : `You asked for 3 generated ${NOUN[a.kind] ?? "options"} (up to ${said(a.generate)}). The owner has been asked; nothing is charged while it waits.`}</p>;
    foot = (
      <>
        {can("cancel") && (
          <Button variant="secondary" busy={act.isPending} onClick={() => go({}, "cancel")}>
            Withdraw
          </Button>
        )}
        {can("upload") && !voice && (
          <Button variant="secondary" icon={Upload} onClick={() => picker.current?.click()}>
            Upload instead
          </Button>
        )}
      </>
    );
  } else if (upload || a.state === "uploading") {
    body = (
      <div className="flex items-center gap-3 rounded-md border border-dashed border-border-strong px-2.5 py-2.5">
        {upload?.file ? <img src={upload.file} alt="" className="size-12 rounded-md object-cover" /> : <Upload size={16} strokeWidth={1.75} aria-hidden />}
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{upload?.name ?? "Your file"}</span>
          <span className="mt-1 block h-1 overflow-hidden rounded-sm bg-surface-3" aria-hidden>
            <i className="block h-full w-1/2 animate-pulse rounded-sm bg-accent" />
          </span>
          <span className="block text-xs text-muted">Uploading · for this video only</span>
        </span>
      </div>
    );
  } else {
    const shown = made.length > 0 && changing !== "options" && a.state !== "failed"; // a failed round shows nothing made
    body = (
      <>
        {voice && audition /* a voice card: its audition first, the brand's voices after */}
        {a.kind === "story" ? (
          <div className="flex gap-2 max-lg:flex-col">
            {a.choices.map((c) => {
              const on = (pick ?? a.pick) === c.key;
              return (
                <button key={c.key} type="button" aria-pressed={on} onClick={() => setPick(c.key)} className={`flex flex-1 flex-col gap-1 rounded-lg border p-3 text-left ${on ? "border-accent-line bg-accent-soft" : "border-border-button"}`}>
                  <span className="text-[11px] font-semibold text-accent-text">{a.pick === c.key ? `${c.key} · my pick` : c.key}</span>
                  <span className="text-sm font-semibold">{c.title}</span>
                  <span className="text-xs text-muted">{c.why}</span>
                </button>
              );
            })}
          </div>
        ) : shown ? (
          <div className="flex flex-col gap-2">
            <p className="text-xs font-semibold text-muted">Made for this video · not saved to the brand</p>
            <div className="flex flex-wrap gap-2">
              {made.map((o) => (
                <Tile key={o.index} file={o.file_id} name={`Option ${o.index + 1}`} note={o.file_id ? undefined : o.state === "failed" ? "didn’t draw" : "drawing…"} drawing={!o.file_id} on={chosen === o.index} onPick={o.file_id ? () => setPick(o.index) : undefined} />
              ))}
            </div>
          </div>
        ) : (
          saved.length > 0 && (a.state !== "failed" || voice) && (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-semibold text-muted">{a.saved_in}</p>
              {a.kind === "voice" ? (
                <div className="flex flex-col gap-1.5">
                  {(every ? saved : saved.filter((o, i) => i < 3 || o.id === chosen)).map((o) => (
                    <VoiceRow key={o.id} o={o} on={chosen === o.id} onPick={() => setPick(o.id)} />
                  ))}
                  {!every && saved.length > 3 && (
                    <button type="button" onClick={() => setEvery(true)} className="self-start text-[13px] font-medium text-accent-text max-lg:min-h-control">
                      {`${saved.length - 3} more voices`}
                    </button>
                  )}
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {saved.map((o) => (
                    <Tile key={o.id} file={o.file_id} name={o.name} note={[o.note && `Saved · ${o.note}`, o.used_in ? `${o.used_in} video${o.used_in === 1 ? "" : "s"}` : ""].filter(Boolean).join(" · ") || "Saved"} on={chosen === o.id} onPick={() => setPick(o.id)} />
                  ))}
                </div>
              )}
            </div>
          )
        )}
        {!voice && audition /* a cast card: who plays them first, then their voice */}
        {a.state === "failed" && (
          <p className="flex items-center gap-2 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">
            <TriangleAlert size={14} strokeWidth={1.75} aria-hidden className="shrink-0" />
            {voice ? ((a.answer as { withdrawn?: boolean } | null)?.withdrawn ? "The clone this card used was withdrawn before it was made. Nothing was charged." : "The voice didn’t clone. Nothing was charged.") : "The picture service made nothing. Nothing was charged."}
          </p>
        )}
        {!shown && (a.state !== "failed" || voice) && !generating && (can("upload") || can("reply") || can("generate") || can("clone")) && (
          <div className="flex flex-col gap-1.5">
            {a.kind === "voice" && <p className="text-xs font-semibold text-muted">Other ways</p>}
            <div className="flex gap-2">
              {can("upload") && a.kind !== "voice" && <Way icon={Upload} title="Upload" note="A photo, a still or a clip" dashed onPress={() => picker.current?.click()} />}
              {can("clone") && <Way icon={Upload} title="Upload a sample" note={`Clone it once · ${cloneTo} · up to ${said(a.clone)}`} dashed onPress={() => picker.current?.click()} />}
              {(can("reply") || can("describe")) && <Way icon={MessageSquare} title={voice ? "Describe it" : "Reply"} note={voice ? "“Late 40s, tired, warm”" : "Tell me in words"} onPress={() => setReplying(true)} />}
              {can("generate") && a.generate && <Way icon={WandSparkles} title="Generate options" note={`3 ${NOUN[a.kind] ?? "options"} · up to ${said(a.generate)} · this video only`} busy={act.isPending} onPress={() => go({}, "generate")} />}
            </div>
          </div>
        )}
        {replying && (
          <form
            className="flex flex-col gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (text.trim()) go(voice ? { how: "describe", text: text.trim(), name: voiceName.trim() } : { how: "reply", text: text.trim() });
            }}
          >
            <label className="sr-only" htmlFor={`reply-${a.id}`}>
              {voice ? "What the voice sounds like" : "Your answer"}
            </label>
            <textarea id={`reply-${a.id}`} rows={2} value={text} onChange={(e) => setText(e.target.value)} autoFocus placeholder={voice ? "Late 40s, tired, warm" : "Tell me in words"} className="resize-none rounded-md border border-border-strong bg-surface px-3 py-2 text-base outline-none focus:border-focus lg:text-sm" />
            {voice && (
              <>
                <input aria-label="Its name (optional)" value={voiceName} onChange={(e) => setVoiceName(e.target.value)} maxLength={120} placeholder="Its name (optional)" className="h-control rounded-md border border-border-strong bg-surface px-3 text-base outline-none focus:border-focus lg:h-9 lg:text-sm" />
                <p className="text-xs text-muted">The nearest app voice reads it, free. It’s saved to {brand}’s voices to use again.</p>
              </>
            )}
            <div className="flex gap-2">
              <Button type="submit" busy={act.isPending} disabled={!text.trim()}>
                {voice ? "Save and use it" : "Send the answer"}
              </Button>
              <Button variant="secondary" onClick={() => setReplying(false)}>
                Not now
              </Button>
            </div>
          </form>
        )}
        {changing === "options" && (
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (text.trim()) go({ change: text.trim() }, "generate");
            }}
          >
            <label className="sr-only" htmlFor={`change-${a.id}`}>
              What should change
            </label>
            <input id={`change-${a.id}`} value={text} onChange={(e) => setText(e.target.value)} autoFocus placeholder="What should change?" className="min-w-0 flex-1 rounded-md border border-border-strong bg-surface px-3 text-base outline-none focus:border-focus max-lg:min-h-control lg:h-9 lg:text-sm" />
            <Button type="submit" busy={act.isPending} disabled={!text.trim()} price={a.generate?.credits ?? null} charge="estimate">
              Make 3 more
            </Button>
          </form>
        )}
      </>
    );
    const madeNow = made.some((o) => o.file_id);
    foot = generating ? (
      <>
        <span className="flex items-center gap-2 text-[13px] text-muted">
          <LoaderCircle size={14} strokeWidth={1.75} aria-hidden className="animate-spin" />
          {voice ? `Cloning the voice · up to ${said(a.clone)}` : `Drawing 3 ${NOUN[a.kind] ?? "options"} · up to ${said(a.generate)}`}
        </span>
        {can("cancel") && !voice && (
          <Button variant="secondary" className="ml-auto" busy={act.isPending} onClick={() => go({}, "cancel")}>
            Cancel
          </Button>
        )}
      </>
    ) : a.state === "failed" && !voice ? (
      <>
        {can("generate") && (
          <Button busy={act.isPending} onClick={() => go({}, "generate")}>
            {`Try again · up to ${said(a.generate)}`}
          </Button>
        )}
        {can("upload") && (
          <Button variant="secondary" icon={Upload} onClick={() => picker.current?.click()}>
            Upload instead
          </Button>
        )}
      </>
    ) : a.kind === "story" ? (
      <>
        {a.choices.map((c, i) => (
          <Button key={c.key} variant={i === 0 ? "primary" : "secondary"} busy={act.isPending} onClick={() => go({ how: "choice", choice: c.key })}>
            {`Go with ${c.key}`}
          </Button>
        ))}
        {a.decide_at && a.pick && <span className="ml-auto text-xs text-muted">{`I’ll go with ${a.pick} at ${clock(a.decide_at)} if I don’t hear back`}</span>}
      </>
    ) : chosen == null && !madeNow ? null : (
      <>
        {chosen != null && (typeof chosen === "number" ? can("option") : can("saved")) && (
          <Button busy={act.isPending} onClick={() => go(typeof chosen === "number" ? { how: "option", option: chosen } : { how: "saved", option: chosen })}>
            {`Use ${name(chosen)}`}
          </Button>
        )}
        {madeNow && typeof chosen === "number" && can("generate") && (
          <Button variant="secondary" icon={RefreshCw} busy={act.isPending} onClick={() => go({ like: chosen }, "generate")}>
            {`More like ${chosen + 1} · up to ${said(a.generate)}`}
          </Button>
        )}
        {madeNow && can("generate") && changing !== "options" && (
          <Button variant="secondary" onClick={() => setChanging("options")}>
            Change something…
          </Button>
        )}
        {madeNow && a.options_spent && a.options_spent.credits > 0 && <span className="ml-auto text-xs text-muted">{`${said(a.options_spent)} spent`}</span>}
      </>
    );
  }

  return (
    <section id={`ask-${a.id}`} aria-label={a.question} className={`overflow-hidden rounded-lg border bg-surface ${held ? "border-[#ecd3a6]" : "border-accent-line shadow-[0_1px_2px_rgb(65_70_184/0.06),0_6px_18px_rgb(65_70_184/0.07)]"}`}>
      {input}
      <p className={`flex items-center gap-2 px-3.5 py-2.5 text-xs font-semibold ${cls}`}>
        <Icon size={14} strokeWidth={1.75} aria-hidden />
        {changing === "answer" ? "Changing your answer · nothing changes until you pick" : label}
        {changing === "answer" && (
          // Change only opens it here (MAIN's Claymation run): the answer stands until another is picked.
          <button type="button" onClick={() => setChanging("")} className="ml-auto font-medium text-muted hover:text-text max-lg:min-h-control">
            Keep my answer
          </button>
        )}
      </p>
      <div className="flex flex-col gap-3 px-3.5 pb-3.5 pt-3 max-lg:px-3">
        <div className="flex flex-col gap-1">
          <h3 className="text-[15px] font-semibold leading-[22px]">{a.question}</h3>
          {a.why && !(held && !money) && <p className="text-[13px] text-muted">{a.why}</p>}
        </div>
        {body}
        {error}
      </div>
      {foot && <div className="flex flex-wrap items-center gap-2 border-t border-border px-3.5 py-2.5 max-lg:px-3">{foot}</div>}
    </section>
  );
}

/** The pinned bar above the message box (S3-05, S4-03, P-06): how many questions wait and, beside the panel, which; Show jumps to the next. */
export function WaitingBar({ waiting }: { waiting: { id: number; topic: string; question: string }[] }) {
  const [at, setAt] = useState(0);
  const rail = useRail(); // a phone shows the count only (P-06)
  if (!waiting.length) return null;
  const next = () => {
    const card = waiting[at % waiting.length];
    document.getElementById(`ask-${card.id}`)?.scrollIntoView?.({ block: "center", behavior: "smooth" });
    setAt(at + 1);
  };
  return (
    <div className="mx-5 mb-2 flex items-center gap-2 rounded-lg border border-accent-line bg-accent-soft px-2.5 py-1.5 text-[13px] font-medium text-accent-text max-lg:mx-3">
      <CircleHelp size={14} strokeWidth={1.75} aria-hidden className="shrink-0" />
      <span className="min-w-0 truncate">{[`${waiting.length} question${waiting.length === 1 ? "" : "s"} waiting`, ...(rail ? waiting.map((w) => w.topic).filter(Boolean) : [])].join(" · ")}</span>
      <button type="button" onClick={next} className="ml-auto shrink-0 font-semibold max-lg:min-h-control">
        {waiting.length > 1 ? "Next" : "Show"}
      </button>
    </div>
  );
}

export const isOpen = (a: Ask) => OPEN.includes(a.state);

/** A freestyle's send held for the owner before its video has cards (an editor's first send, or a change after a delivery):
 *  the same held card (S3-07, P-07), its "up to" in credits, with Withdraw the request; the owner answers it in Needs you. */
export function HeldSend({ projectId, change, upTo, sentAt, owner, onWithdraw }: { projectId: number; change: boolean; upTo: number | null | undefined; sentAt: string; owner: boolean; onWithdraw: () => void }) {
  const price = { credits: upTo ?? 0, usd: null };
  const ask: Ask = {
    id: 0, project_id: projectId, kind: "start", topic: "", subject: "", state: "held", by_owner: false, clone_to: "", created_at: sentAt, can: owner ? [] : ["withdraw"], answered_by: "", saved_in: "", closed: "", choices: [], saved: [], options: [], audition: [], voice_name: "", voice_saved: false, audition_failed: false, other_voices: [],
    question: `${change ? "Make this change" : "Make it"}${upTo ? ` for up to ${said(price)}` : ""}?`,
    why: change ? "The owner has been asked. The cut stays as it is; no generation starts until they say yes." : "The owner has been asked. No generation starts until they say yes.",
    money: { up_to: price, clips: [], making: [], sent_at: sentAt, held: "", since: "", updating: false, carry: false, what: "", over: "the budget", expected: false },
  };
  return <AskCard ask={ask} owner={owner} onWithdraw={onWithdraw} />;
}
