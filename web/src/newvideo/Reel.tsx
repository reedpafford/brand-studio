import { useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, Copy, Upload } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import { Button } from "../components";
import { mmss } from "../freestyle/FromScript";
import { sentTo } from "../freestyle/useFreestyle";
import { postUpload, useReelImport } from "../scripts/ReelImport";
import { ActionBar } from "../shell/ActionBar";
import { useBrands } from "../shell/useBrands";
import type { Look } from "./Cards";
import { FixedChip } from "./Chips";
import { Press, box, row } from "./NewVideoPage";
import { useEstimate, type Estimate } from "./useNewVideo";

type Mode = "copy" | "structure" | "look";
const MODES: { id: Mode; name: string }[] = [
  { id: "copy", name: "Copy it shot by shot" },
  { id: "structure", name: "Just its structure" },
  { id: "look", name: "Just its look" },
];

/** New video › Use a reel (S2-07; S-gaps-01, 2): upload a reel; Copy it shot by shot or Just its structure read it (its own
 *  "up to") and the director makes the video from the script it writes; Just its look makes your words in its look. */
export function Reel({ brandId, owner, folder, seg, rail, format, formatName, look, broll }: { brandId: number; owner: boolean; folder: number | null; seg: ReactNode; rail: boolean; format: string; formatName?: string; look?: Look; broll: string | null }) {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const scriptId = Number(params.get("reel")) || 0;
  const brand = useBrands().data?.find((b) => b.id === brandId);
  const reel = useReelImport(scriptId).data;
  const [mode, setMode] = useState<Mode>("copy");
  const [name, setName] = useState("");
  const [words, setWords] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const upload = useMutation({
    mutationFn: async (f: File) => {
      const { data, error } = await postUpload("/scripts/import/upload", { brand_id: String(brandId) }, f);
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (d) => setParams((p) => (p.set("reel", String(d.script_id)), p), { replace: true }),
  });
  const readPrice = useQuery({
    queryKey: ["reel-estimate", scriptId, reel?.status],
    enabled: !!scriptId && reel?.status === "ready",
    queryFn: async () => (await api.GET("/freestyles/reel/estimate", { params: { query: { script_id: scriptId } } })).data ?? null,
  }).data;
  const ownWords = mode === "look" && words.trim() ? { type: format, look: look?.id ?? "house", shape: "9:16" as const, brand_id: brandId, broll_look: broll, text: words.trim() } : null;
  const lookEst = useEstimate(ownWords).data;
  const go = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/freestyles/reel", { body: { script_id: scriptId, mode, type: format, look: look?.id, shape: "9:16", folder_id: folder, broll_look: broll, ...(mode === "look" ? { text: words.trim() } : {}) } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (fs) => navigate(sentTo(fs, owner, brandId)),
  });
  // A silent reel has nothing to read, but Just its look only needs its picture (S-gaps-01).
  const silent = reel?.problem_code === "no_sound";
  const ready = reel?.status === "ready" || (mode === "look" && (reel?.status === "done" || silent));
  const readEst: Estimate | undefined = readPrice ? { credits: readPrice.credits, usd: readPrice.usd, held: "", budget: null } : undefined;
  const est = mode === "look" ? lookEst : readEst;
  const disabled = !ready || (mode === "look" && !words.trim());
  const press = <Press owner={owner} est={est} busy={go.isPending} disabled={disabled} onClick={() => go.mutate()} go={mode === "look" ? "Make it" : "Watch it and write the script"} wide={!rail} />;
  const file = (
    <input ref={input} type="file" accept="video/mp4,video/quicktime,.mp4,.mov" aria-label="Choose a reel" tabIndex={-1} className="sr-only" onChange={(e) => {
      const f = e.target.files?.[0];
      if (f) {
        setName(f.name);
        upload.mutate(f);
      }
      e.target.value = "";
    }} />
  );
  const problem = reel?.problem && !(silent && mode === "look") ? (silent ? `${reel.problem} Just its look can still use it.` : reel.problem) : null;
  const status = !scriptId ? null : !reel || reel.status === "preparing" ? "Getting the reel ready…" : problem;
  const picked = scriptId ? (
    <div className="flex items-start gap-4 px-4 py-3.5">
      <div className="relative h-[128px] w-[72px] shrink-0 overflow-hidden rounded-md bg-surface-3">
        {reel?.video_file_id && <video src={fileUrl(reel.video_file_id)} muted preload="metadata" className="size-full object-cover" />}
        {reel?.seconds ? <span className="absolute bottom-1 left-1 rounded-sm bg-black/60 px-1 text-xs text-white">{mmss(reel.seconds)}</span> : null}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <span className="font-semibold">{name || "The reel"}</span>
        {mode !== "look" && <span className="text-sm text-muted">{[reel?.seconds ? mmss(reel.seconds) : null, "uploaded", `the director watches and listens to it, then writes a script that keeps its shape with ${brand?.name ?? "the brand"}’s product`].filter(Boolean).join(" · ")}</span>}
        <div role="radiogroup" aria-label="What to take from it" className="flex flex-wrap gap-2">
          {MODES.map((m) => (
            <button key={m.id} type="button" role="radio" aria-checked={mode === m.id} onClick={() => setMode(m.id)} className={`inline-flex h-11 lg:h-[26px] items-center gap-1.5 rounded-sm border px-2.5 text-xs font-medium ${mode === m.id ? "border-[#c9ccf6] bg-accent-soft text-accent-text" : "border-border-button bg-surface hover:bg-surface-2"}`}>
              {mode === m.id && (m.id === "copy" ? <Copy size={12} aria-hidden /> : <Check size={12} aria-hidden />)}
              {m.name}
            </button>
          ))}
        </div>
        {mode === "look" ? (
          <>
            <span className="text-sm">The director studies the reel’s look: camera, light, colour and cut pace. It makes your script in that look. The reel’s words and story aren’t used.</span>
            <label className="flex flex-col rounded-lg border border-border px-2.5 py-2">
              <span className="text-xs text-muted">Your script</span>
              <textarea value={words} onChange={(e) => setWords(e.target.value)} rows={2} maxLength={5000} className="field-sizing-content resize-none bg-transparent font-script text-sm leading-[1.6] outline-none!" />
            </label>
          </>
        ) : (
          <span className="text-xs text-muted">Live-action parts are swapped for the brand’s ending.</span>
        )}
        {status && <span role="status" className={`text-sm ${problem ? "text-danger" : "text-muted"}`}>{status}</span>}
      </div>
    </div>
  ) : (
    <div className="flex flex-col items-start gap-2 px-4 py-6">
      <p className="text-sm text-muted">Upload a reel, MP4 or MOV up to 90 seconds. The director watches and listens to it, then adapts it for {brand?.name ?? "the brand"}.</p>
      <Button variant="secondary" icon={Upload} busy={upload.isPending} onClick={() => input.current?.click()}>
        Upload a reel
      </Button>
    </div>
  );
  const error = [upload, go].find((m) => m.isError)?.error?.message;
  // S2-07 draws nothing under the read's press; Just its look says what its price covers.
  const under = mode === "look" ? <span className="text-xs text-muted">Watching the reel is free. The price includes the director’s time studying it.</span> : null;
  if (!rail)
    return (
      <div className="flex flex-col gap-3">
        {file}
        <div className="rounded-xl border border-border-strong bg-surface">{picked}</div>
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        <ActionBar phone>
          <div className="flex flex-col gap-1">
            {press}
            {est && under}
          </div>
        </ActionBar>
      </div>
    );
  return (
    <>
      {file}
      <div className={box}>
        <div className="px-3 pt-2.5">{seg}</div>
        {picked}
        <div className={row}>
          <button type="button" aria-label="Upload another reel" onClick={() => input.current?.click()} className="grid size-8 place-items-center rounded-md text-muted hover:bg-surface-2">
            <Upload size={14} aria-hidden />
          </button>
          <FixedChip label="Format">{formatName ?? format}</FixedChip>
          {mode === "look" ? <FixedChip label="Look">from the reel</FixedChip> : <FixedChip label="Style">{look?.name}</FixedChip>}
          <span className="flex-1" />
          {press}
        </div>
      </div>
      <div className="flex min-h-6 items-center px-1 py-1.5">{est && !disabled && under}</div>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
    </>
  );
}
