import { useEffect, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Ellipsis, Pause, Play, RefreshCw, Lock, LockOpen, MapPin, Merge, MessageSquare, SlidersHorizontal, Trash2, Upload, UserRound, Users, WandSparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl, uploadFile } from "../api/upload";
import { Button, Dot, Menu, MenuItem, Skeleton, TextArea, useToast, type Tone } from "../components";
import { refreshJobs } from "../jobs/refresh";
import { useFrames } from "../projects/useProgress";
import { lookFitNote, useSheetPrice } from "../library/sheets";
import { RoleTextFit } from "../projects/RoleTextFit";
import { MergeRole, mergedText } from "../projects/MergeRole";
import { useBrands } from "../shell/useBrands";
import { useMedia } from "../useMedia";
import { Empty } from "../videos/Empty";
import { useLocks } from "../videos/locks";
import { spent, upTo } from "../videos/money";
import type { PaneProps } from "../videos/Preview";
import { approveCast, keepOld, makePlace, pickPlace, uploadPlace, useCast, type Cast, type CastItem } from "./gate";
import { Presenter } from "./Presenter";
import { notInShots, useAssets } from "./useAssets";

type Asset = components["schemas"]["AssetOut"];
const NO_LOCKS: components["schemas"]["LocksIO"] = { locks: { cast: false, look: false, length: false, song: false, screens: [], roles: [] }, outfits: {} };
type Pair = components["schemas"]["SamePair"];
type State = { tone: Tone; word: string; hollow?: boolean };

const clipNo = (id: string) => Number(id.replace(/^c/i, ""));
/** "Clips 2–4", "Clip 3", "Clips 2, 5 and 7". */
export function clipsText(ids: string[]) {
  const n = ids.map(clipNo).filter((x) => !Number.isNaN(x)).sort((a, b) => a - b);
  if (n.length === 0) return "";
  if (n.length === 1) return `Clip ${n[0]}`;
  if (n.every((x, i) => i === 0 || x === n[i - 1] + 1)) return `Clips ${n[0]}–${n.at(-1)}`;
  return `Clips ${n.slice(0, -1).join(", ")} and ${n.at(-1)}`;
}
const pronoun = (a: Asset) => {
  const g = (a.facts?.gender?.value ?? "").toLowerCase();
  return /\b(female|woman|girl)\b/.test(g) ? "her" : /\b(male|man|boy)\b/.test(g) ? "him" : "them";
};

/** Where an item stands against the combined OK (S-gaps-07 B as redrawn): ready to check, changed since the OK, or
 *  approved; null while it isn't ready (its card says why). */
function gateState(ci: CastItem | undefined): State | null {
  if (!ci || ci.readiness !== "ready") return null;
  if (ci.approval === "approved") return { tone: "success", word: "Approved" };
  if (ci.approval === "changed") return { tone: "warning", word: "Changed · needs your OK" };
  return { tone: "warning", word: "Ready to check", hollow: true };
}

/** Where its look came from, as a tag (S-gaps-07 A): the brand's library, an upload, made for this video or script. */
function sourceTag(ci: CastItem | undefined, brand: string, phone: boolean, saved?: string) {
  if (!ci?.source) return null;
  if (ci.source === "library") return phone ? `${brand}’s library` : `From ${brand}’s library · “${saved || ci.name}”${ci.version ? ` v${ci.version}` : ""}`;
  if (ci.source === "uploaded") return phone ? "Uploaded" : "Uploaded for this video";
  if (ci.made_by === "director") return phone ? "By the director · chat" : `Made by the director in the chat${ci.made_at ? ` · ${hhmm(ci.made_at)}` : ""}`;
  return ci.source === "script" ? "Made for this script" : "Made for this video";
}

const hhmm = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });

/** "Revised 09:21 after your note · was ▣" (S-gaps-07 B): a look redrawn since it was first shown, with the one before. */
function Revised({ ci, phone }: { ci: CastItem | undefined; phone: boolean }) {
  if (!ci?.revised_at) return null;
  return (
    <>
      <Tag tone="accent">{phone ? "Revised" : `Revised ${hhmm(ci.revised_at)}${ci.revised_why ? " after your note" : ""}`}</Tag>
      {!phone && ci.was_preview_file_id != null && (
        <span className="inline-flex items-center gap-1 text-xs text-muted">
          was <img src={fileUrl(ci.was_preview_file_id)} alt="The look before" className="h-6 w-4 rounded-[2px] object-cover" />
        </span>
      )}
    </>
  );
}

/** A sample that plays in place (a voice's free sample). */
function PlaySample({ url, label }: { url: string; label: string }) {
  const [on, setOn] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  useEffect(() => () => audio.current?.pause(), []);
  const src = /^https?:/.test(url) ? url : `/api${url}`;
  return (
    <button type="button" aria-label={`${on ? "Stop" : "Play"} ${label}`} onClick={() => {
        audio.current ??= Object.assign(new Audio(src), { onended: () => setOn(false), onerror: () => setOn(false) });
        if (on) audio.current.pause();
        else void audio.current.play().catch(() => setOn(false)); // a sample that won't play stops showing as playing
        setOn(!on);
      }} className="inline-grid size-6 place-items-center rounded-md border border-border bg-surface text-muted max-lg:size-11">
      {on ? <Pause size={12} strokeWidth={1.75} aria-hidden /> : <Play size={12} strokeWidth={1.75} aria-hidden />}
    </button>
  );
}

/** "Voice changed: Sarah → Roger ▶" (Reed, 4 Nov): a character's new voice is a change the combined OK covers; it says what
 *  changed, with the new voice's sample when there is one. */
function VoiceChange({ ci }: { ci: CastItem | undefined }) {
  if (!ci || ci.approval !== "changed") return null;
  const what = ci.changes ?? [];
  const voice = (what.includes("voice") || (!ci.changes && ci.was_voice)) && ci.voice;
  const other = [what.includes("look") && "look", what.includes("words") && "words"].filter(Boolean).join(" and ");
  return (
    <>
      {other && <span className="text-sm text-warning">{other[0].toUpperCase() + other.slice(1)} changed</span>}
      {voice && (
        <span className="inline-flex flex-wrap items-center gap-1.5 text-sm text-warning">
          Voice changed: {ci.was_voice ? `${ci.was_voice.name} → ` : ""}
          {ci.voice!.name}
          {ci.voice!.sample_url && <PlaySample url={ci.voice!.sample_url} label={`${ci.voice!.name}’s voice`} />}
        </span>
      )}
    </>
  );
}

const Tag = ({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "warning" | "accent" }) => (
  <span className={`inline-flex h-5 items-center rounded-[4px] px-1.5 text-[11px] font-semibold ${tone === "warning" ? "bg-warning-soft text-warning" : tone === "accent" ? "bg-accent-soft text-accent-text" : "bg-surface-2 text-muted"}`}>{children}</span>
);

