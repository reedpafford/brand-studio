import { useEffect, useMemo, useRef, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useToast } from "../toast";
import { useBrands } from "../shell/useBrands";
import { Sparkles } from "lucide-react";
import { Button, TextArea } from "../components";
import { ActionBar } from "../shell/ActionBar";
import { useMedia } from "../useMedia";
import { BrandPieces, useBrandPieces, type Piece } from "./BrandPieces";
import { ImproveDialog } from "./Improve";
import { History, isRendering, useJobs } from "./History";
import { ModelPicker } from "./ModelPicker";
import { blockedReason, clipCredits, defaultSettings, fit, mentionsMoment, type Model, type Settings } from "./logic";

const MAX_PROMPT = 2000;

/** The value, once it has stopped changing for a moment. */
function useDebounced<T>(value: T, ms = 400) {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}

export function ClipPage() {
  const models = useQuery({
    queryKey: ["models"],
    queryFn: async () => ((await api.GET("/models")).data ?? []).filter((m) => m.kind === "video"),
  });
  const list = models.data;
  if (models.isPending) return <p className="p-6 text-muted">Loading…</p>;
  if (!list || list.length === 0) return <p role="alert" className="p-6 text-danger">No video models are available.</p>;
  return <Studio models={list} />;
}

function Studio({ models }: { models: Model[] }) {
  const brandId = Number(useParams().brandId);
  const [params] = useSearchParams();
  const { data: brands } = useBrands();
  const brand = brands?.find((b) => b.id === brandId);
  const toast = useToast();
  const rail = useMedia("(min-width: 1024px)");
  const promptBox = useRef<HTMLTextAreaElement>(null);
  const first = models.find((m) => m.default) ?? models[0];
  const [model, setModel] = useState(first);
  const [settings, setSettings] = useState<Settings>(defaultSettings(first));
  const [prompt, setPrompt] = useState(params.get("prompt") ?? "");
  const [picked, setPicked] = useState<Piece[]>([]);
  const [dismissed, setDismissed] = useState<string[]>([]);
  const [sent, setSent] = useState("");
  // Improve prompt: the prompt that was there before (for Undo improve), and whether the box still holds Claude's text.
  const [improving, setImproving] = useState(false);
  const [improved, setImproved] = useState(false);
  const [before, setBefore] = useState<string | null>(null);
  const { pieces, screens, isPending } = useBrandPieces(brandId);
  const jobs = useJobs();
  const allowance = useQuery({
    queryKey: ["allowance"],
    queryFn: async () => (await api.GET("/credits/me")).data ?? null,
  });
  // Chosen pieces = what you picked, plus the character from the address, plus screens whose
  // "always used for" moment the prompt mentions (marked ★). Removing any of them keeps it out.
  const wantedCharacter = `character-${params.get("character")}`;
  const chosen = useMemo(() => {
    const auto = screens.flatMap((sc) => {
      const moment = sc.moments.find((m) => mentionsMoment(prompt, m));
      const piece = pieces.find((p) => p.key === sc.key);
      return moment && piece ? [{ ...piece, auto: moment }] : [];
    });
    const fromAddress = pieces.filter((p) => p.key === wantedCharacter);
    const all = [...fromAddress, ...picked, ...auto];
    return all.filter((p, i) => !dismissed.includes(p.key) && all.findIndex((x) => x.key === p.key) === i);
  }, [prompt, screens, pieces, picked, dismissed, wantedCharacter]);

  const ids = (type: Piece["type"]) => chosen.filter((p) => p.type === type).map((p) => p.id);
  const maxRefs = model.max_reference_images;

  const queryClient = useQueryClient();
  const body: components["schemas"]["ClipIn"] = {
    brand_id: brandId,
    model_id: model.id,
    prompt: prompt.trim(),
    aspect_ratio: settings.aspect,
    duration: settings.duration,
    resolution: settings.resolution,
    generate_audio: true,
    character_ids: ids("character"),
    place_ids: ids("place"),
    prop_ids: ids("prop"),
    screen_ids: ids("screen"),
    skip_screen_ids: dismissed.filter((k) => k.startsWith("screen-")).map((k) => Number(k.slice(7))),
    file_ids: [],
    improved,
  };
  // Ask the server what this would cost, and whether this person may spend it. Nothing is queued.
  const settledBody = useDebounced(body);
  const estimate = useQuery({
    queryKey: ["estimate", settledBody],
    enabled: settledBody.prompt.length >= 8 && !isPending,
    retry: false,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await api.POST("/clips/estimate", { body: settledBody });
      if (!data) throw new Error(errorText(error));
      return data;
    },
  });
  const credits = estimate.data?.credits ?? clipCredits(model, settings);
  const generate = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.POST("/clips", { body });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => {
      setSent(JSON.stringify(body));
      toast("Clip queued. It will show in History.");
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["allowance"] });
    },
  });

  const reason = blockedReason({ prompt, loading: isPending, tooMany: chosen.length > maxRefs, maxRefs, rendering: isRendering(jobs.data), noEstimate: !estimate.data && !estimate.error, refused: estimate.error?.message, alreadySent: sent === JSON.stringify(body) });

  // Try again: put a failed clip's prompt, settings and brand pieces back. Nothing is sent until Generate.
  const tryAgain = async (jobId: number) => {
    const { data } = await api.GET("/clips/{job_id}/request", { params: { path: { job_id: jobId } } });
    if (!data) return toast("Could not load that clip's settings.");
    const old = models.find((m) => m.id === data.model_id) ?? model;
    const keys = [
      ...data.character_ids.map((id) => `character-${id}`),
      ...data.place_ids.map((id) => `place-${id}`),
      ...data.prop_ids.map((id) => `prop-${id}`),
      ...data.screen_ids.map((id) => `screen-${id}`),
    ];
    setModel(old);
    setSettings(fit(old, { aspect: data.aspect_ratio, duration: data.duration, resolution: data.resolution }).settings);
    setPrompt(data.prompt);
    setPicked(keys.flatMap((k) => pieces.find((p) => p.key === k) ?? []));
    setDismissed(data.skip_screen_ids.map((id) => `screen-${id}`));
    toast("Brought back that clip's prompt and settings. Press Generate to try again.");
  };

  const switchModel = (m: Model) => {
    const { settings: next, notes } = fit(m, settings);
    setModel(m);
    setSettings(next);
    if (notes.length) toast(notes.join(" "));
  };
  const seg = (on: boolean) => `min-h-control min-w-16 flex-1 rounded-md border px-3 font-medium ${on ? "border-accent bg-accent-soft text-accent-text" : "border-border-strong bg-surface-2 hover:bg-surface-3"}`;
  const allowanceLine = allowance.data && (
    <p className="text-sm tabular-nums text-muted">
      This week: {Math.round(allowance.data.quick_clip_credits_used)} of {Math.round(allowance.data.quick_clip_credits_allowed)} credits
    </p>
  );
  const footer = (
    <div className="space-y-1">
      <Button
        price={credits}
        busy={generate.isPending}
        disabled={reason !== null}
        reason={reason}
        onClick={() => generate.mutate()}
        className="w-full"
      >
        Generate
      </Button>
      {generate.isError && <p role="alert" className="text-center text-sm text-danger">{generate.error.message}</p>}
    </div>
  );

  return (
    <main className="mx-auto grid max-w-content gap-6 p-4 sm:p-6 lg:grid-cols-[400px_1fr]">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-1 lg:col-span-2">
        <div>
          <p className="type-eyebrow text-muted">{brand?.name}</p>
          <h1 className="type-page">Quick clip</h1>
        </div>
        {allowanceLine}
      </div>
      <section aria-label="Clip settings" className="flex flex-col lg:self-start lg:rounded-xl lg:border lg:border-border lg:bg-surface lg:shadow-card">
        <div className="space-y-5 lg:p-5">
          <div className="space-y-1">
            <div className="text-sm font-medium">Model</div>
            <ModelPicker models={models} value={model} onChange={switchModel} />
          </div>
          <TextArea
            ref={promptBox}
            label="What happens"
            rows={6}
            maxLength={MAX_PROMPT}
            counter={`${prompt.length} / ${MAX_PROMPT.toLocaleString()}`}
            hint="Who's in it, what happens, how the camera moves."
            value={prompt}
            onChange={(e) => {
              setPrompt(e.target.value);
              setImproved(false);
            }}
          />
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" icon={Sparkles} disabled={prompt.trim().length < 8} reason={prompt.trim().length < 8 ? "Describe the clip first (8 or more characters)" : null} onClick={() => setImproving(true)}>
              Improve prompt
            </Button>
            {before !== null && (
              <Button
                variant="ghost"
                onClick={() => {
                  setPrompt(before);
                  setImproved(false);
                  setBefore(null);
                }}
              >
                Undo improve
              </Button>
            )}
          </div>
          {improving && (
            <ImproveDialog
              body={body}
              onClose={() => setImproving(false)}
              onUse={(text) => {
                setBefore(prompt);
                setPrompt(text);
                setImproved(true);
                setImproving(false);
              }}
            />
          )}
          <BrandPieces
            all={pieces}
            chosen={chosen}
            max={maxRefs}
            onAdd={(p) => {
              setPicked([...picked, p]);
              setDismissed(dismissed.filter((k) => k !== p.key));
            }}
            onRemove={(key) => {
              setPicked(picked.filter((c) => c.key !== key));
              setDismissed([...dismissed, key]);
            }}
          />
          <fieldset className="space-y-1">
            <legend className="text-sm font-medium">Shape</legend>
            <div className="flex flex-wrap gap-2">
              {model.aspect_ratios.map((a) => (
                <button key={a} type="button" aria-pressed={a === settings.aspect} className={seg(a === settings.aspect)} onClick={() => setSettings({ ...settings, aspect: a })}>
                  {a}
                </button>
              ))}
            </div>
          </fieldset>
          <label className="block">
            <span className="flex justify-between text-sm font-medium">
              Length <span className="font-normal tabular-nums">{settings.duration} s</span>
            </span>
            <input type="range" className="block h-control w-full accent-accent" min={model.duration?.min ?? 1} max={model.duration?.max ?? 30} value={settings.duration} onChange={(e) => setSettings({ ...settings, duration: Number(e.target.value) })} />
            <span className="flex justify-between text-sm tabular-nums text-muted">
              <span>{model.duration?.min ?? 1} s</span>
              <span>{model.duration?.max ?? 30} s</span>
            </span>
          </label>
          <fieldset className="space-y-1">
            <legend className="text-sm font-medium">Quality</legend>
            <div className="flex flex-wrap gap-2">
              {model.resolutions.map((r) => (
                <button key={r} type="button" aria-pressed={r === settings.resolution} className={seg(r === settings.resolution)} onClick={() => setSettings({ ...settings, resolution: r })}>
                  {r}
                </button>
              ))}
            </div>
          </fieldset>
        </div>
        {/* Desktop: the page scrolls, and the footer sticks to the bottom of the window inside the panel, never over a field. Phone: it is the action bar. */}
        {rail ? <div className="sticky bottom-0 rounded-b-xl border-t border-border bg-surface p-5 shadow-[0_-10px_12px_-10px_rgb(0_0_0/0.18)]">{footer}</div> : <ActionBar phone>{footer}</ActionBar>}
      </section>
      <section aria-label="History" className="space-y-3">
        <h2 className="type-section">History</h2>
        <History brandName={brand?.name ?? "brand"} onTryAgain={tryAgain} onStart={() => promptBox.current?.focus()} />
      </section>
    </main>
  );
}
