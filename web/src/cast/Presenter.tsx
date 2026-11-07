import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleHelp, Pause, Play, RefreshCw } from "lucide-react";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Button, useToast, useViewOnly } from "../components";
import { useVideoSettings } from "../projects/VideoSettings";
import { credits, upTo } from "../videos/money";
import type { Head } from "../videos/VideoHead";

type Project = components["schemas"]["ProjectOut"];
type Asset = components["schemas"]["AssetOut"];
type SettingIn = components["schemas"]["SettingIn"];
/** How a saved presenter appears in this video (S-gaps-05 L3): the style sets the start, any mix works. */
export type Way = "talks" | "corner" | "acts";
/** v6-models' per-video presenter field (SettingsOut.presenter / presenter_now; POST /settings takes `presenter`). */
type WithPresenter = { presenter?: Way | null; presenter_now?: Way | null; voice?: string | null };
/** A voice as GET /brands/{id}/voices lists it (#1314; `sample_url` is an API path the web puts /api before). */
type Voice = { id: number | null; name: string; kind?: string; uses?: string | null; stock_key: string | null; provider: string; description: string; sample_url: string | null; preview_file_id: number | null; sample_file_id: number | null };
type Voices = { voices: Voice[]; clone_credits: number; clone_usd: number | null };

export const WAYS: { id: Way; title: string; made: string; line: string; now: string }[] = [
  { id: "talks", title: "Talks to camera", made: "HeyGen from one still, with B-roll laid over parts", line: "Talks to camera, with B-roll laid over parts", now: "talks to camera" },
  { id: "corner", title: "In a corner over the B-roll", made: "HeyGen, keyed over the B-roll", line: "Talks over the B-roll for the whole video", now: "sits in a corner over the B-roll" },
  { id: "acts", title: "Acts in the story", made: "Omni: moves, acts, talks to others", line: "Acts in the story", now: "acts in the story" },
];
/** The style's start when the video doesn't say: UGC talks to camera, every other presenter sits in the corner. */
export const styleWay = (look: string): Way => (look === "ugc" ? "talks" : "corner");
/** A voice as the video's setting names it (#1327): an app voice by its key, a brand's by its id. */
const voiceRef = (v: Voice) => (v.id != null ? `voice:${v.id}` : `stock:${v.stock_key}`);
const PROVIDER: Record<string, string> = { elevenlabs: "ElevenLabs", minimax: "MiniMax", omni: "Omni" };

function useVoices(brandId: number) {
  return useQuery({
    queryKey: ["voices", brandId],
    retry: false,
    queryFn: async (): Promise<Voices | null> => {
      const r = await fetch(`/api/brands/${brandId}/voices`, { credentials: "same-origin" });
      return r.ok ? ((await r.json()) as Voices) : null; // not on this server yet: the voice reads as its name
    },
  });
}