/** Where the role stands, in words with a dot (S5-01, S5-03). */
function stateOf(a: Asset, lockedHere: boolean): State {
  if (a.locked || lockedHere) return { tone: "success", word: "Locked" };
  if (needsLook(a)) return { tone: "warning", word: "Needs a look" };
  if (a.sheet_status === "drawing") return { tone: "accent", word: "Drawing" };
  if (a.sheet_status === "waiting_for_owner") return { tone: "warning", word: "Waiting for the owner", hollow: true };
  if (a.sheet_status === "needs_approval") return a.only_here != null || a.look_copy_id != null ? { tone: "warning", word: "Ready to check", hollow: true } : { tone: "warning", word: "Waiting for its OK in the library" };
  return { tone: "success", word: "Approved" };
}
const own = (a: Asset) => a.only_here != null && a.own_look_id === a.library_item_id;
const copyFailed = (a: Asset) => a.look_copy_id != null && (a.sheet_status === "none" || a.sheet_status === "missing");
function needsLook(a: Asset) {
  if (a.locked) return false;
  if (a.library_deleted) return true;
  if (a.slot_id != null && a.library_item_id == null) return true;
  if (a.look_needed && a.look_copy_id == null) return true;
  return copyFailed(a) || ((a.sheet_status === "none" || a.sheet_status === "missing") && a.kind === "character");
}

function Status({ s }: { s: State }) {
  const colour = s.tone === "success" ? "text-success" : s.tone === "warning" ? "text-warning" : s.tone === "accent" ? "text-accent-text" : "text-muted";
  return (
    <span className={`shrink-0 text-xs font-medium ${colour}`}>
      <Dot tone={s.tone} hollow={s.hollow}>
        {s.word}
      </Dot>
    </span>
  );
}

/** A press with its price after the label, as the boards write it ("Make a look · up to $0.08"). */
function Priced({ label, price, ...rest }: { label: string; price: string | null } & Omit<Parameters<typeof Button>[0], "children" | "price" | "charge">) {
  return (
    <Button variant="secondary" {...rest}>
      {label}
      {price && (
        <>
          {" "}
          <span className="font-normal text-muted">· {price}</span>
        </>
      )}
    </Button>
  );
}

/** The role's picture: its sheet, the picture someone gave for it, three frames while it's drawn, or an empty frame. */
function Picture({ a, wide, phone }: { a: Asset; wide?: boolean; phone?: boolean }) {
  const size = phone ? "h-20 w-[60px]" : wide ? "h-[100px] w-[150px]" : "h-[118px] w-[88px]";
  const file = a.sheet_file_id ?? a.photo_file_id ?? (a.kind !== "character" ? a.file_id : null);
  if (a.sheet_status === "drawing" && !phone)
    return (
      <div aria-hidden className={`flex shrink-0 gap-1 ${wide ? "w-[150px]" : ""}`}>
        {[0, 1, 2].map((i) => (
          <span key={i} className={`${wide ? "h-[100px] flex-1" : "h-[118px] w-[42px]"} animate-pulse rounded-md bg-surface-3 motion-reduce:animate-none`} />
        ))}
      </div>
    );
  if (file && (!needsLook(a) || (a.photo_file_id && !a.sheet_file_id))) return <img src={fileUrl(file)} alt={`${a.role || a.name}’s look`} className={`${size} shrink-0 rounded-md bg-black object-cover`} />;
  const Icon = a.kind === "place" ? MapPin : UserRound;
  return (
    <span aria-hidden className={`${size} grid shrink-0 place-items-center rounded-md border border-dashed border-border-strong bg-surface-2`}>
      {!phone && <Icon size={20} strokeWidth={1.75} className="text-warning" />}
    </span>
  );
}

type Ctx = {
  projectId: number;
  brandId: number;
  brand: string;
  head: PaneProps["head"];
  total: number; // the video's clips ("in 9 of 9 clips")
  characters: components["schemas"]["ItemOut"][];
  roles: string[]; // the roles locked in this video
  outfits: Record<string, string>;
  /** Saves one change on the newest locks read (never an older render's), once it has loaded. */
  setLocks: (change: (now: components["schemas"]["LocksIO"]) => components["schemas"]["LocksIO"]) => Promise<unknown>;
  locksReady: boolean;
  all: Asset[]; // every role, for Merge into…
  gate: (a: Asset) => CastItem | undefined; // the checkpoint's view of a card's item (#1331); none on a server without it
  hasGate: boolean; // the checkpoint's routes are on the server (a place's Pick, Upload and Make one use them)
  refresh: () => Promise<unknown>;
  phone: boolean;
};

/** "Main character · in 9 of 9 clips" beside the name. */
function where(a: Asset, total: number) {
  const n = a.clip_ids.length;
  const part = n > 0 ? (total > 0 && n === total ? `in ${n} of ${total} clips` : `in ${n} clip${n === 1 ? "" : "s"}`) : a.shots > 0 ? `in ${a.shots} shot${a.shots === 1 ? "" : "s"}` : "";
  return [a.description.split(",")[0].trim(), part].filter(Boolean).join(" · ");
}

/** Where its look came from, or what it waits for (S5-01, S5-03). */
function source(a: Asset, c: Ctx, outfit: string) {
  const saved = `Saved in ${c.brand}: “${a.name}”${a.library_version ? ` v${a.library_version}` : ""}`;
  if (a.locked) return `${saved}${c.phone ? "" : " · used as is in every shot"}`;
  if (a.library_deleted) return "Its saved character was deleted from Cast & places.";
  if (needsLook(a)) {
    if (copyFailed(a)) return "The look didn't finish. Nothing was charged.";
    if (a.look_needed) return `${saved}, drawn in another style. This video needs a ${a.look_needed} look.`;
    if (a.photo_file_id) return "Your picture, for this video only. Its look is drawn from it.";
    const waits = clipsText(a.clip_ids);
    return `No sheet yet.${waits ? ` ${waits} wait${a.clip_ids.length === 1 ? "s" : ""} for ${pronoun(a)}.` : ""}`;
  }
  if (a.sheet_status === "drawing") return `Drawing a front, side and back sheet${a.look_credits != null ? ` · ${upTo(c.head, a.look_credits)}` : ""} · about 30 s`;
  if (a.sheet_status === "waiting_for_owner") return "Its look waits for the owner’s OK on the price.";
  if (outfit) return `Outfit for this video: ${outfit}. The sheet still sets the face.`;
  if (a.only_here) return `${a.photo_file_id ? "Your picture, drawn as a look" : "Look made"} for this ${a.only_here} · not in the library`;
  if (a.look_copy_id != null) return `This video’s own ${a.look_needed ?? ""} look of “${a.name}”`.replace("  ", " ");
  return saved;
}

