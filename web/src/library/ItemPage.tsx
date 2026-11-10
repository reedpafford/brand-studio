import { useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArrowLeft, Check, ChevronDown, Pencil, Upload } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, errorText, must } from "../api/client";
import { fileUrl } from "../api/upload";
import { Banner, Button, Field, Menu, MenuItem, textSize } from "../components";
import { refreshJobs } from "../jobs/refresh";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useRail } from "../useMedia";
import { Picture } from "./Cards";
import { ItemMore } from "./ItemMore";
import { LibraryFrame } from "./LibraryFrame";
import { SHEET_MODEL, SHEET_NOTE, lookFitNote } from "./sheets";
import { useJobs } from "../clip/History";
import { KINDS, PRODUCT_TYPE, cover, day, isKindSlug, upTo, useItems, videos, type Item, type KindSlug } from "./kinds";
import { addPicture } from "./products";
import { sampleOf, useVoiceList, voiceFields, voiceOf, type Voice } from "./Voices";
import { AddScreens } from "../brand/AddScreens";
import { ScreenEditor, useScreens, type Screen } from "../brand/screens";

/** /b/:brandId/library/:tab/:itemId: one saved item (S8-03), with everything else under More (S-gaps-05 L5). */
export function ItemPage() {
  const { brandId, kindSlug, itemId } = useParams();
  const slug = isKindSlug(kindSlug) ? kindSlug : "characters";
  const kind = KINDS[slug].kind;
  const id = Number(brandId);
  const item = useQuery({
    queryKey: ["library", kind, "item", Number(itemId)],
    queryFn: async () => {
      const { data, response } = await api.GET("/library/{kind}/{item_id}", { params: { path: { kind, item_id: Number(itemId) } } });
      if (response.status === 404) return null; // gone or archived
      if (!data) throw new Error("load");
      return data;
    },
    refetchInterval: (q) => (["drawing", "waiting_for_owner"].includes(q.state.data?.sheet_status ?? "") ? 3000 : false),
  });
  const back = useSearchParams()[0].get("back"); // "Open Mia" from a video comes back to it
  const backTo = back?.startsWith(`/b/${id}/`) ? back : null;
  const action = backTo ? (
    <Link to={backTo} className="inline-flex min-h-control items-center gap-1.5 rounded-md border border-border-button px-3 lg:min-h-9 text-sm font-medium">
      <ArrowLeft size={14} strokeWidth={1.75} aria-hidden />
      Back to your video
    </Link>
  ) : (
    <Link to={`/b/${id}/library/${slug}`} className="inline-flex min-h-control items-center gap-1.5 rounded-md border border-border-button px-3 lg:min-h-9 text-sm font-medium">
      <ArrowLeft size={14} strokeWidth={1.75} aria-hidden />
      Back to {KINDS[slug].title.toLowerCase()}
    </Link>
  );
  return (
    <LibraryFrame brandId={id} tab={slug} action={action}>
      {item.isPending ? (
        <p className="text-muted">Loading…</p>
      ) : item.isError ? (
        <Banner title="Couldn't load this." action={<Button variant="secondary" onClick={() => void item.refetch()}>Try again</Button>}>Check your connection.</Banner>
      ) : !item.data ? (
        <p>That {KINDS[slug].one} doesn't exist, or it was archived.</p>
      ) : (
        <Page key={`${item.data.id}-${item.data.version}`} item={item.data} slug={slug} brandId={id} />
      )}
    </LibraryFrame>
  );
}

const STATUS: Record<string, { words: string; dot: string; text: string }> = {
  approved: { words: "In use", dot: "bg-success", text: "text-success" },
  needs_approval: { words: "Needs your OK", dot: "bg-[var(--need-dot,var(--warning))]", text: "text-warning" },
  drawing: { words: "Drawing the sheet", dot: "bg-accent", text: "text-accent-text" },
  waiting_for_owner: { words: "Waiting for the owner’s OK", dot: "bg-accent", text: "text-accent-text" },
  none: { words: "No sheet yet", dot: "border border-muted", text: "text-muted" },
};
const USED = { done: ["Done", "bg-success", "text-success"], making: ["Working", "bg-accent", "text-accent-text"], needs_you: ["Needs you", "bg-warning", "text-warning"] } as const;

