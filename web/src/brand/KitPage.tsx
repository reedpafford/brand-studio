import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { Banner, Button, buttonClass, Field, Select, TextArea } from "../components";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { BrandAction, useBrandFrame, useReportDirty } from "./BrandPage";
import { ChipList } from "./ChipList";
import { ImagePicker } from "./ImagePicker";
import { useMe } from "../auth/useMe";
import { lookName, useLooks } from "../scripts/Looks";
import { useLanguages } from "../languages/useLanguages";
import { CtaLines, DefaultCast, setupOf } from "./BrandSetup";
import { SiteImport, stored } from "./SiteImport";

type Brand = components["schemas"]["BrandOut"];

const HEX = /^#[0-9a-fA-F]{6}$/;

type Part = "look" | "voice";

export function KitPage({ part = "look" }: { part?: Part }) {
  const { brandId } = useParams();
  const { data: brands, isError, refetch } = useBrands();
  const brand = brands?.find((b) => b.id === Number(brandId));
  if (isError) return <Banner title="Couldn't load the brand." action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>}>Check your connection.</Banner>;
  if (!brand) return <p className="p-6">That brand doesn't exist.</p>;
  return <KitWithImport brand={brand} part={part} />;
}

/** The owner's Import from website above the form; a save there starts the form again from the brand as saved. */
function KitWithImport({ brand, part }: { brand: Brand; part: Part }) {
  const owner = useMe().data?.role === "owner";
  const { importing, setImporting } = useBrandFrame();
  // Import from website shows once it's pressed in the top bar (or while a read is on its way), on the Look tab (F_BrandImport).
  const showImport = owner && part === "look" && (importing || stored(brand.id) !== null);
  const [round, setRound] = useState(0);
  const [changed, setChanged] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  return (
    <div className="space-y-4">
      {showImport ? (
        <SiteImport brandId={brand.id} waitFor={changed ? "Save or undo your changes below first" : null} onSaved={() => { setRound((n) => n + 1); setImporting(false); }} onReviewing={setReviewing} />
      ) : (
        part === "look" && <SetUp brand={brand} owner={owner} onImport={() => setImporting(true)} />
      )}
      <KitForm key={`${brand.id}:${round}`} brand={brand} part={part} onChanged={setChanged} quiet={reviewing} />
    </div>
  );
}