/** One role (S5-01, S5-03): its picture, where it came from, its state and the presses that move it on. */
function RoleCard({ a, c }: { a: Asset; c: Ctx }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { model, price: sheet } = useSheetPrice();
  const file = useRef<HTMLInputElement>(null);
  const [changing, setChanging] = useState<string | null>(null);
  const [dressing, setDressing] = useState<string | null>(null);
  const slot = a.slot_id;
  const ref = `slot:${slot}`;
  const lockedHere = slot != null && c.roles.includes(ref);
  const item = a.look_copy_id ?? a.library_item_id;
  const outfitKey = `char:${a.library_item_id}`;
  const outfit = c.outfits[outfitKey] ?? "";
  const ownLook = own(a) || a.look_copy_id != null;
  const ci = c.gate(a);
  const s = gateState(ci) ?? stateOf(a, lockedHere);
  const [picking, setPicking] = useState(false);
  const look = a.look_credits ?? sheet ?? null;
  const price = look == null ? null : upTo(c.head, look);
  const path = { project_id: c.projectId, slot_id: slot ?? 0 };
  const done = async () => {
    await refreshJobs(queryClient);
    await c.refresh();
  };
  const run = useMutation({ mutationFn: (f: () => Promise<unknown>) => f(), onSuccess: done, onError: (e: Error) => toast(e.message, undefined, "error") });
  const go = (f: () => Promise<unknown>) => run.mutate(f);
  // The frames follow the new cast for free; stills of the old look are redrawn when the video can pay, and that is said.
  const pick = (id: number) =>
    go(async () => {
      await must(api.PUT("/projects/{project_id}/assets/slots/{slot_id}", { params: { path }, body: { library_item_id: id } }));
      const video = await queryClient.fetchQuery({ queryKey: ["project", c.projectId], staleTime: 0, queryFn: async () => (await api.GET("/projects/{project_id}", { params: { path: { project_id: c.projectId } } })).data ?? null });
      const redrew = (video?.cast_redraw as { redrawn_for_cast?: { count: number; credits: number } } | null | undefined)?.redrawn_for_cast;
      if (redrew) toast(`Redrew ${redrew.count} still${redrew.count === 1 ? "" : "s"} for the new cast · ${spent(c.head, redrew.credits)}.`);
    });
  const makeLook = () =>
    go(async () => {
      if (a.look_needed && a.library_item_id != null && a.look_copy_id == null)
        return must(api.POST("/projects/{project_id}/assets/looks/{item_id}/copy", { params: { path: { project_id: c.projectId, item_id: a.library_item_id } } }));
      if ((a.photo_file_id || copyFailed(a)) && item != null)
        return must(api.POST("/library/{kind}/{item_id}/sheet", { params: { path: { kind: "character", item_id: item } }, body: { model_id: model, change: "" } }));
      return must(api.POST("/projects/{project_id}/assets/slots/{slot_id}/make-look", { params: { path } }));
    });
  const upload = (f: File) =>
    go(async () => {
      const stored = await uploadFile(f);
      return must(api.POST("/projects/{project_id}/assets/slots/{slot_id}/upload", { params: { path }, body: { file_id: stored.id } }));
    });
  // Change…: a look made for this video is drawn again from the note (priced); any other is asked of the director in the
  // chat (free), who changes it in Cast, where the combined OK covers it again (S-gaps-07 B).
  const change = (note: string) =>
    go(async () => {
      if (ownLook && item != null) await must(api.POST("/library/{kind}/{item_id}/sheet", { params: { path: { kind: "character", item_id: item } }, body: { model_id: model, change: note } }));
      else await must(api.POST("/projects/{project_id}/director/messages", { params: { path: { project_id: c.projectId } }, body: { text: `${a.role || a.name}: ${note}` } }));
      setChanging(null);
      if (!ownLook) toast(`Asked the director: “${note}”.`);
    });
  const cancel = () => go(() => must(api.POST("/jobs/{job_id}/cancel", { params: { path: { job_id: a.drawing_job_id! } } })));
  // Locks and outfits are the video's own choices; an outfit changes what the cast OK covers, so the set is read again.
  const lock = (on: boolean) =>
    void c.setLocks((now) => ({ ...now, locks: { ...now.locks, roles: on ? [...(now.locks.roles ?? []).filter((r) => r !== ref), ref] : (now.locks.roles ?? []).filter((r) => r !== ref) } })).then(() => (toast(on ? `${a.role}’s look is locked in this video.` : `${a.role}’s look is unlocked.`), c.refresh()), () => null);
  const unlockScript = () => go(() => must(api.DELETE("/projects/{project_id}/assets/slots/{slot_id}/script-lock", { params: { path } })));
  const dress = (text: string) => void c.setLocks((now) => ({ ...now, outfits: { ...now.outfits, [outfitKey]: text } })).then(() => (setDressing(null), c.refresh()), () => null);
  const others = c.characters.filter((x) => x.id !== a.library_item_id);
  const pickMenu = (label: string, primary: boolean) => (
    <Menu
      title={`Pick from ${c.brand}’s cast`}
      trigger={(t) => (
        <Button variant={primary ? "primary" : "secondary"} icon={Users} disabled={others.length === 0} reason={others.length === 0 ? `${c.brand} has no saved characters yet.` : undefined} {...t}>
          {label}
        </Button>
      )}
    >
      {(close) =>
        others.map((x) => (
          <MenuItem key={x.id} onClick={() => (close(), pick(x.id))}>
            {x.sheet_file_id ? <img src={fileUrl(x.sheet_file_id)} alt="" className="h-10 w-8 shrink-0 rounded-sm object-cover" /> : <span aria-hidden className="h-10 w-8 shrink-0 rounded-sm bg-surface-2" />}
            <span className="min-w-0 flex-1 truncate">{x.name}</span>
            <span className="text-xs text-muted">{x.sheet_status !== "approved" ? "needs a look" : `in ${x.used_in_count} video${x.used_in_count === 1 ? "" : "s"}`}</span>
          </MenuItem>
        ))
      }
    </Menu>
  );
  const uploadButton = (
    <>
      <input ref={file} type="file" accept="image/*" className="hidden" aria-label={`Upload a picture for ${a.role}`} onChange={(e) => (e.target.files?.[0] && upload(e.target.files[0]), (e.target.value = ""))} />
      <Button variant="secondary" icon={Upload} onClick={() => file.current?.click()}>
        Upload
      </Button>
    </>
  );
  // Its look lives in Cast & places (a saved character, or one the shots use with no role): made and approved there.
  const inLibrary = a.library_item_id != null && (
    <Link to={`/b/${c.brandId}/library/characters/${a.library_item_id}`} className="inline-flex min-h-control items-center gap-2 rounded-md border border-border-button px-3 text-sm font-medium hover:bg-surface-2 lg:min-h-control-dense">
      <Users size={16} strokeWidth={1.75} aria-hidden />
      {a.sheet_status === "needs_approval" ? "Approve it in Cast & places" : "Make its look in Cast & places"}
    </Link>
  );
  let actions: ReactNode = null;
  if (slot == null && !a.locked)
    // A character the shots use with no role in the script: Make a look only for its own copy in this style (ST2).
    actions = a.look_needed && a.look_copy_id == null ? <Priced icon={WandSparkles} label={`Make a ${a.look_needed} look`} price={price} busy={look == null} onClick={makeLook} /> : a.sheet_status !== "approved" ? inLibrary : null;
  else if (needsLook(a))
    actions = (
      <>
        {!copyFailed(a) && pickMenu(c.phone ? "Library" : `From ${c.brand}’s library`, true)}
        {!copyFailed(a) && !a.look_needed && uploadButton}
        <Priced icon={WandSparkles} label={copyFailed(a) ? "Try again" : a.look_needed ? `Make a ${a.look_needed} look` : c.phone ? "Make" : "Make one"} price={price} busy={look == null} onClick={makeLook} />
      </>
    );
  else if (a.sheet_status === "drawing" || a.sheet_status === "waiting_for_owner")
    actions = (
      <>
        {a.drawing_job_id && (
          <Button variant="secondary" onClick={cancel}>
            Cancel
          </Button>
        )}
        {a.sheet_status === "waiting_for_owner" && others.length > 0 && pickMenu(c.phone ? "Pick saved" : `Pick from ${c.brand}’s cast`, false)}
      </>
    );
  else if (a.sheet_status === "needs_approval" && !ownLook) actions = inLibrary;
  // No OK on the card (Reed, S-gaps-07 B): ask for changes here; the whole cast and places are approved together above.
  // Ready or approved (S-gaps-07 as redrawn): ask for a change here; the rest is under More. The whole set is approved
  // together above, never on a card.
  else if ((a.sheet_status === "needs_approval" || a.sheet_status === "approved") && !a.locked && !lockedHere)
    actions = (
      <Button variant="ghost" icon={MessageSquare} onClick={() => setChanging(a.look_fit?.problem ?? "")}>
        Change…
      </Button>
    );
  // Merge into another role (this video only, with a preview and Undo), and Delete a look of its own it no longer uses.
  const [merging, setMerging] = useState(false);
  const mates = c.all.filter((r) => r.slot_id != null && r.slot_id !== slot);
  const unused = a.own_look_id != null && a.own_look_id !== a.library_item_id && !a.locked;
  const remove = () =>
    go(async () => {
      await must(api.DELETE("/library/{kind}/{item_id}", { params: { path: { kind: "character", item_id: a.own_look_id! } } }));
      toast(`Deleted ${a.role}’s own look.`, () => void must(api.POST("/library/{kind}/{item_id}/unarchive", { params: { path: { kind: "character", item_id: a.own_look_id! } } })).then(done));
    });
  const settled = a.sheet_status === "approved" || a.sheet_status === "needs_approval";
  const more = slot != null && settled && (
    <Menu title={`More for ${a.role}`} align="right" trigger={(t) => <Button variant="ghost" dense icon={Ellipsis} aria-label={`More for ${a.role}`} {...t} />}>
      {(close) => (
        <>
          {a.locked && a.script_unlock && (
            <MenuItem onClick={() => (close(), unlockScript())}>
              <LockOpen size={20} strokeWidth={1.75} aria-hidden />
              Unlock on the script
            </MenuItem>
          )}
          {!a.locked && a.sheet_status === "approved" && (
            <MenuItem disabled={!c.locksReady} onClick={() => (close(), lock(!lockedHere))}>
              {lockedHere ? <LockOpen size={20} strokeWidth={1.75} aria-hidden /> : <Lock size={20} strokeWidth={1.75} aria-hidden />}
              {lockedHere ? "Unlock" : "Lock in this video"}
            </MenuItem>
          )}
          {!a.locked && !lockedHere && (
            <MenuItem disabled={!c.locksReady} onClick={() => (close(), setDressing(outfit))}>
              <SlidersHorizontal size={20} strokeWidth={1.75} aria-hidden />
              {outfit ? "Change the outfit for this video" : "Outfit for this video"}
            </MenuItem>
          )}
          {!a.locked && !lockedHere && outfit && (
            <MenuItem onClick={() => (close(), dress(""))}>
              <SlidersHorizontal size={20} strokeWidth={1.75} aria-hidden />
              Use the sheet’s outfit
            </MenuItem>
          )}
          {!a.locked && !lockedHere && others.length > 0 && (
            <MenuItem onClick={() => (close(), setPicking(true))}>
              <Users size={20} strokeWidth={1.75} aria-hidden />
              Pick another from {c.brand}’s library
            </MenuItem>
          )}
          {!a.locked && a.own_look_id != null && a.own_look_id !== a.library_item_id && (
            <MenuItem onClick={() => (close(), pick(a.own_look_id!))}>
              <Users size={20} strokeWidth={1.75} aria-hidden />
              Use its own look again
            </MenuItem>
          )}
          {!a.locked && mates.length > 0 && (
            <MenuItem onClick={() => (close(), setMerging(true))}>
              <Merge size={20} strokeWidth={1.75} aria-hidden />
              Merge into…
            </MenuItem>
          )}
          {unused && (
            <MenuItem danger onClick={() => (close(), remove())}>
              <Trash2 size={20} strokeWidth={1.75} aria-hidden />
              Delete its own look
            </MenuItem>
          )}
        </>
      )}
    </Menu>
  );
  const facts = (r: Asset) => [r.facts?.age_range, r.facts?.gender, r.facts?.occupation].map((f) => f?.value).filter(Boolean).join(" · ");
  const mergeDialog = merging && slot != null && (
    <MergeRole
      role={a.role}
      roleId={slot}
      videoOnly
      others={mates.map((r) => ({ id: r.slot_id!, role: r.role, kind: "", locked: r.locked, facts: facts(r) }))}
      adapter={{
        preview: async (into) => {
          const data = (await must(api.GET("/projects/{project_id}/assets/slots/{slot_id}/merge/preview", { params: { path, query: { into } } }))).data!;
          return { ...data.moved, look_unused: data.look_unused };
        },
        merge: async (into) => {
          const data = (await must(api.POST("/projects/{project_id}/assets/slots/{slot_id}/merge", { params: { path }, body: { into_slot_id: into } }))).data!;
          await c.refresh();
          return { ...data.moved, look_unused: data.look_unused, token: data.token };
        },
      }}
      onMerged={(into, m) => {
        setMerging(false);
        toast(mergedText(into.role, m), () => void must(api.POST("/projects/{project_id}/assets/merge/undo", { params: { path: { project_id: c.projectId } }, body: { token: m.token! } })).then(c.refresh, (e: Error) => toast(e.message, undefined, "error")));
      }}
      onClose={() => setMerging(false)}
    />
  );
  const need = s.word === "Needs a look";
  return (
    <section id={slot != null ? `role-${slot}` : undefined} aria-label={a.role || a.name} className={`flex flex-wrap gap-3.5 rounded-lg border p-3 ${need ? "border-[#ecd3a6] bg-[#fffdf8]" : "border-border bg-surface"}`}>
      <Picture a={a} phone={c.phone} />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        {c.phone ? (
          <div className="flex flex-col gap-1">
            <span className="font-semibold">{a.role || a.name}</span>
            {need && a.clip_ids.length ? <span className="text-xs text-muted">{`${clipsText(a.clip_ids)} wait${a.clip_ids.length === 1 ? "s" : ""} for ${pronoun(a)}`}</span> : sourceTag(ci, c.brand, true) ? <span className="flex flex-wrap gap-1"><Tag>{sourceTag(ci, c.brand, true)}</Tag><Revised ci={ci} phone /><VoiceChange ci={ci} /></span> : <span className="text-xs text-muted">{a.locked ? `Saved in ${c.brand}` : a.only_here ? "Look for this video" : `Saved in ${c.brand}`}</span>}
            <Status s={s} />
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-semibold">{a.role || a.name}</span>
              <span className="text-sm text-muted">{where(a, c.total)}</span>
              <span className="flex-1" />
              <Status s={s} />
            </div>
            {(sourceTag(ci, c.brand, false, a.name) || a.locked || lockedHere || ci?.revised_at || ci?.approval === "changed") && (
              <div className="flex flex-wrap items-center gap-1.5">
                {sourceTag(ci, c.brand, false, a.name) && <Tag>{sourceTag(ci, c.brand, false, a.name)}</Tag>}
                <Revised ci={ci} phone={false} />
                <VoiceChange ci={ci} />
                {a.locked && <Tag>Locked on the script</Tag>}
                {lockedHere && <Tag>Locked in this video</Tag>}
              </div>
            )}
            {(!ci || needsLook(a) || outfit || a.sheet_status !== "approved") && !(ci && ci.readiness === "ready" && !outfit) && <p className="text-sm text-muted">{source(a, c, outfit)}</p>}
          </>
        )}
        {a.look_fit && !a.locked && <p className="text-sm text-warning">{lookFitNote(a.look_fit)}</p>}
        {changing !== null ? (
          <div className="flex flex-col gap-2">
            <TextArea label={`Change ${a.role || a.name}…`} rows={2} maxLength={500} placeholder="What should change?" value={changing} onChange={(e) => setChanging(e.target.value)} />
            <div className="flex flex-wrap gap-2">
              {ownLook ? (
                <Priced icon={WandSparkles} label="Change it" price={price} busy={run.isPending} disabled={!changing.trim()} reason={changing.trim() ? null : "Say what should change"} onClick={() => change(changing.trim())} />
              ) : (
                <Button variant="secondary" icon={MessageSquare} busy={run.isPending} disabled={!changing.trim()} reason={changing.trim() ? "Asking is free. The director shows any price before it makes a new look, and the cast and places are approved again together." : "Say what should change"} onClick={() => change(changing.trim())}>
                  Ask the director
                </Button>
              )}
              <Button variant="ghost" onClick={() => setChanging(null)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : picking ? (
          <div className="flex flex-wrap items-center gap-2">
            {pickMenu(`Pick from ${c.brand}’s library`, true)}
            <Button variant="ghost" onClick={() => setPicking(false)}>
              Cancel
            </Button>
          </div>
        ) : dressing !== null ? (
          <form className="flex flex-col gap-2" onSubmit={(e) => (e.preventDefault(), dress(dressing.trim()))}>
            <TextArea label={`${a.role}’s outfit for this video`} rows={2} maxLength={200} placeholder="Rain-soaked green hoodie, grey joggers" value={dressing} onChange={(e) => setDressing(e.target.value)} />
            <div className="flex flex-wrap gap-2">
              <Button type="submit" variant="secondary" busy={run.isPending} disabled={!dressing.trim()}>
                Save the outfit
              </Button>
              <Button variant="ghost" onClick={() => setDressing(null)}>
                Cancel
              </Button>
            </div>
          </form>
        ) : (
          (actions || more) && (
            <div className="flex flex-wrap items-center gap-2">
              {actions}
              {more}
            </div>
          )
        )}
        {mergeDialog}
      </div>
      {/* Its own row under the picture and the words: the card's full width on a phone (QA-2 on #720). */}
      {a.text_fit && slot != null && !a.locked && (
        <div className="basis-full">
          <RoleTextFit key={a.text_fit.description} asset={a} projectId={c.projectId} stopFor={() => null} onDone={c.refresh} />
        </div>
      )}
    </section>
  );
}

/** Two roles that may be one person (S5-01 "Mom · Mom (kitchen)"): one press merges, with Undo; or keep them two. */
function PairCard({ pair, rows, c }: { pair: Pair; rows: Asset[]; c: Ctx }) {
  const toast = useToast();
  const into = rows.find((r) => r.slot_id === pair.into_slot_id)!;
  const other = rows.find((r) => r.slot_id !== pair.into_slot_id)!;
  const path = { project_id: c.projectId };
  const merge = useMutation({
    mutationFn: () => must(api.POST("/projects/{project_id}/assets/slots/{slot_id}/merge", { params: { path: { ...path, slot_id: other.slot_id! } }, body: { into_slot_id: into.slot_id! } })).then((r) => r.data!),
    onSuccess: async (m) => {
      await c.refresh();
      toast(mergedText(into.role, { ...m.moved, look_unused: m.look_unused }), () => void must(api.POST("/projects/{project_id}/assets/merge/undo", { params: { path }, body: { token: m.token } })).then(c.refresh, (e: Error) => toast(e.message, undefined, "error")));
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const body = { a_slot_id: pair.a_slot_id, b_slot_id: pair.b_slot_id };
  const apart = useMutation({
    mutationFn: () => must(api.POST("/projects/{project_id}/assets/maybe-same/dismiss", { params: { path }, body })),
    onSuccess: async () => {
      await c.refresh();
      toast("Kept as two roles.", () => void must(api.DELETE("/projects/{project_id}/assets/maybe-same/dismiss", { params: { path }, body })).then(c.refresh));
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const each = into.clip_ids.length === 1 && other.clip_ids.length === 1 ? "In 1 clip each" : `In ${into.clip_ids.length} and ${other.clip_ids.length} clips`;
  return (
    <section aria-label={`${into.role} and ${other.role}`} className="flex gap-3.5 rounded-lg border border-border bg-surface p-3">
      <div className="flex shrink-0 gap-1">
        {[into, other].map((r) => {
          const f = r.sheet_file_id ?? r.photo_file_id;
          return f ? <img key={r.ref} src={fileUrl(f)} alt="" className={`${c.phone ? "h-20 w-[29px]" : "h-[118px] w-[42px]"} rounded-md object-cover`} /> : <span key={r.ref} aria-hidden className={`${c.phone ? "h-20 w-[29px]" : "h-[118px] w-[42px]"} rounded-md border border-dashed border-border-strong bg-surface-2`} />;
        })}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="font-semibold">
            {into.role} · {other.role}
          </span>
          <span className="text-sm text-muted">{each}</span>
          <span className="flex-1" />
          <Status s={{ tone: "warning", word: "Check" }} />
        </div>
        <p className="text-sm text-muted" title={pair.why}>
          These may be the same person.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" icon={Copy} busy={merge.isPending} onClick={() => merge.mutate()}>
            Merge into {into.role}
          </Button>
          <Button variant="secondary" busy={apart.isPending} onClick={() => apart.mutate()}>
            They’re different
          </Button>
        </div>
      </div>
    </section>
  );
}

/** A place the shots use (S-gaps-07 A, Reed: yes): the role card with a wide picture and where its look came from. One
 *  with no look yet is picked from the brand's places, uploaded (free) or made for this video (its "up to" first);
 *  a place made for the video never enters the brand's library. */
function PlaceCard({ a, c }: { a: Asset; c: Ctx }) {
  const toast = useToast();
  const file = useRef<HTMLInputElement>(null);
  const [changing, setChanging] = useState<string | null>(null);
  const ci = c.gate(a);
  const id = a.library_item_id;
  const queryClient = useQueryClient();
  const { price: sheet } = useSheetPrice();
  const needs = ci ? ci.readiness === "needs_look" : a.sheet_status === "none" || a.sheet_status === "missing";
  const readiness = ci?.readiness ?? (needs ? "needs_look" : a.sheet_status === "drawing" ? "drawing" : a.sheet_status === "waiting_for_owner" ? "waiting_for_owner" : "ready");
  const s: State = gateState(ci) ?? (readiness === "needs_look" ? { tone: "warning", word: "Needs a look" } : readiness === "drawing" ? { tone: "accent", word: "Drawing" } : readiness === "waiting_for_owner" ? { tone: "warning", word: "Waiting for the owner", hollow: true } : { tone: "success", word: "Approved" });
  const busy = readiness === "drawing" || readiness === "waiting_for_owner";
  const places = useQuery({ queryKey: ["library", "place", c.brandId, false], enabled: needs, queryFn: async () => (await api.GET("/library/{kind}", { params: { path: { kind: "place" }, query: { brand_id: c.brandId } } })).data ?? [] });
  const run = useMutation({ mutationFn: (f: () => Promise<unknown>) => f(), onSettled: () => Promise.all([refreshJobs(queryClient), c.refresh()]), onError: (e: Error) => toast(e.message, undefined, "error") });
  const n = a.clip_ids.length;
  // A place made for this video carries its look's "up to"; a brand place's look is priced as one sheet with its check.
  const look = a.look_credits ?? sheet ?? null;
  const price = look == null ? null : upTo(c.head, look);
  const saved = (places.data ?? []).filter((x) => x.id !== id);
  const note = (text: string) =>
    run.mutate(async () => {
      await must(api.POST("/projects/{project_id}/director/messages", { params: { path: { project_id: c.projectId } }, body: { text: `${a.name}: ${text}` } }));
      setChanging(null);
      toast(`Asked the director: “${text}”.`);
    });
  return (
    <section aria-label={a.name} className={`flex gap-3.5 rounded-lg border p-3 ${needs || s.word.startsWith("Changed") ? "border-[#ecd3a6] bg-[#fffdf8]" : "border-border bg-surface"}`}>
      <Picture a={{ ...a, sheet_file_id: ci?.preview_file_id ?? a.sheet_file_id }} wide={!c.phone} phone={c.phone} />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="font-semibold">{a.name}</span>
          {n > 0 && !c.phone && <span className="text-sm text-muted">{n} clip{n === 1 ? "" : "s"}</span>}
          <span className="flex-1" />
          <Status s={s} />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {sourceTag(ci, c.brand, c.phone) ? <Tag>{sourceTag(ci, c.brand, c.phone)}</Tag> : needs && <Tag>No look yet</Tag>}
          <Revised ci={ci} phone={c.phone} />
          {needs && n > 0 && !c.phone && (
            <span className="text-sm text-muted">
              {clipsText(a.clip_ids)} wait{n === 1 ? "s" : ""} for it.
            </span>
          )}
        </div>
        {changing !== null ? (
          <div className="flex flex-col gap-2">
            <TextArea label={`Change ${a.name}…`} rows={2} maxLength={500} placeholder="What should change?" value={changing} onChange={(e) => setChanging(e.target.value)} />
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" icon={MessageSquare} busy={run.isPending} disabled={!changing.trim()} reason={changing.trim() ? "Asking is free. The director shows any price before it makes a new look." : "Say what should change"} onClick={() => note(changing.trim())}>
                Ask the director
              </Button>
              <Button variant="ghost" onClick={() => setChanging(null)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : needs && id != null && !c.hasGate ? (
          <p className="text-sm text-muted">Its look is made with the cast and places, once they’re ready to check.</p>
        ) : needs && id != null ? (
          <div className="flex flex-wrap items-center gap-2">
            <Menu
              title={`Pick from ${c.brand}’s places`}
              trigger={(t) => (
                <Button icon={MapPin} disabled={saved.length === 0} reason={saved.length === 0 ? `${c.brand} has no saved places yet.` : undefined} {...t}>
                  {c.phone ? "Library" : `From ${c.brand}’s library`}
                </Button>
              )}
            >
              {(close) =>
                saved.map((x) => (
                  <MenuItem key={x.id} onClick={() => (close(), run.mutate(() => pickPlace(c.projectId, id, x.id)))}>
                    {x.sheet_file_id ? <img src={fileUrl(x.sheet_file_id)} alt="" className="h-8 w-12 shrink-0 rounded-sm object-cover" /> : <span aria-hidden className="h-8 w-12 shrink-0 rounded-sm bg-surface-2" />}
                    <span className="min-w-0 flex-1 truncate">{x.name}</span>
                  </MenuItem>
                ))
              }
            </Menu>
            <input
              ref={file}
              type="file"
              accept="image/*"
              className="hidden"
              aria-label={`Upload a picture of ${a.name}`}
              onChange={(e) => {
                const f = e.target.files?.[0];
                e.target.value = "";
                if (f) run.mutate(async () => uploadPlace(c.projectId, id, (await uploadFile(f)).id));
              }}
            />
            <Button variant="secondary" icon={Upload} onClick={() => file.current?.click()}>
              Upload
            </Button>
            <Priced icon={WandSparkles} label={c.phone ? "Make" : "Make one"} price={price} busy={run.isPending || look == null} onClick={() => run.mutate(() => makePlace(c.projectId, id))} />
          </div>
        ) : busy ? (
          a.drawing_job_id != null && (
            <div>
              <Button variant="secondary" busy={run.isPending} onClick={() => run.mutate(() => must(api.POST("/jobs/{job_id}/cancel", { params: { path: { job_id: a.drawing_job_id! } } })))}>
                Cancel
              </Button>
            </div>
          )
        ) : (
          !needs && (
            <div>
              <Button variant="ghost" icon={MessageSquare} onClick={() => setChanging("")}>
                Change…
              </Button>
            </div>
          )
        )}
      </div>
    </section>
  );
}

/** "Marcus, Jade, Mom and 2 places": the approved ones folded into one line. */
const foldWords = (rows: Asset[]) => {
  const people = rows.filter((a) => a.kind === "character").map((a) => a.role || a.name);
  const n = rows.length - people.length;
  return names([...people, ...(n ? [people.length ? `${n} place${n === 1 ? "" : "s"}` : `Places · ${rows.map((a) => a.name).join(", ")}`] : [])]);
};

const names = (l: string[]) => (l.length < 2 ? l.join("") : `${l.slice(0, -1).join(", ")} and ${l.at(-1)}`);

/** "Approve cast & places" (Reed, S-gaps-07 B as redrawn): what waits for the one combined OK, said once above the set. */
function GateBanner({ gate, phone, head }: { gate: Cast; phone: boolean; head: PaneProps["head"] }) {
  const changed = gate.items.filter((i) => i.approval === "changed").map((i) => i.name);
  const kept = gate.items.filter((i) => i.approval === "approved").length;
  if (gate.state === "none" || (gate.state === "approved" && !gate.waiting.length)) return null;
  const pv = gate.previews;
  const previews = pv && pv.credits > 0 ? ` Previews so far: ${pv.usd != null ? `$${pv.usd.toFixed(2)}` : spent(head, pv.credits)} of the approved budget.` : "";
  if (changed.length && kept)
    return (
      <p className="flex items-start gap-2 rounded-lg bg-warning-soft px-3 py-2.5 text-sm text-warning">
        <Users size={14} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
        <span>
          <b className="font-semibold">{names(changed)} changed.</b>{" "}
          {phone ? "Approve again before anything new with them is made. The rest stay approved." : `Approve the cast and places again before anything new with ${names(changed)} is made. The other ${kept === 1 ? "one stays" : `${kept} stay`} approved, and clips without ${changed.length === 1 ? "it" : "them"} carry on.`}
        </span>
      </p>
    );
  return (
    <p className="flex items-start gap-2 rounded-lg bg-accent-soft px-3 py-2.5 text-sm text-accent-text">
      <Users size={14} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
      <span>
        <b className="font-semibold">{phone ? "Check them together." : "Check the cast and places together."}</b> {phone ? "Storyboards and clips wait for your OK." : `Storyboards and clips that use them wait until you approve. The rest of the plan carries on.${previews}`}
        {gate.not_ready.length > 0 && <> Not ready yet: {gate.not_ready.map((x) => x.why).join("; ")}.</>}
      </span>
    </p>
  );
}

/** Stills and clips made with a look since changed (S-gaps-07 B): kept as they are; once approved, remake them at their
 *  "up to", or keep them (recorded, and they leave the price). */
function UpdateCard({ gate, c, frames }: { gate: Cast; c: Ctx; frames: { clip_id: string; shot_id: string; id: number; file_id: number | null }[] }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { clips, stills } = gate.update;
  const run = useMutation({ mutationFn: (f: () => Promise<unknown>) => f(), onSettled: () => Promise.all([refreshJobs(queryClient), c.refresh()]), onError: (e: Error) => toast(e.message, undefined, "error") });
  if (!clips.length && !stills.length) return null;
  // Whose look changed: what isn't approved yet, else (after the OK) what was revised and shows in these clips.
  const touched = gate.items.filter((i) => i.clip_ids.some((x) => clips.includes(x)) || frames.some((f) => stills.includes(f.shot_id) && i.clip_ids.includes(f.clip_id)));
  const who = (touched.some((i) => i.approval !== "approved") ? touched.filter((i) => i.approval !== "approved") : touched.filter((i) => i.revised_at)).map((i) => i.name);
  const what = clips.length ? clipsText(clips) : `${stills.length} still${stills.length === 1 ? "" : "s"}`;
  const waits = gate.state !== "approved";
  const thumbs = clips.length ? clips.map((x) => frames.find((f) => f.clip_id === x)?.file_id ?? null) : stills.map((x) => frames.find((f) => f.shot_id === x)?.file_id ?? null);
  const remake = () =>
    run.mutate(async () => {
      for (const f of frames.filter((x) => stills.includes(x.shot_id) && !clips.includes(x.clip_id))) await must(api.POST("/projects/{project_id}/storyboard/frames/{frame_id}/render", { params: { path: { project_id: c.projectId, frame_id: f.id } } }));
      const rows = clips.length ? ((await must(api.GET("/projects/{project_id}/clips", { params: { path: { project_id: c.projectId } } }))).data ?? []) : [];
      for (const r of rows.filter((x) => clips.includes(x.clip_id))) await must(api.POST("/projects/{project_id}/clips/{clip_id}/generate", { params: { path: { project_id: c.projectId, clip_id: r.id } }, body: { note: "" } }));
    });
  return (
    <section aria-label="Made with an older look" className="flex gap-3 rounded-lg border border-border bg-surface p-3">
      <div aria-hidden className="flex shrink-0 gap-1">
        {thumbs.slice(0, 3).map((f, k) => (f ? <img key={k} src={fileUrl(f)} alt="" className="h-14 w-8 rounded-[3px] object-cover" /> : <span key={k} className="h-14 w-8 rounded-[3px] bg-surface-2" />))}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <span className="font-semibold">
          {what} {clips.length === 1 || (!clips.length && stills.length === 1) ? "was" : "were"} made with {who.length ? `${names(who)}’s` : "an"} old look
        </span>
        <span className="text-sm text-muted">{waits ? "They’re kept as they are. After you approve, you choose:" : "They’re kept as they are. Remake them with the new look, or keep them."}</span>
        <div className={`flex gap-2 ${c.phone ? "flex-col" : "flex-wrap"}`}>
          <Priced icon={RefreshCw} label={`Remake ${what.toLowerCase()}${c.phone ? "" : " with the new look"}`} price={upTo(c.head, stills.length ? gate.update.credits : (gate.update.clips_credits ?? gate.update.credits))} busy={run.isPending} disabled={waits} reason={waits ? "Approve the cast and places first." : null} onClick={remake} />
          <Button variant="secondary" busy={run.isPending} onClick={() => run.mutate(() => keepOld(c.projectId, null, null))}>
            Keep them
          </Button>
        </div>
      </div>
    </section>
  );
}

/** The video's Cast tab (v6 S5-01 to S5-04, P-09, S-gaps-05 L3, S-gaps-07): the presenter, every role with its look and
 *  the one press that moves it on, then the places. Editors see credits. Replaces the old Cast step (rule 26). */
export function CastPane({ p, head, progress }: PaneProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const phone = !useMedia("(min-width: 768px)");
  const assets = useAssets(p.id);
  const cast = useCast(p.id);
  const frames = useFrames(p.id);
  const { locks: read, save } = useLocks(p.id);
  const locks = read ?? NO_LOCKS; // nothing locked until the read says otherwise
  const brands = useBrands();
  const pairs = useQuery({ queryKey: ["assets-maybe-same", p.id], queryFn: async () => (await api.GET("/projects/{project_id}/assets/maybe-same", { params: { path: { project_id: p.id } } })).data ?? [] });
  const characters = useQuery({
    queryKey: ["library", "character", p.brand_id, false],
    queryFn: async () => (await api.GET("/library/{kind}", { params: { path: { kind: "character" }, query: { brand_id: p.brand_id } } })).data ?? [],
  });
  const brand = brands.data?.find((b) => b.id === p.brand_id)?.name ?? "the brand";
  const refresh = () => Promise.all([["assets", p.id], ["cast", p.id], ["assets-maybe-same", p.id], ["library", "character"], ["breakdown", p.id], ["storyboard", p.id], ["project-clips", p.id], ["locks", p.id], ["project", p.id], ["idea", p.id], ["host", p.id]].map((queryKey) => queryClient.invalidateQueries({ queryKey })));
  // One press for the whole set as this person saw it (each item's sig); if anything changed meanwhile, it says so and
  // shows the set again.
  const approve = useMutation({
    mutationFn: (gate: Cast) => approveCast(p.id, gate.items),
    onSuccess: (out) => {
      queryClient.setQueryData(["cast", p.id], out);
      toast("Cast and places approved. What waited for them carries on.");
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
    onSettled: refresh,
  });
  if (assets.isPending || cast.isPending) return <Skeleton className="h-64" />;
  const gate = cast.data ?? null;
  const rows = (assets.data ?? []).filter((a) => !notInShots(a));
  const roles = rows.filter((a) => a.kind === "character");
  const places = rows.filter((a) => a.kind === "place");
  const c: Ctx = {
    projectId: p.id,
    brandId: p.brand_id,
    brand,
    head,
    total: progress.clips.total,
    characters: characters.data ?? [],
    roles: locks.locks.roles ?? [],
    outfits: locks.outfits,
    setLocks: (change) => save.mutateAsync(change(queryClient.getQueryData<components["schemas"]["LocksIO"]>(["locks", p.id]) ?? locks)),
    locksReady: !!read,
    all: roles,
    // The checkpoint names a locked role by its slot (slot:2) and a cast look by its item (char:4): match either.
    hasGate: !!gate,
    gate: (a) => (gate?.items ?? []).find((i) => i.ref === a.ref || (a.slot_id != null && i.ref === `slot:${a.slot_id}`) || (i.kind === a.kind && a.library_item_id != null && i.library_item_id === a.library_item_id)),
    refresh,
    phone,
  };
  const merged = (pairs.data ?? []).filter((x) => x.undo_token); // merged by itself ("Mom is Mom in this video"), with Undo
  const unmerge = (token: number) => void must(api.POST("/projects/{project_id}/assets/merge/undo", { params: { path: { project_id: p.id } }, body: { token } })).then(refresh, (e: Error) => toast(e.message, undefined, "error"));
  const open = (pairs.data ?? []).filter((x) => !x.undo_token && roles.some((r) => r.slot_id === x.a_slot_id) && roles.some((r) => r.slot_id === x.b_slot_id));
  const paired = new Set(open.flatMap((x) => [x.a_slot_id, x.b_slot_id]));
  const noSaved = c.characters.length === 0;
  const changed = (gate?.items ?? []).filter((i) => i.approval === "changed");
  // Once something changed after the OK, the approved items fold into one line, so the change stands out (S-gaps-07 B).
  const folds = (a: Asset) => changed.length > 0 && c.gate(a)?.approval === "approved" && (phone || a.kind === "place");
  const folded = [...roles, ...places].filter(folds);
  const section = (title: string, n: number) => (
    <div className="flex items-baseline justify-between gap-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      <span className="text-xs text-muted tabular-nums">{n}</span>
    </div>
  );
  const waiting = !!gate && (gate.state === "ready" || gate.state === "not_ready" || gate.waiting.length > 0);
  const said = !gate ? null : changed.length && gate.approved_at ? `Needs you · ${changed.length} change${changed.length === 1 ? "" : "s"}` : gate.state === "approved" ? "Approved" : gate.state === "none" ? null : "Needs you · approve to continue";
  const counts = `${roles.length} character${roles.length === 1 ? "" : "s"} · ${places.length} place${places.length === 1 ? "" : "s"}`;
  const card = (a: Asset) => {
    if (a.slot_id != null && paired.has(a.slot_id)) {
      const pair = open.find((x) => x.a_slot_id === a.slot_id || x.b_slot_id === a.slot_id)!;
      if (pair.a_slot_id !== a.slot_id) return null; // drawn once, where its first role is
      return <PairCard key={`pair-${pair.a_slot_id}-${pair.b_slot_id}`} pair={pair} rows={roles} c={c} />;
    }
    return <RoleCard key={`${a.ref}-${a.slot_id}`} a={a} c={c} />;
  };
  return (
    <div className={`flex flex-col ${phone ? "gap-2" : "gap-4"}`}>
      <Presenter p={p} head={head} rows={roles} brand={brand} phone={phone} approval={(id) => gate?.items.find((i) => i.library_item_id === id)?.approval} />
      {roles.length === 0 && places.length === 0 ? (
        <Empty title="The cast fills in here">The director reads who’s in the script, then gives each role a look: a saved character first, or one made for this video.</Empty>
      ) : (
        <>
          <div className="flex items-baseline justify-between gap-3">
            <h2 className={phone ? "text-sm font-semibold" : "text-lg font-semibold"}>Cast &amp; places</h2>
            {said ? <Status s={{ tone: said === "Approved" ? "success" : "warning", word: said }} /> : <span className={`${phone ? "text-xs" : "text-sm"} text-muted`}>{counts}</span>}
          </div>
          {gate && <GateBanner gate={gate} phone={phone} head={head} />}
          {merged.map((x) => (
            <p key={x.undo_token} className="flex min-h-control items-center gap-2 rounded-lg border border-border px-3 text-sm">
              <span className="flex-1">{x.why}</span>
              <Button variant="ghost" dense onClick={() => unmerge(x.undo_token!)}>
                Undo
              </Button>
            </p>
          ))}
          <span id="cast-list" />
          {section("Characters", roles.length)}
          <div className={`flex flex-col ${phone ? "gap-2" : "gap-3"}`}>{roles.filter((a) => !folds(a)).map(card)}</div>
          {noSaved && !phone && (
            <section className="flex flex-col items-start gap-2 rounded-lg border border-border bg-surface p-3">
              <span className="font-semibold">{brand} has no saved characters yet</span>
              <p className="text-sm text-muted">The director prepares the characters and places. Review them together, request any changes, then approve the cast and places to continue. To reuse a person in every video, add them in Cast &amp; places.</p>
              <Link to={`/b/${p.brand_id}/library/characters`} className="inline-flex min-h-control items-center gap-2 rounded-md border border-border-button px-3 text-sm font-medium hover:bg-surface-2 lg:min-h-control-dense">
                <Users size={16} strokeWidth={1.75} aria-hidden />
                Open Cast &amp; places
              </Link>
            </section>
          )}
          {places.length > 0 && (
            <>
              {section("Places", places.length)}
              <div className={`flex flex-col ${phone ? "gap-2" : "gap-3"}`}>
                {places.filter((a) => !folds(a)).map((a) => (
                  <PlaceCard key={a.ref} a={a} c={c} />
                ))}
              </div>
            </>
          )}
          {folded.length > 0 && (
            <p className="flex items-center gap-2 text-sm text-muted">
              <Check size={14} strokeWidth={1.75} aria-hidden />
              <span className="flex-1">{foldWords(folded)}</span>
              <Status s={{ tone: "success", word: "Approved" }} />
            </p>
          )}
          {gate && <UpdateCard gate={gate} c={c} frames={frames.data ?? []} />}
          {!phone && roles.length > 0 && (
            <p className="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2.5 text-sm">
              <Lock size={14} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
              Locked looks are used as they are in every shot. The sheet sets the face, and the outfit unless this video sets its own.
            </p>
          )}
          {gate && waiting && gate.can_approve === false && <p className="text-sm text-muted">Whoever made this video, or the owner, approves the cast and places.</p>}
          {gate && waiting && gate.can_approve !== false && (
            <div className={`sticky -bottom-5 z-10 -mx-5 -mb-5 flex items-center gap-3 border-t border-border bg-surface px-5 pt-3 pb-5 ${phone ? "flex-col items-stretch" : ""}`}>
              {!phone && <span className="flex-1 text-sm text-muted">{[counts, changed.length && gate.approved_at ? `${changed.length} change${changed.length === 1 ? "" : "s"} · ${gate.items.length - changed.length} still approved` : ""].filter(Boolean).join(" · ")}</span>}
              <Button icon={Check} busy={approve.isPending} disabled={gate.state === "not_ready" || gate.waiting.length === 0} reason={gate.state === "not_ready" ? `Not ready yet: ${gate.not_ready.map((x) => x.why).join("; ")}.` : gate.waiting.length === 0 ? "Nothing new to approve." : null} onClick={() => approve.mutate(gate)}>
                Approve cast &amp; places
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