/** A voice with its free sample (S5-02, S8-04). */
function VoiceRow({ v, on, onPick }: { v: Voice; on: boolean; onPick?: () => void }) {
  const [playing, setPlaying] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  useEffect(() => () => audio.current?.pause(), []); // a sample stops when its row closes
  const src = v.sample_url ? (/^https?:/.test(v.sample_url) ? v.sample_url : `/api${v.sample_url}`) : (v.preview_file_id ? fileUrl(v.preview_file_id) : v.sample_file_id ? fileUrl(v.sample_file_id) : null);
  const toggle = () => {
    if (!src) return;
    audio.current ??= Object.assign(new Audio(src), { onended: () => setPlaying(false) });
    if (playing) audio.current.pause();
    else void audio.current.play();
    setPlaying(!playing);
  };
  return (
    <div className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 ${on ? "border-accent bg-accent-soft" : "border-border bg-surface"}`}>
      <button type="button" disabled={!src} onClick={toggle} aria-label={`${playing ? "Stop" : "Play"} ${v.name}`} className="grid size-8 shrink-0 place-items-center rounded-md border border-border bg-surface text-muted disabled:opacity-50">
        {playing ? <Pause size={14} strokeWidth={1.75} aria-hidden /> : <Play size={14} strokeWidth={1.75} aria-hidden />}
      </button>
      <span className="flex min-w-0 flex-1 flex-col">
        {onPick ? (
          <button type="button" role="radio" aria-checked={on} onClick={onPick} className="text-left text-sm font-semibold hover:underline">
            {v.name}
          </button>
        ) : (
          <span className="text-sm font-semibold">{v.name}</span>
        )}
        <span className="truncate text-xs text-muted">{(v.kind === "described" ? [`Described: “${v.description}”`, v.uses && `${v.uses}’s voice`] : [v.description, PROVIDER[v.provider] ?? v.provider]).filter(Boolean).join(" · ")}</span>
      </span>
    </div>
  );
}

/** The presenter (S5-02, S-gaps-05 L3): a saved presenter is a face and a voice; this video picks how they appear. */
export function Presenter({ p, head, rows, brand, phone, approval }: { p: Project; head: Head | undefined; rows: Asset[]; brand: string; phone: boolean; approval?: (libraryItemId: number) => string | undefined }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const host = useQuery({ queryKey: ["host", p.id], queryFn: async () => (await api.GET("/projects/{project_id}/host", { params: { path: { project_id: p.id } } })).data ?? null });
  const settings = useVideoSettings(p.id);
  const lookOnly = useViewOnly();
  const [choosing, setChoosing] = useState(false);
  const [remaking, setRemaking] = useState(false);
  const remake = useMutation({
    mutationFn: () => must(api.POST("/projects/{project_id}/host/{number}", { params: { path: { project_id: p.id, number: 0 } } })),
    onSuccess: async () => {
      setRemaking(false);
      await queryClient.invalidateQueries({ queryKey: ["host", p.id] });
      toast("Making the presenter again. The one you have stays until the new one is made.");
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  // A person's narrator for this video (#1327's setting): free to change, it wins over the director's, with Undo.
  const pickVoice = useMutation({
    mutationFn: async (v: Voice) => must(api.POST("/projects/{project_id}/settings", { params: { path: { project_id: p.id } }, body: { voice: voiceRef(v) } as SettingIn })).then((r) => r.data!),
    onSuccess: (out, v) => {
      queryClient.setQueryData(["video-settings", p.id], out.settings);
      setChoosing(false);
      void queryClient.invalidateQueries({ queryKey: ["cast", p.id] }); // a new voice is a change the cast OK covers
      const back = (out.was as WithPresenter | undefined)?.voice ?? null;
      toast(`The narrator is now ${v.name}.`, () => void must(api.POST("/projects/{project_id}/settings", { params: { path: { project_id: p.id } }, body: { voice: back, undo: true } as SettingIn })).then(() => queryClient.invalidateQueries({ queryKey: ["video-settings", p.id] })));
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const voices = useVoices(p.brand_id);
  const s = settings.data as (typeof settings.data & WithPresenter) | undefined;
  const now: Way = s?.presenter_now ?? s?.presenter ?? styleWay(p.look);
  // The per-video choice is v6-models' setting: until the server has it, the style's start shows and can't be changed.
  const settable = !!s && "presenter_now" in s;
  const choose = useMutation({
    mutationFn: async (way: Way) => must(api.POST("/projects/{project_id}/settings", { params: { path: { project_id: p.id } }, body: { presenter: way } as SettingIn })).then((r) => r.data!),
    onSuccess: async (out, way) => {
      queryClient.setQueryData(["video-settings", p.id], out.settings);
      await queryClient.invalidateQueries({ queryKey: ["director", p.id] });
      const back = (out.was as WithPresenter | undefined)?.presenter;
      toast(`${who?.name || "The presenter"} now ${WAYS.find((w) => w.id === way)!.now}.`, () =>
        void must(api.POST("/projects/{project_id}/settings", { params: { path: { project_id: p.id } }, body: { presenter: back ?? null, undo: true } as SettingIn })).then(() => queryClient.invalidateQueries({ queryKey: ["video-settings", p.id] })),
      );
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const h = host.data;
  // Remake the presenter (Reed, 8): the still and every piece from it, its scope and "up to" said first; the pieces made
  // now stay as earlier versions until the new ones land.
  const still = h?.pieces.find((x) => x.number === 0 && x.file_id != null);
  const hasEarlier = !!h?.pieces.some((x) => x.earlier.length > 0);
  const back = useMutation({
    mutationFn: () => must(api.POST("/projects/{project_id}/host/back", { params: { path: { project_id: p.id } } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["host", p.id] });
      toast("The earlier presenter is back. Nothing was charged.", () => void must(api.POST("/projects/{project_id}/host/back", { params: { path: { project_id: p.id } } })).then(() => queryClient.invalidateQueries({ queryKey: ["host", p.id] })));
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  if (!h?.on) return null;
  const who = rows.find((r) => r.library_item_id === h.presenter_id) ?? null;
  const picture = who?.sheet_file_id ?? who?.photo_file_id ?? null;
  // The video's own voice (#1327: "stock:<key>" or "voice:<id>", a person's choice), else the narration's.
  const list = voices.data?.voices ?? [];
  const chosen = s?.voice ? list.find((v) => voiceRef(v) === s.voice) : undefined;
  // The voice it's read in (or will be, before the narration: the presenter's own saved voice, else the style's), by its
  // real key only: an app voice's key or a saved voice's "voice:<id>" (a saved voice has no app key to match by).
  const said = h.voice;
  const byKey = said ? list.find((v) => voiceRef(v) === said || (v.stock_key != null && v.stock_key === said)) : undefined;
  const voice = chosen ?? byKey ?? (said ? { id: null, name: said, stock_key: said, provider: "", description: "", sample_url: null, preview_file_id: null, sample_file_id: null } : null);
  const canVoice = !!s && "voice" in s && !lookOnly && list.length > 0;
  const way = WAYS.find((w) => w.id === now)!;
  const from = who ? (who.only_here ? "look made for this video" : `saved in ${brand}`) : "";
  const clone = voices.data ? (voices.data.clone_usd != null ? `up to $${voices.data.clone_usd.toFixed(2)}` : `up to ${credits(Math.ceil(voices.data.clone_credits))}`) : null;
  return (
    <section aria-label="Presenter" className={`flex flex-col ${phone ? "gap-2" : "gap-4"}`}>
      <div className="flex items-baseline justify-between gap-3">
        <h2 className={phone ? "text-sm font-semibold" : "text-lg font-semibold"}>Presenter</h2>
        <span className={`${phone ? "text-xs" : "text-sm"} text-muted`}>{way.line}</span>
      </div>
      <div className={`flex items-start ${phone ? "gap-3" : "gap-5"}`}>
        <figure className={`flex shrink-0 flex-col gap-2 ${phone ? "w-[90px]" : "w-[150px]"}`}>
          {picture ? (
            <img src={fileUrl(picture)} alt={`${who?.name ?? "The presenter"}’s look`} className={`${phone ? "h-[160px] w-[90px]" : "h-[266px] w-[150px]"} rounded-md bg-black object-cover`} />
          ) : (
            <span aria-hidden className={`${phone ? "h-[160px] w-[90px]" : "h-[266px] w-[150px]"} rounded-md border border-dashed border-border-strong bg-surface-2`} />
          )}
          {who && (
            <figcaption className="text-xs text-muted">
              {who.name || who.role} · {from}
            </figcaption>
          )}
        </figure>
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <dl className={`grid ${phone ? "grid-cols-[76px_1fr]" : "grid-cols-[110px_1fr]"} gap-x-3 gap-y-1.5 text-sm`}>
            <dt className="text-muted">Avatar</dt>
            <dd>
              {who ? `${who.name || who.role} still` : "Gets a look in the cast below"}
              {who?.slot_id != null && !lookOnly && (
                <>
                  {" · "}
                  <button type="button" aria-label="Change the avatar" className="text-accent-text hover:underline" onClick={() => (document.getElementById(`role-${who.slot_id}`) ?? document.getElementById("cast-list"))?.scrollIntoView({ block: "center", behavior: "smooth" })}>
                    Change
                  </button>
                </>
              )}
            </dd>
            <dt className="text-muted">Made with</dt>
            <dd>{way.made}</dd>
            <dt className="text-muted">Voice</dt>
            <dd>
              {voice ? [voice.name, PROVIDER[voice.provider]].filter(Boolean).join(" · ") : "Chosen when the narration is made"}
              {canVoice && (
                <>
                  {" · "}
                  <button type="button" aria-expanded={choosing} aria-label={choosing ? "Done choosing the voice" : "Change the voice"} onClick={() => setChoosing(!choosing)} className="text-accent-text hover:underline">
                    {choosing ? "Done" : "Change"}
                  </button>
                </>
              )}
            </dd>
          </dl>
          {choosing ? (
            <div className="flex flex-col gap-2">
              <div role="radiogroup" aria-label="The narrator’s voice" className="flex max-h-[260px] flex-col gap-2 overflow-y-auto">
                {list.map((v) => (
                  <VoiceRow key={voiceRef(v)} v={v} on={!!voice && voiceRef(v) === voiceRef(voice)} onPick={() => pickVoice.mutate(v)} />
                ))}
              </div>
            </div>
          ) : (
            voice && <VoiceRow v={voice} on />
          )}
          {!canVoice && !!s && !("voice" in s) && <span className="text-xs text-muted">The voice is the narration’s for now. Picking another for this video comes with the voice setting.</span>}
          {who?.library_item_id != null && approval?.(who.library_item_id) === "changed" && <span className="text-xs text-warning">{who.name || who.role} changed since the cast and places OK. Approve them again in the cast below before anything new is made with them. Nothing made so far changes.</span>}
          <span className="text-xs text-muted">Voices play here free.{clone ? ` A new clone costs ${clone}, once.` : ""}</span>
        </div>
      </div>
      {still && h.state !== "making" && !lookOnly && (
        <div className="flex flex-col items-start gap-2">
          {remaking ? (
            <div className="flex flex-col items-start gap-2 rounded-lg border border-border bg-surface p-3 text-sm">
              <span>
                Makes the presenter again: the still, then all {h.pieces.length - 1} piece{h.pieces.length === 2 ? "" : "s"} of the narration from it. The presenter you have now stays until the new one is made, and "Use the earlier presenter" brings it back, free.
              </span>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" busy={remake.isPending} onClick={() => remake.mutate()}>
                  Make it again <span className="font-normal text-muted">· {upTo(head, still.credits)}</span>
                </Button>
                <Button variant="ghost" onClick={() => setRemaking(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button variant="ghost" icon={RefreshCw} onClick={() => setRemaking(true)}>
                Make the presenter again…
              </Button>
              {hasEarlier && (
                <Button variant="ghost" busy={back.isPending} onClick={() => back.mutate()}>
                  Use the earlier presenter <span className="font-normal text-muted">· free</span>
                </Button>
              )}
            </div>
          )}
        </div>
      )}
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold">How the presenter appears</h3>
        <div role="radiogroup" aria-label="How the presenter appears" className={`flex flex-wrap items-start ${phone ? "gap-2" : "gap-3"}`}>
          {WAYS.map((w) => (
            <button key={w.id} type="button" role="radio" aria-checked={w.id === now} disabled={choose.isPending || head === undefined || lookOnly || !settable} onClick={() => w.id !== now && choose.mutate(w.id)} className={`flex flex-col gap-1 text-left ${phone ? "w-[108px]" : "w-[150px]"}`}>
              <img src={`/api/presenter-ways/${w.id}.jpg`} alt="" className={`${phone ? "h-[144px] w-[108px]" : "h-[200px] w-[150px]"} rounded-md bg-black object-cover ${w.id === now ? "outline-2 outline-offset-2 outline-accent" : ""}`} />
              <span className="text-sm font-semibold">{w.title}</span>
              <span className="text-xs text-muted">{w.made}</span>
            </button>
          ))}
        </div>
      </div>
      {!settable && settings.isFetched && <p className="text-xs text-muted">This video uses its style’s choice for now. Picking another way here comes with the presenter setting.</p>}
      {!phone && (
        <p className="flex items-start gap-2 rounded-lg bg-surface-2 px-3 py-2.5 text-sm">
          <CircleHelp size={14} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0 text-muted" />
          The style sets the start: UGC talks to camera, Dr. Pickle sits in the corner, and moving scripts act in the story. Any mix works. The director says its pick in the treatment; change it here or in the chat.
        </p>
      )}
    </section>
  );
}