/** `quiet`: an import review holds the page's one press, so an untouched form's Save changes steps aside. */
function KitForm({ brand, part, onChanged, quiet }: { brand: Brand; part: Part; onChanged: (changed: boolean) => void; quiet: boolean }) {
  const setup = setupOf(brand); // BR1, once the server has it
  const looks = useLooks().data;
  const languages = useLanguages().data;
  // Editors edit the whole brand, as the owner does (Reed, 30 Oct). With BR1, never_say and end_line are the server's to
  // keep in step with the Don't list and the Default CTA line, so they are never sent.
  const extra = setup
    ? { audience: setup.audience, do_list: setup.do_list, dont_list: setup.dont_list, music_style: setup.music_style, default_look: setup.default_look, default_language: setup.default_language, default_cast: setup.default_cast }
    : null;
  const start = {
    name: brand.name,
    logo_file_id: brand.logo_file_id ?? null,
    style_board_file_id: brand.style_board_file_id ?? null,
    colours: brand.colours ?? [],
    fonts: brand.fonts ?? [],
    tone_notes: brand.tone_notes ?? "",
    never_say: brand.never_say ?? [],
    legal_line: brand.legal_line ?? "",
    end_line: brand.end_line ?? "",
    ...extra,
  };
  const [kit, setKit] = useState(start);
  const [saved, setSaved] = useState(start);
  const set = <K extends keyof typeof kit>(k: K, v: (typeof kit)[K]) => setKit({ ...kit, [k]: v });
  const queryClient = useQueryClient();
  const toast = useToast();
  const patch = async (all: typeof kit) => {
    const { never_say, end_line, audience, do_list, dont_list, music_style, default_look, default_language, default_cast, tone_notes, ...rest } = all;
    const body = setup ? { ...rest, tone_notes, audience, do_list, dont_list, music_style, default_look, default_language, default_cast } : { ...rest, tone_notes, never_say, end_line };
    const { error, response } = await api.PATCH("/brands/{brand_id}", { params: { path: { brand_id: brand.id } }, body: body as typeof kit });
    if (!response.ok) throw new Error(errorText(error));
    await queryClient.invalidateQueries({ queryKey: ["brands"] });
  };
  const save = useMutation({
    mutationFn: async () => {
      const before = saved;
      await patch(kit);
      return before;
    },
    onSuccess: (before) => {
      setSaved(kit);
      toast("Saved.", async () => {
        await patch(before);
        setSaved(before);
        setKit(before);
      });
    },
  });
  const changed = JSON.stringify(kit) !== JSON.stringify(saved);
  useReportDirty(changed);
  useEffect(() => onChanged(changed), [changed, onChanged]);
  const valid = kit.colours.every((c) => HEX.test(c));

  const err = save.isError && <p role="alert" className={errorClass}>{save.error.message}</p>;
  // v5 F_BrandLook / F_BrandVoice: a 640 px column of fields and a 320 px side column; Save changes sits in the bottom bar.
  return (
    <form
      className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,640px)_320px] lg:gap-12"
      onSubmit={(e) => {
        e.preventDefault();
        if (changed && valid) save.mutate();
      }}
    >
      {!(quiet && !changed) && <BrandAction>
        <Button type="button" busy={save.isPending} disabled={!changed || !valid} reason={!changed ? "No changes yet" : !valid ? "Fix the colour codes first" : undefined} onClick={() => save.mutate()}>
          Save changes
        </Button>
      </BrandAction>}
      {part === "look" ? (
        <>
          <div className="min-w-0 space-y-6">
            <section className="min-w-0 space-y-5 border-b border-border pb-6 last:border-b-0">
              <h2 className="type-section">Look</h2>
              <Field label="Name" required value={kit.name} onChange={(e) => set("name", e.target.value)} />
              <ImagePicker label="Logo" inline="Change logo" fileId={kit.logo_file_id} onChange={(id) => set("logo_file_id", id)} />
              <fieldset className="space-y-2">
                <legend className="text-sm font-medium">Colours</legend>
                <p className="text-sm text-muted">The first colour tints the brand's dot.</p>
                {/* v5 F_BrandLook: each colour's swatch and hex side by side, + Add at the end of the row. */}
                <div className="flex flex-wrap items-start gap-3">
                  {kit.colours.map((c, i) => (
                    <span key={i} className="flex w-full flex-col gap-1 sm:w-48 lg:w-40">
                      <span className="flex items-center gap-1">
                        <input
                          type="color"
                          className="size-control shrink-0 cursor-pointer rounded-md border border-border bg-transparent p-0.5"
                          aria-label={`Colour ${i + 1} picker`}
                          value={HEX.test(c) ? c : "#000000"}
                          onChange={(e) => set("colours", kit.colours.map((x, j) => (j === i ? e.target.value : x)))}
                        />
                        <input
                          className="min-h-control w-full min-w-0 rounded-md border border-border-strong bg-surface px-2 font-mono text-sm"
                          aria-label={`Colour ${i + 1}`}
                          placeholder="#12A150"
                          value={c}
                          onChange={(e) => set("colours", kit.colours.map((x, j) => (j === i ? e.target.value : x)))}
                        />
                        <button type="button" className="grid size-control shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2 lg:w-6" aria-label={`Remove colour ${i + 1}`} onClick={() => set("colours", kit.colours.filter((_, j) => j !== i))}>
                          <X size={14} strokeWidth={1.75} aria-hidden />
                        </button>
                      </span>
                      {c !== "" && !HEX.test(c) && <span className={errorClass}>Use a colour like #12A150.</span>}
                    </span>
                  ))}
                  <Button type="button" variant="secondary" icon={Plus} aria-label="Add colour" onClick={() => set("colours", [...kit.colours, kit.colours.at(-1) ?? ""])}>
                    Add
                  </Button>
                </div>
              </fieldset>
              <ChipList label="Fonts" items={kit.fonts} onChange={(v) => set("fonts", v)} placeholder="e.g. Manrope" />
            </section>
            {setup && (
              <section className="min-w-0 space-y-5">
                <h2 className="type-section">Defaults for new scripts</h2>
                <div className="grid gap-4 sm:grid-cols-2">
            {looks && (
              <Select label="Style for new scripts" value={kit.default_look} onChange={(e) => set("default_look", e.target.value)} hint={looks.find((l) => l.id === kit.default_look)?.on === false ? "Off for editors: new scripts will start on House until it's on." : undefined}>
                {/* The styles; a brand already on one of a style's lanes keeps it, by its name (one look per style). */}
                {looks.map((l) => (
                  <option key={l.id} value={l.id}>{l.name}{l.on ? "" : " (off for editors)"}</option>
                ))}
                {!looks.some((l) => l.id === kit.default_look) && kit.default_look && <option value={kit.default_look}>{lookName(looks, kit.default_look)}</option>}
              </Select>
            )}
            {languages && (
              // Every language, as the Look picker: an Off one is marked, and editors start in English.
              <Select label="Language" value={kit.default_language} onChange={(e) => set("default_language", e.target.value)} hint={languages.some((l) => l.id === kit.default_language && !l.on) ? "New scripts by editors start in English." : undefined}>
                {languages.map((l) => (
                  <option key={l.id} value={l.id}>{l.name}{l.on ? "" : " (off for editors)"}</option>
                ))}
              </Select>
            )}
                </div>
              </section>
            )}
            {err}
          </div>
          <aside className="min-w-0 space-y-2 lg:self-start">
            <ImagePicker label="Style board" shape="wide" fileId={kit.style_board_file_id} onChange={(id) => set("style_board_file_id", id)} />
            <p className="text-sm text-muted">One picture of the brand's mood. The director reads it for every style.</p>
          </aside>
        </>
      ) : setup ? (
        <>
          <section className="min-w-0 space-y-5">
            <h2 className="type-section">Voice</h2>
            <TextArea label="How we sound" rows={5} value={kit.tone_notes} onChange={(e) => set("tone_notes", e.target.value)} />
            <Field label="Audience" placeholder="Dog owners who've tried everything" value={kit.audience ?? ""} onChange={(e) => set("audience", e.target.value)} />
            <ChipList label="Do" items={kit.do_list ?? []} onChange={(v) => set("do_list", v)} placeholder="Something to always do" />
            <ChipList label="Never say" items={kit.dont_list ?? []} onChange={(v) => set("dont_list", v)} placeholder="A word or phrase" />
            <Field label="Music style" value={kit.music_style ?? ""} placeholder="Upbeat pop, warm" hint="New song versions start with this music style." onChange={(e) => set("music_style", e.target.value)} />
            <Field label="Legal line" value={kit.legal_line} onChange={(e) => set("legal_line", e.target.value)} />
            {err}
          </section>
          <aside className="min-w-0 space-y-6 lg:self-start">
            <CtaLines brandId={brand.id} lines={setup.cta_lines} advice={setup.advice} />
            <section className="space-y-3">
              <h2 className="type-section">Default cast</h2>
              <DefaultCast brandId={brand.id} value={kit.default_cast ?? []} picks={setup.cast} onChange={(v) => set("default_cast", v)} />
            </section>
          </aside>
        </>
      ) : (
      <section className="min-w-0 space-y-5 border-b border-border pb-6 last:border-b-0 lg:self-start">
        <h2 className="type-section">Voice</h2>
        <TextArea label="How we sound" rows={6} value={kit.tone_notes} onChange={(e) => set("tone_notes", e.target.value)} />
        <ChipList label="Never say" items={kit.never_say} onChange={(v) => set("never_say", v)} placeholder="A word or phrase" />
        <Field label="Legal line" value={kit.legal_line} onChange={(e) => set("legal_line", e.target.value)} />
        <Field label="End line" value={kit.end_line} onChange={(e) => set("end_line", e.target.value)} hint={`The last clip of every video says this. Example: "Find ${kit.name || "us"} through the link in my bio."`} />
        {save.isError && (
          <p role="alert" className={errorClass}>
            {save.error.message}
          </p>
        )}
      </section>
      )}
    </form>
  );
}

