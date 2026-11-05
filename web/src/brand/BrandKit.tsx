import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Navigate, useBlocker, useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Banner, Button, Dialog, Menu, MenuItem } from "../components";
import { LibraryFrame } from "../library/LibraryFrame";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { ImagePicker } from "./ImagePicker";

type Brand = components["schemas"]["BrandOut"];
const HEX = /^#[0-9a-fA-F]{6}$/;

/** /b/:brandId/brand: the Brand kit tab of the library (v6 S8-05 as redrawn in S-gaps-05 L1): only the brand's name, logo,
 *  colours, and tone and rules. The script and the director carry the rest; products (apps and things) are their own tab. */
export function BrandKit() {
  const brandId = Number(useParams().brandId);
  const { data: brands, isError, refetch } = useBrands();
  const brand = brands?.find((b) => b.id === brandId);
  if (isError) return <Banner title="Couldn't load the brand." action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>}>Check your connection.</Banner>;
  if (brands && !brand) return <p className="p-6">That brand doesn't exist.</p>;
  if (!brand) return null;
  return <Kit key={brand.id} brand={brand} />;
}

/** The old /kit and /screens addresses land on the Brand kit. */
export function ToBrand() {
  return <Navigate to={`/b/${useParams().brandId}/brand`} replace />;
}

const startOf = (b: Brand) => ({ name: b.name, logo_file_id: b.logo_file_id ?? null, colours: b.colours ?? [], tone_notes: b.tone_notes ?? "" });
type Form = ReturnType<typeof startOf>;

function Kit({ brand }: { brand: Brand }) {
  const [saved, setSaved] = useState(() => startOf(brand));
  const [kit, setKit] = useState(saved);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setKit({ ...kit, [k]: v });
  const queryClient = useQueryClient();
  const toast = useToast();
  const changed = JSON.stringify(kit) !== JSON.stringify(saved);
  const valid = kit.colours.every((c) => c === "" || HEX.test(c)) && kit.name.trim() !== "";
  // Leaving with unsaved changes asks first (QA-12 on #1254): the rail, a link, Back, a reload.
  const away = useBlocker(({ currentLocation, nextLocation }) => changed && currentLocation.pathname !== nextLocation.pathname);
  useEffect(() => {
    if (!changed) return;
    const ask = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", ask);
    return () => window.removeEventListener("beforeunload", ask);
  }, [changed]);
  const write = async (all: Form) => {
    const { error, response } = await api.PATCH("/brands/{brand_id}", { params: { path: { brand_id: brand.id } }, body: all });
    if (!response.ok) throw new Error(errorText(error));
    await queryClient.invalidateQueries({ queryKey: ["brands"] });
  };
  const save = useMutation({
    mutationFn: async () => {
      const clean = { ...kit, name: kit.name.trim(), colours: kit.colours.filter((c) => c !== "") };
      await write(clean);
      return { before: saved, clean };
    },
    onSuccess: ({ before, clean }) => {
      setSaved(clean);
      setKit(clean);
      toast("Saved.", async () => {
        await write(before);
        setSaved(before);
        setKit(before);
      });
    },
  });
  const action = (
    <div className="flex items-center gap-2">
      <Button busy={save.isPending} disabled={!changed || !valid} reason={changed && !valid ? (kit.name.trim() ? "Fix the colour codes first" : "Give it a name first") : null} onClick={() => save.mutate()}>
        Save changes
      </Button>
    </div>
  );
  return (
    <LibraryFrame brandId={brand.id} tab="kit" action={action}>
      {save.isError && <p role="alert" className={`${errorClass} mb-4`}>{save.error.message}</p>}
      <div className="flex max-w-[600px] flex-col gap-4">
        <div className="flex flex-wrap items-start gap-4">
          <label className="flex w-full flex-col gap-1 text-sm font-semibold lg:w-[180px]">
            Name
            <input value={kit.name} required maxLength={120} onChange={(e) => set("name", e.target.value)} className="h-control lg:h-9 rounded-md border border-border-strong bg-surface px-3 text-base font-normal text-text lg:text-sm" />
          </label>
          <div className="flex flex-col gap-1">
            <span className="text-sm font-semibold">Logo</span>
            <div className="flex items-center gap-2">
              {kit.logo_file_id ? <img src={fileUrl(kit.logo_file_id)} alt={`${brand.name} logo`} className="size-9 rounded-md bg-surface-2 object-contain" /> : <span aria-hidden className="size-9 rounded-md border border-dashed border-border-strong bg-surface-2" />}
              <ImagePicker label="Logo" inline="Change" fileId={kit.logo_file_id} onChange={(id) => set("logo_file_id", id)} bare />
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-sm font-semibold">Colours</span>
            <Colours colours={kit.colours} onChange={(c) => set("colours", c)} />
          </div>
        </div>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Tone and rules
          <textarea rows={3} value={kit.tone_notes} onChange={(e) => set("tone_notes", e.target.value)} placeholder="fomo only in a positive light: wins on fomo, losses on plain apps." className="rounded-md border border-border-strong bg-surface px-3 py-2 text-base font-normal text-text lg:text-sm" />
        </label>
      </div>
      {away.state === "blocked" && (
        <Dialog title="Leave without saving?" cancelLabel="Keep editing" actionLabel="Leave" danger onCancel={() => away.reset()} onConfirm={() => away.proceed()}>
          Your changes to the brand kit aren't saved. Leaving drops them.
        </Dialog>
      )}
    </LibraryFrame>
  );
}

