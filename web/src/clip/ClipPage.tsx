import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useToast } from "../toast";
import { useBrands } from "../shell/useBrands";
import { btnPrimary, input, pageTitle } from "../ui";
import { BrandPieces, useBrandPieces, type Piece } from "./BrandPieces";
import { useMe } from "../auth/useMe";
import { History, isRendering, useJobs } from "./History";
import { ModelPicker } from "./ModelPicker";
import { blockedReason, clipCredits, defaultSettings, fit, mentionsMoment, type Model, type Settings } from "./logic";

const MAX_PROMPT = 2000;

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
  const { pieces, screens, isPending } = useBrandPieces(brandId);
  const { data: me } = useMe();
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

  const credits = useMemo(() => clipCredits(model, settings), [model, settings]);
  const maxRefs = model.max_reference_images;
  // The weekly allowance is for editors; the owner's clips need no ask.
  const left = allowance.data && me?.role !== "owner" ? allowance.data.quick_clip_credits_allowed - allowance.data.quick_clip_credits_used : null;
  const reason = blockedReason({ prompt, loading: isPending, tooMany: chosen.length > maxRefs, maxRefs, credits, left, rendering: isRendering(jobs.data) });

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
      <section aria-label="Clip settings" className="space-y-4 lg:self-start lg:rounded-md lg:border lg:border-border lg:bg-surface lg:p-6">
        <div className="space-y-1 text-sm">
          <div className="font-medium">Model</div>
          <ModelPicker models={models} value={model} onChange={switchModel} />
        </div>
        <label className="block text-sm">
          <span className="flex justify-between font-medium">
            Prompt <span className="font-normal text-muted">{prompt.length}/{MAX_PROMPT.toLocaleString()}</span>
          </span>
          <textarea className={input} rows={6} maxLength={MAX_PROMPT} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          <span className="text-muted">Who's in it, what happens, how the camera moves.</span>
        </label>
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
          <input type="range" className="w-full" min={model.duration?.min ?? 1} max={model.duration?.max ?? 30} value={settings.duration} onChange={(e) => setSettings({ ...settings, duration: Number(e.target.value) })} />
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
        {left !== null && <p className="text-sm text-muted">Quick clips this week: {allowance.data?.quick_clip_credits_used} of {allowance.data?.quick_clip_credits_allowed} credits used.</p>}
        <div className="fixed inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom))] z-10 space-y-1 md:bottom-0 border-t border-border bg-surface p-4 shadow-md lg:sticky lg:bottom-0 lg:border-0 lg:p-0 lg:shadow-none">
          <button className={`${btnPrimary} min-h-11 w-full`} disabled={reason !== null}>
            Generate · {credits} credits
          </button>
          {reason && <p className="text-sm text-muted">{reason}</p>}
        </div>
      </section>
      <section aria-label="History" className="space-y-3">
        <h2 className="text-[length:var(--text-md)] font-semibold">History</h2>
        <History brandName={brand?.name ?? "brand"} />
      </section>
    </main>
  );
}
