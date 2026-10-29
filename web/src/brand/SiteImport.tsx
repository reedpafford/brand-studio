import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe } from "lucide-react";
import { api, errorText, must } from "../api/client";
import type { components } from "../api/schema";
import { Badge, Banner, Button, Card, Field, creditsLabel, useToast } from "../components";
import { ActionBar } from "../shell/ActionBar";
import { useRail } from "../useMedia";

type Read = components["schemas"]["app__routes__site_read__ReadOut"];
const WEB = /^https?:\/\/[^\s/]+\.[^\s]+$/i;
const key = (name: string) => name.split(/\s+/).filter(Boolean).join(" ").toLowerCase(); // as the server matches products

/** Import from website (flows BR2), the owner's: read the brand's site, review what it found (nothing saved yet),
 *  then save the ticked ones with Undo. `waitFor` holds Save while the form below has unsaved changes. */
export function SiteImport({ brandId, waitFor, onSaved, onReviewing }: { brandId: number; waitFor: string | null; onSaved: () => void; onReviewing: (on: boolean) => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const rail = useRail();
  const [url, setUrl] = useState("");
  const [bad, setBad] = useState(false);
  const [jobId, setJobId] = useState<number | null>(null);
  const [logoBroke, setLogoBroke] = useState(false); // the site's picture didn't load here: name it instead
  const [ticks, setTicks] = useState<{ logo: boolean; colours: string[]; products: number[] } | null>(null);
  const price = useQuery({ queryKey: ["site-read-estimate", brandId], queryFn: () => must(api.GET("/brands/{brand_id}/site-read/estimate", { params: { path: { brand_id: brandId } } })).then((r) => r.data!.credits) });
  const props = useQuery({ queryKey: ["library", "prop", brandId], queryFn: async () => (await api.GET("/library/{kind}", { params: { path: { kind: "prop" }, query: { brand_id: brandId } } })).data ?? [] });
  const start = useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST("/brands/{brand_id}/site-read", { params: { path: { brand_id: brandId } }, body: { url: url.trim() } });
      if (response.status === 422) throw new Error("Paste a web address (https://…)"); // the server's own check of the address
      if (!response.ok) throw new Error(errorText(error));
      return data!.id;
    },
    onSuccess: (id) => {
      setJobId(id);
      setTicks(null);
    },
  });
  const read = useQuery({
    enabled: jobId !== null,
    queryKey: ["site-read", brandId, jobId],
    queryFn: () => must(api.GET("/brands/{brand_id}/site-read/{job_id}", { params: { path: { brand_id: brandId, job_id: jobId! } } })).then((r) => r.data!),
    refetchInterval: (q) => (q.state.data?.status === "reading" ? 1500 : false),
  });
  const r = read.data;
  const reviewing = jobId !== null && r?.status === "done";
  useEffect(() => onReviewing(reviewing), [reviewing, onReviewing]);
  // What a found product would do: new, fill an empty description, or nothing (it's already described).
  const productNote = (p: Read["found"]["products"][number]) => {
    const have = props.data?.find((x) => key(x.name) === key(p.name));
    return !have ? "new" : !have.short_description?.trim() && p.short_description.trim() ? "fills" : "has";
  };
  // Everything found starts ticked, except what the brand already has.
  const tick = ticks ?? (r?.status === "done" ? { logo: !!r.found.logo_url, colours: r.found.colours.filter((c) => !r.have_colours.includes(c)), products: r.found.products.map((_, i) => i).filter((i) => productNote(r.found.products[i]) !== "has") } : null);
  const refresh = () => Promise.all(["brands", "library", "site-read"].map((k) => queryClient.invalidateQueries({ queryKey: [k] })));
  const save = useMutation({
    mutationFn: () => must(api.POST("/brands/{brand_id}/site-read/{job_id}/save", { params: { path: { brand_id: brandId, job_id: jobId! } }, body: tick! })).then((s) => s.data!),
    onSuccess: async (s) => {
      await refresh();
      onSaved();
      const parts = [s.logo && "the logo", s.colours_added > 0 && `${s.colours_added} colour${s.colours_added === 1 ? "" : "s"}`, s.products_made > 0 && `${s.products_made} product${s.products_made === 1 ? "" : "s"}`, s.products_filled > 0 && `${s.products_filled} description${s.products_filled === 1 ? "" : "s"}`].filter(Boolean);
      const id = jobId!;
      const said = [parts.length ? `Saved ${parts.join(", ")}.` : "Nothing new to save.", ...s.problems].join(" "); // "Couldn't get the logo from the site." The rest is saved.
      toast(said, async () => {
        await must(api.POST("/brands/{brand_id}/site-read/{job_id}/undo", { params: { path: { brand_id: brandId, job_id: id } } })).catch((e: Error) => toast(e.message, undefined, "error"));
        await refresh();
        onSaved();
      });
      setJobId(null);
      setTicks(null);
    },
  });
  const again = () => {
    setJobId(null);
    setTicks(null);
    start.reset();
  };
  const go = () => {
    if (!WEB.test(url.trim())) return setBad(true);
    start.mutate();
  };
  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const count = tick ? Number(tick.logo) + tick.colours.length + tick.products.length : 0;
  const saveButton = (
    <Button busy={save.isPending} disabled={count === 0 || !!waitFor} reason={waitFor ?? (count === 0 ? "Tick something to save" : undefined)} onClick={() => save.mutate()}>
      Save the ticked ones
    </Button>
  );

  let body: ReactNode;
  if (r?.status === "reading" || (jobId !== null && read.isPending)) {
    body = (
      <p role="status" className="text-sm text-muted">
        Reading the site…
      </p>
    );
  } else if (r && (r.status === "failed" || r.status === "empty")) {
    body = (
      <Banner tone={r.status === "failed" ? "danger" : "warning"} title={r.reason} action={<Button variant="secondary" onClick={again}>Try again</Button>}>
        {r.status === "failed" ? "Or fill it in by hand below." : undefined}
      </Banner>
    );
  } else if (r?.status === "done" && tick) {
    const { found } = r;
    body = (
      <div className="space-y-4">
        <p className="text-sm text-muted">Tick what to keep. Nothing is saved yet. Colours are added to yours, never replacing them.</p>
        {found.logo_url && (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Logo</legend>
            <label className="flex min-h-control items-center gap-3">
              <input type="checkbox" className="size-5 sm:size-4" checked={tick.logo} onChange={() => setTicks({ ...tick, logo: !tick.logo })} />
              {logoBroke ? (
                <span className="min-w-0 break-all text-sm">The logo on the site ({found.logo_url.split("/").pop()})</span>
              ) : (
                <img src={found.logo_url} alt="The logo on the site" referrerPolicy="no-referrer" onError={() => setLogoBroke(true)} className="h-12 max-w-48 rounded-sm bg-surface-2 object-contain" />
              )}
            </label>
          </fieldset>
        )}
        {found.colours.length > 0 && (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Colours</legend>
            <ul className="flex flex-col gap-1 sm:flex-row sm:flex-wrap sm:gap-4">
              {found.colours.map((c) => {
                const have = r.have_colours.includes(c);
                return (
                  <li key={c}>
                    <label className="flex min-h-control items-center gap-3">
                      {have ? <span className="size-5 sm:size-4" aria-hidden /> : <input type="checkbox" className="size-5 sm:size-4" checked={tick.colours.includes(c)} onChange={() => setTicks({ ...tick, colours: toggle(tick.colours, c) })} />}
                      <span aria-hidden className="size-6 shrink-0 rounded-sm border border-border" style={{ background: c }} />
                      <span className="font-mono text-sm">{c}</span>
                      {have && <span className="text-sm text-muted">Already in your colours</span>}
                    </label>
                  </li>
                );
              })}
            </ul>
          </fieldset>
        )}
        {found.products.length > 0 && (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Products</legend>
            <ul className="space-y-2">
              {found.products.map((p, i) => {
                const note = productNote(p);
                return (
                  <li key={i}>
                    <label className="flex items-start gap-3">
                      {note === "has" ? <span className="mt-0.5 size-5 shrink-0 sm:size-4" aria-hidden /> : <input type="checkbox" className="mt-0.5 size-5 shrink-0 sm:size-4" checked={tick.products.includes(i)} onChange={() => setTicks({ ...tick, products: toggle(tick.products, i) })} />}
                      <span className="min-w-0 flex-1 space-y-0.5">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="break-words font-medium">{p.name}</span>
                          <Badge tone={note === "new" ? "accent" : "neutral"}>{note === "new" ? "New product" : note === "fills" ? "Fills an empty description" : "Already in your products"}</Badge>
                        </span>
                        {p.short_description && <span className="block break-words text-sm text-muted">{p.short_description}</span>}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </fieldset>
        )}
        {save.isError && <p role="alert" className="text-sm text-danger">{save.error.message}</p>}
        <div className="flex flex-wrap gap-3">
          {rail ? saveButton : <ActionBar phone>{saveButton}</ActionBar>}
          <Button variant="ghost" onClick={again}>
            Cancel
          </Button>
        </div>
      </div>
    );
  } else {
    const refused = start.isError ? start.error.message : null;
    body = (
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="min-w-0 flex-1">
          <Field
            label="Paste the brand's website"
            type="url"
            inputMode="url"
            placeholder="https://"
            value={url}
            error={bad ? "Paste a web address (https://…)" : (refused ?? undefined)}
            onChange={(e) => {
              setUrl(e.target.value);
              setBad(false);
              start.reset();
            }}
          />
        </div>
        <Button icon={Globe} busy={start.isPending || price.isPending} onClick={go}>
          {price.data !== undefined ? `Read the site · about ${creditsLabel(price.data)}` : "Read the site"}
        </Button>
      </div>
    );
  }

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="type-section">Import from website</h2>
        <p className="text-sm text-muted">Reads the logo, colours and products from the brand's site. You pick what to keep.</p>
      </div>
      {body}
    </Card>
  );
}
