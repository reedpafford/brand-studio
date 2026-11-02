import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe, Image } from "lucide-react";
import { api, errorText, must } from "../api/client";
import type { components } from "../api/schema";
import { Banner, Button, Field, pressLabel, useToast } from "../components";
import { BrandAction } from "./BrandPage";

type Read = components["schemas"]["app__routes__site_read__ReadOut"];
const WEB = /^https?:\/\/[^\s/]+\.[^\s]+$/i;
const MARK = { new: "New product", fills: "Fills an empty description", have: "Already in your products" } as const;

/** Import from website (flows BR2, v5 F_BrandImport), the owner's: read the brand's site, review what it found (nothing
 *  saved yet), then save the ticked ones with Undo. It reopens on the brand's last read, its address filled, so "Read it
 *  again" is one press. `waitFor` holds Save while the Look form has unsaved changes. */
export function SiteImport({ brandId, waitFor, onSaved, onCancel }: { brandId: number; waitFor: string | null; onSaved: () => void; onCancel: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [url, setUrl] = useState<string | null>(null); // null: the last read's address
  const [bad, setBad] = useState(false);
  const [jobId, setJobId] = useState<number | null>(null); // null: the last read
  const [ticks, setTicks] = useState<{ logo: boolean; colours: string[]; products: number[] } | null>(null);
  const [noLogo, setNoLogo] = useState(false);
  const price = useQuery({ queryKey: ["site-read-estimate", brandId], queryFn: () => must(api.GET("/brands/{brand_id}/site-read/estimate", { params: { path: { brand_id: brandId } } })).then((r) => r.data!.credits) });
  const latest = useQuery({
    enabled: jobId === null,
    queryKey: ["site-read", brandId, "latest"],
    retry: false,
    queryFn: async () => {
      const { data, response } = await api.GET("/brands/{brand_id}/site-read/latest", { params: { path: { brand_id: brandId } } });
      if (response.status === 404) return null; // never read
      if (!data) throw new Error("load");
      return data;
    },
    refetchInterval: (q) => (q.state.data?.status === "reading" ? 1500 : false),
  });
  const start = useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST("/brands/{brand_id}/site-read", { params: { path: { brand_id: brandId } }, body: { url: address.trim() } });
      if (response.status === 422) throw new Error("Paste a web address (https://…)"); // the server's own check of the address
      if (!response.ok) throw new Error(errorText(error));
      return data!.id;
    },
    onSuccess: (id) => {
      setJobId(id);
      setTicks(null);
      setNoLogo(false);
    },
  });
  const one = useQuery({
    enabled: jobId !== null,
    queryKey: ["site-read", brandId, jobId],
    queryFn: () => must(api.GET("/brands/{brand_id}/site-read/{job_id}", { params: { path: { brand_id: brandId, job_id: jobId! } } })).then((r) => r.data!),
    refetchInterval: (q) => (q.state.data?.status === "reading" ? 1500 : false),
  });
  const r: Read | null | undefined = jobId === null ? latest.data : one.data;
  const address = url ?? r?.url ?? "";
  const readId = jobId ?? r?.id; // the read just started, else the last one
  // Everything found starts ticked, except what the brand already has.
  const tick = ticks ?? (r?.status === "done" ? { logo: !!r.found.logo_url, colours: r.found.colours.filter((c) => !r.have_colours.includes(c)), products: r.found.products.map((_, i) => i).filter((i) => r.found.products[i].mark !== "have") } : null);
  const refresh = () => Promise.all(["brands", "library", "site-read"].map((k) => queryClient.invalidateQueries({ queryKey: [k] })));
  const save = useMutation({
    mutationFn: () => must(api.POST("/brands/{brand_id}/site-read/{job_id}/save", { params: { path: { brand_id: brandId, job_id: readId! } }, body: { ...tick!, logo: tick!.logo && !noLogo } })).then((s) => s.data!),
    onSuccess: async (s) => {
      const id = readId!;
      await refresh();
      onSaved();
      const parts = [s.logo && "the logo", s.colours_added > 0 && `${s.colours_added} colour${s.colours_added === 1 ? "" : "s"}`, s.products_made > 0 && `${s.products_made} product${s.products_made === 1 ? "" : "s"}`, s.products_filled > 0 && `${s.products_filled} description${s.products_filled === 1 ? "" : "s"}`].filter(Boolean);
      const said = [parts.length ? `Saved ${parts.join(", ")}.` : "Nothing new to save.", ...s.problems].join(" "); // "Couldn't get the logo from the site." The rest is saved.
      toast(said, async () => {
        await must(api.POST("/brands/{brand_id}/site-read/{job_id}/undo", { params: { path: { brand_id: brandId, job_id: id } } })).catch((e: Error) => toast(e.message, undefined, "error"));
        await refresh();
        onSaved();
      });
    },
  });
  const go = () => {
    if (!WEB.test(address.trim())) return setBad(true);
    start.mutate();
  };
  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const reviewing = r?.status === "done" && !!tick;
  const count = reviewing ? Number(tick.logo && !noLogo) + tick.colours.length + tick.products.length : 0;
  const reading = r?.status === "reading" || start.isPending || (jobId !== null && one.isPending);
  const refused = start.isError ? start.error.message : null;
  const priceText = price.data !== undefined ? ` · ${pressLabel(price.data, "estimate")}` : ""; // rule 32: a press says "up to"

  let found: ReactNode = null;
  if (reading) {
    found = (
      <p role="status" className="text-sm text-muted">
        Reading the site…
      </p>
    );
  } else if (r && (r.status === "failed" || r.status === "empty")) {
    found = <Banner tone={r.status === "failed" ? "danger" : "warning"} title={r.reason}>{r.status === "failed" ? "Read it again, or fill in the Look by hand." : undefined}</Banner>;
  } else if (r?.status === "saved") {
    found = <p className="text-sm text-muted">The last read is saved. Read it again to see what's on the site now.</p>;
  } else if (reviewing) {
    const f = r.found;
    found = (
      <div className="space-y-3 rounded-lg border border-border p-4">
        <p className="text-xs text-muted">Tick what to keep. Nothing is saved yet. Colours are added to yours, never replacing them.</p>
        {f.logo_url && (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Logo</legend>
            <div className="flex items-center gap-3">
              {noLogo ? (
                <span aria-hidden className="grid size-12 shrink-0 place-items-center rounded-md border border-border bg-surface-2 text-muted">
                  <Image className="size-5" />
                </span>
              ) : (
                <img src={`/api/brands/${brandId}/site-read/${readId}/logo`} alt="The logo found on the site" onError={() => setNoLogo(true)} className="size-12 shrink-0 rounded-md border border-border bg-surface-2 object-contain" />
              )}
              {noLogo ? (
                <p className="text-sm text-muted">Couldn't get the logo from the site. Add one by hand on the Look.</p>
              ) : (
                <label className="flex min-h-control items-center gap-2.5 lg:min-h-9">
                  <input type="checkbox" className="size-5 sm:size-4" checked={tick.logo} onChange={() => setTicks({ ...tick, logo: !tick.logo })} />
                  Logo found on the site
                </label>
              )}
            </div>
          </fieldset>
        )}
        {f.colours.length > 0 && (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Colours</legend>
            <ul className="flex flex-col gap-1 sm:flex-row sm:flex-wrap sm:gap-4">
              {f.colours.map((c) => {
                const have = r.have_colours.includes(c);
                return (
                  <li key={c} className="flex items-center gap-2">
                    <span aria-hidden className="size-6 shrink-0 rounded-sm border border-border" style={{ background: c }} />
                    <label className="flex min-h-control items-center gap-2.5 lg:min-h-9">
                      {have ? <span className="size-5 sm:size-4" aria-hidden /> : <input type="checkbox" className="size-5 sm:size-4" checked={tick.colours.includes(c)} onChange={() => setTicks({ ...tick, colours: toggle(tick.colours, c) })} />}
                      <span className="font-mono text-sm">{c}</span>
                      {have && <span className="text-xs text-muted">Already in your colours</span>}
                    </label>
                  </li>
                );
              })}
            </ul>
          </fieldset>
        )}
        {f.products.length > 0 && (
          <fieldset className="space-y-1">
            <legend className="text-sm font-medium">Products</legend>
            <ul>
              {f.products.map((p, i) => {
                const mark: keyof typeof MARK = p.mark === "fills" || p.mark === "have" ? p.mark : "new";
                return (
                  <li key={i}>
                    <label className="flex min-h-control items-start gap-2.5 py-1.5 lg:min-h-9">
                      {mark === "have" ? <span className="mt-0.5 size-5 shrink-0 sm:size-4" aria-hidden /> : <input type="checkbox" className="mt-0.5 size-5 shrink-0 sm:size-4" checked={tick.products.includes(i)} onChange={() => setTicks({ ...tick, products: toggle(tick.products, i) })} />}
                      <span className="min-w-0 flex-1">
                        <span className="break-words">{p.name}</span> <span className="text-xs text-muted">{MARK[mark]}</span>
                        {p.short_description && <span className="block break-words text-xs text-muted">{p.short_description}</span>}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </fieldset>
        )}
        {save.isError && <p role="alert" className="text-sm text-danger">{save.error.message}</p>}
      </div>
    );
  }

  return (
    <section aria-label="Import from website" className="max-w-[640px] space-y-4">
      <div>
        <h2 className="text-[15px] font-semibold">Import from website</h2>
        <p className="text-xs text-muted">Reads the logo, colours and products from the brand's site. You pick what to keep.</p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="min-w-0 flex-1">
          <Field
            label="Paste the brand's website"
            type="url"
            inputMode="url"
            placeholder="https://"
            value={address}
            error={bad ? "Paste a web address (https://…)" : (refused ?? undefined)}
            onChange={(e) => {
              setUrl(e.target.value);
              setBad(false);
              start.reset();
            }}
          />
        </div>
        <Button variant="secondary" icon={r ? undefined : Globe} busy={reading || price.isPending} onClick={go}>
          {r ? `Read it again${priceText}` : `Read the site${priceText}`}
        </Button>
      </div>
      {found}
      <BrandAction>
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        {reviewing && (
          <Button busy={save.isPending} disabled={count === 0 || !!waitFor} reason={waitFor ?? (count === 0 ? "Tick something to save" : undefined)} onClick={() => save.mutate()}>
            Save {count} picked
          </Button>
        )}
      </BrandAction>
    </section>
  );
}
