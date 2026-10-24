import { useEffect, useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useToast } from "../toast";
import { useBrands } from "../shell/useBrands";
import { btnPrimary, btnSecondary, input, pageTitle } from "../ui";
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
  // Ask the server what this would cost and whether Reed must approve it. Nothing is queued.
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
      toast(estimate.data?.needs_owner_approval ? "Sent to Reed for approval. It will show in History." : "Clip queued. It will show in History.");
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
  const seg = (on: boolean) => `min-h-11 rounded-sm border px-3 sm:min-h-9 ${on ? "border-accent bg-accent-soft text-accent-text" : "border-border-strong bg-surface"}`;

  return (
    <main className="mx-auto grid max-w-6xl gap-6 p-4 pb-32 sm:p-6 lg:grid-cols-[360px_1fr]">
      <h1 className={`${pageTitle} lg:col-span-2`}>Quick clip · {brand?.name}</h1>
      <section aria-label="Clip settings" className="space-y-4 lg:sticky lg:top-4 lg:flex lg:max-h-[calc(100vh-11.5rem)] lg:flex-col lg:self-start lg:space-y-0 lg:rounded-md lg:border lg:border-border lg:bg-surface lg:p-6">
        {/* On desktop the fields scroll inside the panel and Generate stays under them, so it never covers a field. */}
        <div className="space-y-4 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:pb-4">
        <div className="space-y-1 text-sm">
          <div className="font-medium">Model</div>
          <ModelPicker models={models} value={model} onChange={switchModel} />
        </div>
        <label className="block text-sm">
          <span className="flex justify-between font-medium">
            Prompt <span className="font-normal text-muted">{prompt.length}/{MAX_PROMPT.toLocaleString()}</span>
          </span>
          <textarea className={input} rows={6} maxLength={MAX_PROMPT} value={prompt} onChange={(e) => { setPrompt(e.target.value); setImproved(false); }} />
          <span className="text-muted">Who's in it, what happens, how the camera moves.</span>
        </label>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={`${btnSecondary} min-h-11 sm:min-h-9`} disabled={prompt.trim().length < 8} onClick={() => setImproving(true)}>
            ✦ Improve prompt
          </button>
          {before !== null && (
            <button
              type="button"
              className={`${btnSecondary} min-h-11 border-transparent sm:min-h-9`}
              onClick={() => {
                setPrompt(before);
                setImproved(false);
                setBefore(null);
              }}
            >
              Undo improve
            </button>
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
        <fieldset className="space-y-1 text-sm">
          <legend className="font-medium">Shape</legend>
          <div className="flex flex-wrap gap-2">
            {model.aspect_ratios.map((a) => (
              <button key={a} type="button" aria-pressed={a === settings.aspect} className={seg(a === settings.aspect)} onClick={() => setSettings({ ...settings, aspect: a })}>
                {a}
              </button>
            ))}
          </div>
        </fieldset>
        <label className="block text-sm">
          <span className="flex justify-between font-medium">
            Length <span className="font-normal">{settings.duration}s</span>
          </span>
          <input type="range" className="w-full accent-[var(--accent)]" min={model.duration?.min ?? 1} max={model.duration?.max ?? 30} value={settings.duration} onChange={(e) => setSettings({ ...settings, duration: Number(e.target.value) })} />
          <span className="flex justify-between text-muted">
            <span>{model.duration?.min ?? 1}s</span>
            <span>{model.duration?.max ?? 30}s</span>
          </span>
        </label>
        <fieldset className="space-y-1 text-sm">
          <legend className="font-medium">Quality</legend>
          <div className="flex flex-wrap gap-2">
            {model.resolutions.map((r) => (
              <button key={r} type="button" aria-pressed={r === settings.resolution} className={seg(r === settings.resolution)} onClick={() => setSettings({ ...settings, resolution: r })}>
                {r}
              </button>
            ))}
          </div>
        </fieldset>
        {allowance.data && <p className="text-sm text-muted">Quick clips this week: {allowance.data?.quick_clip_credits_used} of {allowance.data?.quick_clip_credits_allowed} credits used.</p>}
        </div>
        <div className="fixed inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom))] z-10 space-y-1 md:bottom-0 border-t border-border bg-surface p-4 shadow-md lg:static lg:shrink-0 lg:border-t lg:border-border lg:bg-surface lg:p-0 lg:pt-4 lg:shadow-none">
          <button className={`${btnPrimary} min-h-11 w-full`} disabled={reason !== null || generate.isPending} onClick={() => generate.mutate()}>
            {generate.isPending ? "Sending…" : `${estimate.data?.needs_owner_approval ? "Ask Reed to approve" : "Generate"} · ${credits} credits`}
          </button>
          {reason && <p className="text-sm text-muted">{reason}</p>}
          {!reason && estimate.data?.needs_owner_approval && <p className="text-sm text-warning">{estimate.data.reason}</p>}
          {generate.isError && <p role="alert" className="text-sm text-danger">{generate.error.message}</p>}
        </div>
      </section>
      <section aria-label="History" className="space-y-3">
        <h2 className="text-[length:var(--text-md)] font-semibold">History</h2>
        <History brandName={brand?.name ?? "brand"} onTryAgain={tryAgain} />
      </section>
    </main>
  );
}
