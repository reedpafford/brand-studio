import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText, must } from "../api/client";
import { ImagePicker } from "../brand/ImagePicker";
import { Button, Field, PageTop, buttonClass, creditsLabel } from "../components";
import { useToast } from "../toast";
import { useMe } from "../auth/useMe";

const HEX = /^#[0-9a-fA-F]{6}$/;
const WEB = /^https?:\/\/[^\s/]+\.[^\s]+$/i;

/** Reed's New brand (v5 F_BrandNew): a name, and optionally its website, colour and logo. With a website its site is
 *  read next and the brand opens on Import from website to pick what to keep; without one it opens on its Look. */
export function NewBrandPage() {
  const [name, setName] = useState("");
  const [website, setWebsite] = useState("");
  const [colour, setColour] = useState("#5E63D6");
  const [logo, setLogo] = useState<number | null>(null);
  const [tried, setTried] = useState(false);
  const me = useMe().data;
  const owner = me?.role === "owner";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const site = website.trim();
  const price = useQuery({ enabled: !!site, queryKey: ["site-read-estimate", "new"], queryFn: () => must(api.GET("/brands/site-read/estimate")).then((r) => r.data!.credits) });
  const badSite = site !== "" && !WEB.test(site) ? "Paste a web address (https://…)" : null;
  const badColour = !HEX.test(colour.trim()) ? "Use a colour like #2F6B4F." : null;
  const reason = !name.trim() ? "Give it a name first" : tried && (badSite || badColour) ? "Fix the field above first" : null;
  const make = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/brands", {
        body: { name: name.trim(), website: site || null, logo_file_id: logo, colours: [colour.trim().toUpperCase()], fonts: [], tone_notes: "", never_say: [], legal_line: "", end_line: "" },
      });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (brand) => {
      await Promise.all([queryClient.invalidateQueries({ queryKey: ["brands"] }), queryClient.invalidateQueries({ queryKey: ["usage"] })]);
      // The brand is made whatever the read does; a read that couldn't start says why, and the Look is there to fill in.
      if (brand.site_read_job_id) {
        navigate(`/b/${brand.id}/brand?import=1`);
        toast(`${brand.name} is ready. Reading its site…`);
      } else {
        navigate(`/b/${brand.id}/brand`);
        toast(brand.site_read_problem ? `${brand.name} is ready. ${brand.site_read_problem}` : `${brand.name} is ready. Add its look next.`);
      }
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTried(true);
    if (name.trim() && !badSite && !badColour) make.mutate();
  };
  if (me && !owner) return <p className="p-6">Only the owner adds brands.</p>;
  return (
    <main className="space-y-6 p-4 sm:p-6">
      <PageTop title="New brand">
        <Link to="/" className={buttonClass("ghost")}>
          Cancel
        </Link>
      </PageTop>
      <form onSubmit={submit} aria-label="New brand" className="mx-auto flex max-w-[520px] flex-col gap-5 sm:pt-6">
        <p className="text-xs text-muted">A brand holds its own look, cast, scripts, videos and budget.</p>
        <Field label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} autoFocus error={make.isError ? make.error.message : null} />
        <Field label="Website (optional)" inputMode="url" placeholder="https://" value={website} onChange={(e) => setWebsite(e.target.value)} hint="We read its logo, colours and products next. You pick what to keep." error={tried ? badSite : null} />
        <div className="space-y-1.5">
          <p className="text-sm font-medium" id="new-colour">Colour</p>
          <div className="flex items-center gap-2">
            <span aria-hidden className="size-9 shrink-0 rounded-md border border-border" style={{ background: HEX.test(colour.trim()) ? colour.trim() : "transparent" }} />
            <input aria-labelledby="new-colour" value={colour} onChange={(e) => setColour(e.target.value)} className="min-h-control w-28 rounded-md border border-border-strong bg-bg px-2.5 font-mono uppercase" />
          </div>
          {tried && badColour && <p role="alert" className="text-sm text-danger">{badColour}</p>}
        </div>
        <ImagePicker label="Logo (optional)" fileId={logo} onChange={setLogo} inline="Change logo" />
        <div className="flex justify-end pt-2">
          {/* "about": the read's usual cost, as Import from website says it (F_BrandNew, F_BrandImport). */}
          <Button type="submit" busy={make.isPending || (!!site && !badSite && price.isPending)} disabled={reason !== null} reason={reason} className="w-full sm:w-auto">
            {site && !badSite && price.data !== undefined ? `Make the brand · about ${creditsLabel(price.data)}` : "Make the brand"}
          </Button>
        </div>
      </form>
    </main>
  );
}