/** Each colour as a small swatch (S-gaps-05 L1). A press on one opens its picker, its code and Remove; + adds one. */
function Colours({ colours, onChange }: { colours: string[]; onChange: (c: string[]) => void }) {
  const at = (i: number, v: string) => onChange(colours.map((x, j) => (j === i ? v : x)));
  return (
    <div className="flex flex-wrap items-center gap-1">
      {colours.map((c, i) => (
        <Menu
          key={i}
          title={`Colour ${i + 1}`}
          trigger={(p) => (
            <button type="button" {...p} aria-label={`Colour ${i + 1}: ${c || "none"}`} className="grid size-11 place-items-center lg:size-[26px]">
              <span aria-hidden className={`block size-[22px] rounded-sm border ${c && !HEX.test(c) ? "border-danger" : "border-border"}`} style={{ background: HEX.test(c) ? c : "transparent" }} />
            </button>
          )}
        >
          {(close) => (
            <div className="flex flex-col gap-2 p-2">
              <div className="flex items-center gap-2">
                <input type="color" aria-label={`Pick colour ${i + 1}`} value={HEX.test(c) ? c : "#000000"} onChange={(e) => at(i, e.target.value)} className="size-9 cursor-pointer rounded-md border border-border bg-transparent p-0.5" />
                <input aria-label={`Colour ${i + 1} code`} value={c} onChange={(e) => at(i, e.target.value)} placeholder="#12A150" className="h-9 w-28 rounded-md border border-border-strong bg-surface px-2 font-mono text-sm" />
              </div>
              {c && !HEX.test(c) && <p className="text-xs text-danger">Use a colour like #12A150.</p>}
              <MenuItem danger onClick={() => (close(), onChange(colours.filter((_, j) => j !== i)))}>Remove colour</MenuItem>
            </div>
          )}
        </Menu>
      ))}
      <button type="button" aria-label="Add colour" onClick={() => onChange([...colours, colours.at(-1) ?? "#000000"])} className="grid size-11 place-items-center text-muted lg:size-[26px]">
        <span className="grid size-[22px] place-items-center rounded-sm border border-dashed border-border-strong">
          <Plus size={12} strokeWidth={1.75} aria-hidden />
        </span>
      </button>
    </div>
  );
}
