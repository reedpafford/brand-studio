import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { Banner, Button, Card, Field, Select, TextArea } from "../components";
import { useMe } from "../auth/useMe";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { BrandAction, useReportDirty } from "./BrandPage";
import { ChipList } from "./ChipList";
import { ImagePicker } from "./ImagePicker";

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
  const start = {
    name: brand.name,
    logo_file_id: brand.logo_file_id ?? null,
    style_board_file_id: brand.style_board_file_id ?? null,
    end_card_file_id: brand.end_card_file_id ?? null,
    colours: brand.colours ?? [],
    fonts: brand.fonts ?? [],
    tone_notes: brand.tone_notes ?? "",
    never_say: brand.never_say ?? [],
    legal_line: brand.legal_line ?? "",
    end_line: brand.end_line ?? "",
    end_logo: brand.end_logo ?? "off",
  };
  const [kit, setKit] = useState(start);
  const [saved, setSaved] = useState(start);
  const set = <K extends keyof typeof kit>(k: K, v: (typeof kit)[K]) => setKit({ ...kit, [k]: v });
  const queryClient = useQueryClient();
  const toast = useToast();
  const patch = async (body: typeof kit) => {
    const { error, response } = await api.PATCH("/brands/{brand_id}", { params: { path: { brand_id: brand.id } }, body });
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
  const owner = useMe().data?.role === "owner";

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
        <div className="flex flex-wrap gap-6">
          <ImagePicker label="Style board" shape="wide" fileId={kit.style_board_file_id} onChange={(id) => set("style_board_file_id", id)} />
          <ImagePicker label="End card" shape="tall" fileId={kit.end_card_file_id} onChange={(id) => set("end_card_file_id", id)} />
        </div>
      </Card>
      <Card className="min-w-0 space-y-5 lg:self-start">
        <h2 className="type-section">Voice</h2>
        <TextArea label="How we sound" rows={6} value={kit.tone_notes} onChange={(e) => set("tone_notes", e.target.value)} />
        <ChipList label="Never say" items={kit.never_say} onChange={(v) => set("never_say", v)} placeholder="A word or phrase" />
        <Field label="Legal line" value={kit.legal_line} onChange={(e) => set("legal_line", e.target.value)} />
        <Field label="End line" value={kit.end_line} onChange={(e) => set("end_line", e.target.value)} hint={'The last clip of every video says this. Example: "Want to trade like me? Download fomo through the link in my bio."'} />
        <Select
          label="End on the logo"
          value={kit.end_logo}
          disabled={!owner}
          hint={owner ? "When a video ends on the end line, the finished video shows the logo. Free." : "Only the owner can change this."}
          onChange={(e) => set("end_logo", e.target.value as typeof kit.end_logo)}
        >
          <option value="off">Off</option>
          <option value="end_card">Logo card after the end line (1.5 s)</option>
          <option value="overlay">Logo over the end line&apos;s shot</option>
        </Select>
        {save.isError && (
          <p role="alert" className={errorClass}>
            {save.error.message}
          </p>
        )}
      </Card>
    </form>
  );
}
