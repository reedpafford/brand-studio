import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { Banner, Button, Card, Field, Select, TextArea } from "../components";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { BrandAction, useReportDirty } from "./BrandPage";
import { ChipList } from "./ChipList";
import { ImagePicker } from "./ImagePicker";
import { useMe } from "../auth/useMe";
import { useLooks } from "../scripts/Looks";
import { CtaLines, DefaultCast, LANGUAGES, OWNER_ONLY, setupOf } from "./BrandSetup";

type Brand = components["schemas"]["BrandOut"];

const HEX = /^#[0-9a-fA-F]{6}$/;

export function KitPage() {
  const { brandId } = useParams();
  const { data: brands, isError, refetch } = useBrands();
  const brand = brands?.find((b) => b.id === Number(brandId));
  if (isError) return <Banner title="Couldn't load the brand." action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>}>Check your connection.</Banner>;
  if (!brand) return <p className="p-6">That brand doesn't exist.</p>;
  return <KitForm key={brand.id} brand={brand} />;
}

function KitForm({ brand }: { brand: Brand }) {
  const setup = setupOf(brand); // BR1, once the server has it
  const owner = useMe().data?.role === "owner";
  const looks = useLooks().data;
  // With BR1 the new sections are the owner's (an editor's save leaves them out), and never_say and end_line are the
  // server's to keep in step with the Don't list and the Default CTA line, so they are never sent.
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
    // Until the owner decides, editors keep what they edit today: tone notes, never say and the end line (the server
    // carries those into the Don't list and the Default CTA line). The owner edits the new fields themselves.
    const body = owner && setup ? { ...rest, tone_notes, audience, do_list, dont_list, music_style, default_look, default_language, default_cast } : { ...rest, tone_notes, never_say, end_line };
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
  const valid = kit.colours.every((c) => HEX.test(c));

  return (
    <form
      className="grid grid-cols-1 gap-4 lg:grid-cols-[7fr_5fr]"
      onSubmit={(e) => {
        e.preventDefault();
        if (changed && valid) save.mutate();
      }}
    >
      <BrandAction>
        <Button type="button" busy={save.isPending} disabled={!changed || !valid} reason={!changed ? "No changes yet" : !valid ? "Fix the colour codes first" : undefined} onClick={() => save.mutate()}>
          Save changes
        </Button>
      </BrandAction>
      <Card className="min-w-0 space-y-5">
        <h2 className="type-section">Look</h2>
        <Field label="Name" required value={kit.name} onChange={(e) => set("name", e.target.value)} />
        <ImagePicker label="Logo" fileId={kit.logo_file_id} onChange={(id) => set("logo_file_id", id)} />
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Colours</legend>
          <div className="flex flex-wrap gap-3">
            {kit.colours.map((c, i) => (
              <span key={i} className="flex w-28 flex-col gap-1">
                <span className="flex items-center gap-1">
                  <input
                    type="color"
                    className="size-control shrink-0 cursor-pointer rounded-md border border-border bg-transparent p-0.5"
                    aria-label={`Colour ${i + 1} picker`}
                    value={HEX.test(c) ? c : "#000000"}
                    onChange={(e) => set("colours", kit.colours.map((x, j) => (j === i ? e.target.value : x)))}
                  />
                  <button type="button" className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2" aria-label={`Remove colour ${i + 1}`} onClick={() => set("colours", kit.colours.filter((_, j) => j !== i))}>
                    <X size={16} strokeWidth={1.75} aria-hidden />
                  </button>
                </span>
                <input
                  className="min-h-control w-full rounded-md border border-border-strong bg-surface px-2 font-mono text-sm"
                  aria-label={`Colour ${i + 1}`}
                  placeholder="#12A150"
                  value={c}
                  onChange={(e) => set("colours", kit.colours.map((x, j) => (j === i ? e.target.value : x)))}
                />
                {c !== "" && !HEX.test(c) && <span className={errorClass}>Use a colour like #12A150.</span>}
              </span>
            ))}
          </div>
          <Button type="button" variant="secondary" icon={Plus} aria-label="Add colour" onClick={() => set("colours", [...kit.colours, kit.colours.at(-1) ?? ""])}>
            Add
          </Button>
          <p className="text-sm text-muted">The first colour tints the brand's dot.</p>
        </fieldset>
        <ChipList label="Fonts" items={kit.fonts} onChange={(v) => set("fonts", v)} placeholder="e.g. Manrope" />
        <ImagePicker label="Style board" shape="wide" fileId={kit.style_board_file_id} onChange={(id) => set("style_board_file_id", id)} />
      </Card>
      {setup ? (
        <div className="min-w-0 space-y-4 lg:self-start">
          <Card className="min-w-0 space-y-5">
            <h2 className="type-section">Voice and tone</h2>
            <TextArea label="How the brand talks" rows={5} value={kit.tone_notes} onChange={(e) => set("tone_notes", e.target.value)} />
            {owner ? (
              <>
                <TextArea label="Audience" rows={2} placeholder="Dog owners who've tried everything" value={kit.audience ?? ""} onChange={(e) => set("audience", e.target.value)} />
                <ChipList label="Do" items={kit.do_list ?? []} onChange={(v) => set("do_list", v)} placeholder="Something to always do" />
                <ChipList label="Don't" items={kit.dont_list ?? []} onChange={(v) => set("dont_list", v)} placeholder="A word or phrase to never say" />
                <Field label="Music style" value={kit.music_style ?? ""} placeholder="Upbeat pop, warm" hint="New song versions start with this music style." onChange={(e) => set("music_style", e.target.value)} />
              </>
            ) : (
              <>
                <ChipList label="Don't" items={kit.never_say} onChange={(v) => set("never_say", v)} placeholder="A word or phrase to never say" />
                <Field label="End line" value={kit.end_line} onChange={(e) => set("end_line", e.target.value)} hint="The Default call to action: the last clip of a video says it." />
                <div className="space-y-3 rounded-md bg-surface-2 p-3">
                  <p className="text-sm text-muted">{OWNER_ONLY}</p>
                  <TextArea label="Audience" rows={2} readOnly value={kit.audience ?? ""} />
                  <ReadList label="Do" items={kit.do_list ?? []} />
                  <Field label="Music style" readOnly value={kit.music_style ?? ""} />
                </div>
              </>
            )}
            <Field label="Legal line" value={kit.legal_line} onChange={(e) => set("legal_line", e.target.value)} />
          </Card>
          <CtaLines brandId={brand.id} lines={setup.cta_lines} advice={setup.advice} owner={owner} />
          <Card className="min-w-0 space-y-5">
            <h2 className="type-section">Defaults for new scripts</h2>
            {!owner && <p className="text-sm text-muted">{OWNER_ONLY}</p>}
            {looks && (
              <Select label="Look" disabled={!owner} value={kit.default_look} onChange={(e) => set("default_look", e.target.value)} hint={looks.find((l) => l.id === kit.default_look)?.on === false ? "Off for editors: new scripts will start on House until it's on." : undefined}>
                {looks.map((l) => (
                  <option key={l.id} value={l.id}>{l.name}{l.on ? "" : " (off for editors)"}</option>
                ))}
              </Select>
            )}
            <Select label="Language" disabled={!owner} value={kit.default_language} onChange={(e) => set("default_language", e.target.value)}>
              {Object.entries({ ...LANGUAGES, ...(kit.default_language && !LANGUAGES[kit.default_language] ? { [kit.default_language]: kit.default_language } : {}) }).map(([id, name]) => (
                <option key={id} value={id}>{name}</option>
              ))}
            </Select>
            <DefaultCast brandId={brand.id} value={kit.default_cast ?? []} picks={setup.cast} readOnly={!owner} onChange={(v) => set("default_cast", v)} />
          </Card>
          {save.isError && <p role="alert" className={errorClass}>{save.error.message}</p>}
        </div>
      ) : (
      <Card className="min-w-0 space-y-5 lg:self-start">
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
      </Card>
      )}
    </form>
  );
}

/** A list shown read only (an editor's Do and Don't). */
function ReadList({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="space-y-1">
      <p className="text-sm font-medium">{label}</p>
      {items.length === 0 ? <p className="text-sm text-muted">Nothing yet.</p> : (
        <ul className="flex flex-wrap gap-2">
          {items.map((x) => (
            <li key={x} className="rounded-md bg-surface-3 px-3 py-1 text-sm">{x}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