/** A brand with nothing set yet (v5 F_BrandEmpty): three things to do, in any order, and a video can still be made now. */
function SetUp({ brand, owner, onImport }: { brand: Brand; owner: boolean; onImport: () => void }) {
  const { goTab } = useBrandFrame();
  const empty = !brand.logo_file_id && (brand.colours ?? []).length === 0 && !brand.tone_notes && !brand.style_board_file_id;
  if (!empty) return null;
  const row = "flex min-h-18 flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3 last:border-b-0";
  return (
    <section aria-label={`Set up ${brand.name}`} className="max-w-[640px] space-y-3">
      <h2 className="text-[length:var(--text-xl)] font-semibold">Set up {brand.name}</h2>
      <p className="text-muted">Three things make every video look and sound like this brand. Do them in any order.</p>
      <div className="rounded-lg border border-border">
        <div className={row}>
          <div><p className="font-medium">Look</p><p className="text-sm text-muted">Logo, colours, fonts and a style board.</p></div>
          {owner ? <Button onClick={onImport}>Import from website</Button> : <span className="text-sm text-muted">Fill it in below.</span>}
        </div>
        <div className={row}>
          <div><p className="font-medium">Voice &amp; lines</p><p className="text-sm text-muted">How it sounds, words to avoid, the end line.</p></div>
          <Button variant="secondary" onClick={() => goTab("voice")}>Write the voice</Button>
        </div>
        <div className={row}>
          <div><p className="font-medium">Cast</p><p className="text-sm text-muted">The characters its videos use.</p></div>
          <Link to={`/b/${brand.id}/library/characters`} className={buttonClass("secondary")}>Add a character</Link>
        </div>
      </div>
      <p className="text-sm text-muted">You can make a video now. It uses the House style until these are set.</p>
    </section>
  );
}