function Page({ item, slug, brandId }: { item: Item; slug: KindSlug; brandId: number }) {
  const { kind, title } = KINDS[slug];
  const product = kind === "prop";
  const rail = useRail();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const path = { kind, item_id: item.id };
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["library", kind] });
  const [changing, setChanging] = useState<string | null>(null);
  const versions = useVersions(item);
  const [shown, setShown] = useState<number | null>(null); // an old version picked to look at
  const big = shown ?? cover(item);
  const archive = useMutation({
    mutationFn: () => must(api.DELETE("/library/{kind}/{item_id}", { params: { path } })),
    onSuccess: async () => {
      await refresh();
      navigate(`/b/${brandId}/library/${slug}`);
      toast(`${item.name} archived.`, async () => {
        await api.POST("/library/{kind}/{item_id}/unarchive", { params: { path } });
        void refresh();
      });
    },
  });
  const draw = useMutation({
    mutationFn: async (change: string) => {
      const { data, error } = await api.POST("/library/{kind}/{item_id}/sheet", { params: { path }, body: { model_id: SHEET_MODEL, change } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => {
      setChanging(null);
      refreshJobs(queryClient);
      void refresh();
    },
  });
  const approve = useMutation({
    mutationFn: () => must(api.POST("/library/{kind}/{item_id}/sheet/approve", { params: { path } })),
    onSuccess: () => {
      void refresh();
      toast(`${item.name}'s sheet approved.`, async () => {
        await api.DELETE("/library/{kind}/{item_id}/sheet/approve", { params: { path } });
        void refresh();
      });
    },
  });
  const restore = useMutation({
    mutationFn: (version: number) => must(api.POST("/library/{kind}/{item_id}/versions/{version}/restore", { params: { path: { ...path, version } } })),
    onSuccess: () => (setShown(null), void refresh()),
  });
  const photo = useMutation({
    mutationFn: (file: File) => addPicture(brandId, item, file),
    onSuccess: refresh,
  });
  const status = STATUS[item.sheet_status] ?? STATUS.none;
  const usd = item.usd;
  const changeCost = upTo(item.change_credits || undefined, usd?.change);
  const makeCost = upTo(item.sheet_credits || undefined, usd?.sheet);
  const busy = item.sheet_status === "drawing" || item.sheet_status === "waiting_for_owner";
  const app = item.product_type === "app";
  const sub = product ? [PRODUCT_TYPE[app ? "app" : "physical"], item.short_description].filter(Boolean).join(" · ") : [item.presenter ? "Presenter" : "", item.notes].filter(Boolean).join(" · ");
  const [editing, setEditing] = useState<Screen | null>(null);
  const [adding, setAdding] = useState(false);
  const screens = useScreens(product ? brandId : 0);
  const shownPicture = product ? (item.pictures ?? []).find((p) => p.file_id === big) : undefined;
  const err = archive.error ?? draw.error ?? approve.error ?? restore.error ?? photo.error;
  const size = textSize(changing ?? "", SHEET_NOTE); // counted, and past the most it waits, said plainly (never cut)
  const old = versions.filter((v) => v.file_id !== cover(item));
  const jobs = useJobs();
  const last = (jobs.data ?? []).filter((j) => j.step === "sheet" && j.library_item_id === item.id).sort((a, b) => b.id - a.id)[0];
  const failed = !product && last?.status === "failed" && !busy;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:gap-8">
        {/* On a phone the name, its presses and facts come first, the picture after (QA-3 on #1204). */}
        <div className="order-2 flex flex-col gap-3 lg:order-1">
          <Picture id={big} alt={item.name} className={rail ? "h-[400px] w-[300px]" : "aspect-[3/4] w-full"} />
          {(old.length > 0 || product) && (
            <div className="flex flex-wrap gap-2">
              {(product ? (item.pictures ?? []).map((p) => ({ file_id: p.file_id, label: p.variant || p.name, version: 0 })) : [{ file_id: cover(item), label: item.sheet_status === "approved" ? `v${item.version} · in use` : `v${item.version}`, version: item.version }, ...old]).map((v, n) =>
                v.file_id ? (
                  <button key={`${v.file_id}-${n}`} type="button" aria-label={`${item.name}, ${v.label}`} aria-pressed={(shown ?? cover(item)) === v.file_id} onClick={() => setShown(n === 0 && !product ? null : v.file_id!)} className="flex flex-col gap-1 text-left">
                    <img src={fileUrl(v.file_id)} alt="" className={`h-[94px] w-[70px] rounded-md object-cover ${(shown ?? cover(item)) === v.file_id ? "outline-2 outline-offset-2 outline-accent" : ""}`} />
                    <span className={`w-[70px] truncate text-xs ${n === 0 && !product ? "font-semibold" : "text-muted"}`}>{v.label}</span>
                  </button>
                ) : null,
              )}
              {product && app && (
                <button type="button" onClick={() => setAdding(true)} className="flex h-[94px] w-[70px] flex-col items-center justify-center gap-1 rounded-md border border-dashed border-border-strong bg-surface-2 text-muted hover:text-text">
                  <Upload size={16} strokeWidth={1.75} aria-hidden />
                  <span className="text-[11px] leading-tight">Add screens</span>
                </button>
              )}
              {product && !app && (
                <label className="flex h-[94px] w-[70px] cursor-pointer flex-col items-center justify-center gap-1 rounded-md border border-dashed border-border-strong bg-surface-2 text-center text-muted hover:text-text" title="Another photo: a flavour, a size or another side">
                  <Upload size={16} strokeWidth={1.75} aria-hidden />
                  <span className="text-[11px] leading-tight">{(item.pictures ?? []).length ? "Add another photo" : "Add a photo"}</span>
                  <input type="file" accept="image/*" className="sr-only" onChange={(e) => e.target.files?.[0] && photo.mutate(e.target.files[0])} />
                </label>
              )}
            </div>
          )}
          {shownPicture && (
            <Button variant="secondary" icon={Pencil} onClick={() => setEditing(screens.data?.find((s) => s.id === shownPicture.screen_id) ?? null)}>
              Edit this {app ? "screen" : "photo"}
            </Button>
          )}
          {editing && <ScreenEditor key={editing.id} brandId={brandId} screen={editing} onClose={() => setEditing(null)} />}
          {adding && <AddScreens brandId={brandId} productId={item.id} tags={[...new Set((screens.data ?? []).flatMap((s) => s.tags))].sort()} onClose={() => setAdding(false)} />}
          {shown !== null && !product && (
            <Button variant="secondary" busy={restore.isPending} onClick={() => restore.mutate(versions.find((v) => v.file_id === shown)!.version)}>
              Use this version
            </Button>
          )}
        </div>
        <div className="order-1 flex min-w-0 max-w-[640px] grow flex-col gap-5 lg:order-2">
          <div className="flex flex-col gap-1">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold">{item.name}</h1>
              {!product && (
                <span className={`inline-flex items-center gap-1.5 text-sm font-medium ${status.text}`}>
                  <span aria-hidden className={`size-2 rounded-full ${status.dot}`} />
                  {status.words}
                </span>
              )}
              <span className="flex-1" />
              {!product && item.sheet_status === "needs_approval" && (
                <Button icon={Check} busy={approve.isPending} onClick={() => approve.mutate()}>Approve</Button>
              )}
              {!product && !busy && (
                <Button variant="secondary" icon={Pencil} onClick={() => (item.sheet_status === "none" ? draw.mutate("") : setChanging(""))} busy={draw.isPending && changing === null}>
                  {item.sheet_status === "none" ? "Make the sheet" : "Change this…"}
                  {(item.sheet_status === "none" ? makeCost : changeCost) && <>{" "}<span className="opacity-80">· {item.sheet_status === "none" ? makeCost : changeCost}</span></>}
                </Button>
              )}
              <Button variant="secondary" icon={Archive} busy={archive.isPending} onClick={() => archive.mutate()}>Archive</Button>
            </div>
            {sub && <p className="text-md text-muted">{sub}</p>}
          </div>
          {changing !== null && (
            <div className="flex flex-col gap-2 rounded-md border border-border bg-surface p-3">
              <Field autoFocus label="What should change?" value={changing} counter={size.counter} error={size.error} onChange={(e) => setChanging(e.target.value)} placeholder="“Navy polo, no hat, a little older”" />
              <div className="flex gap-2">
                <Button busy={draw.isPending} disabled={!changing.trim() || size.over} onClick={() => draw.mutate(changing.trim())}>
                  Change it{changeCost && <>{" "}<span className="opacity-80">· {changeCost}</span></>}
                </Button>
                <Button variant="ghost" onClick={() => setChanging(null)}>Cancel</Button>
              </div>
            </div>
          )}
          {item.look_fit && !busy && changing === null && (
            <p role="note" aria-label="Look check" className="rounded-md bg-warning-soft p-3 text-sm">
              {lookFitNote(item.look_fit)}{" "}
              <button type="button" className="font-medium text-accent-text hover:underline" onClick={() => setChanging(item.look_fit!.problem)}>Fix it with a note</button>
            </p>
          )}
          {failed && <p role="alert" className={errorClass}>The sheet didn’t finish. Nothing was charged.</p>}
          {err && <p role="alert" className={errorClass}>{err.message}</p>}
          <Facts item={item} brandId={brandId} />
          <UsedIn item={item} brandId={brandId} />
        </div>
      </div>
      <ItemMore item={item} kind={kind} brandId={brandId} title={title} />
    </div>
  );
}

/** The item's facts (S8-03): where it came from, its voice, its usual place, its rules. */
function Facts({ item, brandId }: { item: Item; brandId: number }) {
  const members = useQuery({ queryKey: ["team", "members"], queryFn: async () => (await api.GET("/team/members")).data ?? [] });
  const places = useItems("place", brandId);
  const queryClient = useQueryClient();
  const who = members.data?.find((m) => m.id === item.created_by_id)?.name;
  const pics = item.pictures?.length ?? 0;
  const from = item.kind === "prop" ? (item.product_type === "app" ? `${pics} real screen${pics === 1 ? "" : "s"}` : pics ? "A real photo" : "No photo yet") : item.source_photo_file_id ? "Uploaded" : "Made from a description";
  const came = [from, who && `by ${who}`].filter(Boolean).join(" ") + (item.created_at ? `, ${day(item.created_at)}` : "");
  const place = places.data?.find((p) => p.id === item.place_id);
  const setPlace = useMutation({
    mutationFn: (place_id: number | null) => must(api.PATCH("/library/{kind}/{item_id}", { params: { path: { kind: "character", item_id: item.id } }, body: { place_id } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["library", "character"] }),
  });
  const rows: [string, ReactNode][] = [["Came from", came]];
  if (item.kind === "character") {
    rows.push(["Voice", <CharacterVoice key="voice" item={item} brandId={brandId} />]);
    rows.push([
      "Place",
      <Menu key="place" title="Usual place" trigger={(p) => <button type="button" {...p} className="inline-flex min-h-control items-center gap-1 hover:underline lg:min-h-0">{place?.name ?? <span className="text-muted">None</span>}<ChevronDown size={14} strokeWidth={1.75} aria-hidden className="text-muted" /></button>}>
        {(close) => [
          ...(places.data ?? []).map((p) => <MenuItem key={p.id} checked={p.id === item.place_id} onClick={() => (close(), setPlace.mutate(p.id))}>{p.name}</MenuItem>),
          <MenuItem key="none" checked={!item.place_id} onClick={() => (close(), setPlace.mutate(null))}>None</MenuItem>,
        ]}
      </Menu>,
    ]);
  }
  if (item.kind === "prop") {
    rows.push(["Claim", item.main_claim || <span className="text-muted">Not said yet</span>]);
    rows.push(["Rules", item.notes || <span className="text-muted">None</span>]);
  }
  return (
    <dl className="grid grid-cols-[110px_minmax(0,1fr)] items-center gap-x-4 gap-y-2 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted">{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

/** A character's voice (S8-03 "Roger · relaxed · Play"): one of the app's voices or a saved one, changed from the list of
 *  every voice; an uploaded sample of their real voice plays too. */
function CharacterVoice({ item, brandId }: { item: Item; brandId: number }) {
  const voices = useVoiceList(brandId).data?.voices ?? [];
  const queryClient = useQueryClient();
  const voice = voiceOf(item, voices);
  const sample = voice ? sampleOf(voice) : item.voice_file_id ? fileUrl(item.voice_file_id) : null;
  const pick = useMutation({
    mutationFn: (v: Voice | null) => must(api.PATCH("/library/{kind}/{item_id}", { params: { path: { kind: "character", item_id: item.id } }, body: v ? voiceFields(v) : { voice_id: null, voice_stock_key: null } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["library", "character"] }),
  });
  const words = voice ? [voice.name, voice.description.split(",")[0].toLowerCase()].filter(Boolean).join(" · ") : item.voice_file_id ? "Their own voice sample" : "";
  return (
    <span className="inline-flex flex-wrap items-center gap-x-1">
      {words ? <span>{words}</span> : <span className="text-muted">None yet</span>}
      {sample && <> · <PlayLink src={sample} /></>}
      {" · "}
      <Menu title="Voice" trigger={(p) => <button type="button" {...p} className="inline-flex min-h-control items-center lg:min-h-0 text-accent-text hover:underline">{voice ? "Change" : "Pick a voice"}</button>}>
        {(close) => [
          ...voices.filter((v) => v.state !== "expired" && v.state !== "failed").map((v) => (
            <MenuItem key={v.id ?? v.stock_key ?? v.name} checked={v === voice} onClick={() => (close(), pick.mutate(v))}>{v.name}</MenuItem>
          )),
          voice && <MenuItem key="none" onClick={() => (close(), pick.mutate(null))}>No voice</MenuItem>,
        ]}
      </Menu>
    </span>
  );
}

/** A quiet Play for a sample (samples play free). */
function PlayLink({ src }: { src: string }) {
  const audio = useRef<HTMLAudioElement>(null);
  return (
    <>
      <button type="button" className="inline-flex min-h-control items-center lg:min-h-0 text-accent-text hover:underline" onClick={() => void audio.current?.play()}>Play</button>
      <audio ref={audio} src={src} preload="none" className="hidden" />
    </>
  );
}

/** "Used in N videos" (S8-03): each with its still, its status and its date; three, then "+ N more". */
function UsedIn({ item, brandId }: { item: Item; brandId: number }) {
  const [all, setAll] = useState(false);
  const used = item.used_in ?? [];
  if (used.length === 0) return <p className="text-sm text-muted">Not in a video yet.</p>;
  const rows = all ? used : used.slice(0, 3);
  return (
    <section aria-label="Used in" className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold">Used in {videos(used.length)}</h2>
      <ul className="divide-y divide-border rounded-lg border border-border bg-surface">
        {rows.map((u) => {
          const [words, dot, text] = USED[u.status];
          return (
            <li key={u.project_id}>
              <Link to={`/b/${brandId}/videos/${u.project_id}`} className="flex min-h-14 items-center gap-3 px-3 hover:bg-surface-2">
                <Picture id={u.still_file_id} alt="" className="h-[39px] w-[22px] shrink-0" />
                <span className="min-w-0 grow truncate font-medium">{u.name}</span>
                <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${text}`}>
                  <span aria-hidden className={`size-2 rounded-full ${dot}`} />
                  {words}
                </span>
                <span className="w-20 text-sm text-muted">{u.at ? day(u.at) : ""}</span>
              </Link>
            </li>
          );
        })}
        {used.length > 3 && (
          <li>
            <button type="button" className="min-h-control w-full px-3 text-left text-sm text-muted hover:text-text lg:min-h-10" onClick={() => setAll(!all)}>
              {all ? "Show fewer" : `+ ${used.length - 3} more`}
            </button>
          </li>
        )}
      </ul>
    </section>
  );
}

/** The sheets this item has had, newest first, each with the version it was in: S8-03's v3 · v2 · v1. */
function useVersions(item: Item) {
  const versions = useQuery({
    enabled: item.kind !== "prop",
    queryKey: ["library", item.kind, "versions", item.id, item.version],
    queryFn: async () => (await api.GET("/library/{kind}/{item_id}/versions", { params: { path: { kind: item.kind, item_id: item.id } } })).data ?? [],
  });
  const seen = new Set<number>();
  const out: { file_id: number; label: string; version: number }[] = [];
  for (const v of versions.data ?? []) {
    const file = v.sheet_file_id ?? v.snapshot.source_photo_file_id;
    if (!file || seen.has(file)) continue;
    seen.add(file);
    out.push({ file_id: file, label: `v${v.version}`, version: v.version });
  }
  return out;
}
