import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, errorText, must } from "../api/client";
import { fileUrl, uploadFile } from "../api/upload";
import type { components } from "../api/schema";
import { useToast } from "../toast";
import { useBrands } from "../shell/useBrands";
import { Button, Menu, MenuItem } from "../components";
import { backLink, btnPrimary, btnSecondary, card, errorText as errorClass, input, linkText } from "../ui";
import { ItemView } from "./ItemView";
import { CharacterExtras } from "./CharacterExtras";
import { SheetPanel } from "./SheetPanel";
import { LookSheets } from "./LookSheets";
import { SheetVersions } from "./SheetVersions";
import { KINDS, isKindSlug } from "./kinds";
import { serverTime } from "../time";
import { useRail } from "../useMedia";

type Item = components["schemas"]["ItemOut"];

const day = (iso: string) => serverTime(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

export function ItemPage() {
  const { brandId, kindSlug, itemId } = useParams();
  const slug = isKindSlug(kindSlug) ? kindSlug : null;
  const kind = slug ? KINDS[slug].kind : "character";
  const item_id = Number(itemId);
  const item = useQuery({
    enabled: !!slug,
    queryKey: ["library", kind, "item", item_id],
    queryFn: async () => (await api.GET("/library/{kind}/{item_id}", { params: { path: { kind, item_id } } })).data ?? null,
    refetchInterval: (q) => (["drawing", "waiting_for_owner"].includes(q.state.data?.sheet_status ?? "") ? 3000 : false),
  });
  if (!slug) return <p className="p-6">That library doesn't exist.</p>;
  if (item.isPending) return <p className="p-6 text-muted">Loading…</p>;
  if (!item.data) return <p className="p-6">That {KINDS[slug].one} doesn't exist, or it was archived.</p>;
  return <ItemEditor key={`${item.data.id}-${item.data.version}`} item={item.data} slug={slug} brandId={Number(brandId)} />;
}

function ItemEditor({ item, slug, brandId }: { item: Item; slug: keyof typeof KINDS; brandId: number }) {
  const { kind, one, title } = KINDS[slug];
  const { data: brands } = useBrands();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const start = { name: item.name, notes: item.notes ?? "", brand_ids: item.brand_ids ?? [], image_file_ids: item.image_file_ids ?? [],
    outfits: item.outfits ?? [],
    voice_file_id: item.voice_file_id ?? null,
    // A product's line and its claim (flows BR1, #910), read by every script; editors change them too (Reed, 30 Oct).
    short_description: item.short_description ?? "",
    main_claim: item.main_claim ?? "",
  };
  const [form, setForm] = useState(start);
  // v5 (G_Character, G_Place, G_Prop): the item reads as a page; Edit opens the form in its place. A save shows the page again.
  const [editing, setEditing] = useState(false);
  const rail = useRail();
  const changed = JSON.stringify(form) !== JSON.stringify(start);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["library", kind] });
  const path = { kind, item_id: item.id };
  const others = (item.brand_ids ?? []).filter((id) => id !== brandId).map((id) => brands?.find((b) => b.id === id)?.name).filter(Boolean);
  const currentName = brands?.find((b) => b.id === brandId)?.name;
  // "Open Mia" from a storyboard or clips step comes back to that step.
  const back = useSearchParams()[0].get("back");
  const backTo = back?.startsWith(`/b/${brandId}/`) ? back : null;

  const save = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.PATCH("/library/{kind}/{item_id}", { params: { path }, body: kind === "character" ? { ...form, short_description: undefined, main_claim: undefined } : { name: form.name, notes: form.notes, brand_ids: form.brand_ids, image_file_ids: form.image_file_ids, ...(kind === "prop" ? { short_description: form.short_description, main_claim: form.main_claim } : {}) } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: refresh,
  });
  const archive = useMutation({
    mutationFn: () => must(api.DELETE("/library/{kind}/{item_id}", { params: { path } })),
    onSuccess: async () => {
      await refresh();
      navigate(`/b/${brandId}/library/${slug}`);
      toast(`${item.name} archived.`, async () => {
        await api.POST("/library/{kind}/{item_id}/unarchive", { params: { path } });
        refresh();
      });
    },
  });
  const addImage = useMutation({
    mutationFn: uploadFile,
    onSuccess: (f) => setForm((s) => ({ ...s, image_file_ids: [...s.image_file_ids, f.id] })),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };
  const toggleBrand = (id: number) =>
    setForm({ ...form, brand_ids: form.brand_ids.includes(id) ? form.brand_ids.filter((b) => b !== id) : [...form.brand_ids, id] });

  return (
    <main className="mx-auto max-w-content space-y-6 p-4 sm:p-6">
      {backTo && (
        <Link to={backTo} className={backLink}>
          ← Back to your video
        </Link>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
        <nav aria-label="Breadcrumb" className="flex min-w-0 flex-wrap items-center gap-x-2 text-sm text-muted">
          <Link to={`/b/${brandId}/library/characters`} className="inline-flex min-h-control min-w-11 items-center justify-center hover:text-text sm:min-h-control-dense">Cast &amp; places</Link>
          <span aria-hidden>›</span>
          <Link to={`/b/${brandId}/library/${slug}`} className="inline-flex min-h-control min-w-11 items-center justify-center hover:text-text sm:min-h-control-dense">{slug === "props" ? "Props & products" : title}</Link>
          <span aria-hidden>›</span>
          <span className="font-medium text-text" aria-current="page">{item.name}</span>
        </nav>
        <div className="flex items-center gap-1">
          {!editing && <Button variant="ghost" onClick={() => setEditing(true)}>Edit</Button>}
          <Menu title="More" align="right" trigger={(t) => <Button variant="ghost" {...t}>More</Button>}>
            {(close) => (
              <MenuItem danger onClick={() => { close(); archive.mutate(); }}>
                Archive {one}
              </MenuItem>
            )}
          </Menu>
        </div>
      </div>
      {archive.isError && <p role="alert" className={errorClass}>{archive.error.message}</p>}
      <div className="grid gap-8 lg:grid-cols-[360px_minmax(0,1fr)] lg:items-start">
        <div className="order-2 min-w-0 space-y-6 lg:order-1">
          {kind === "prop" ? (
            <PropPictures ids={item.image_file_ids ?? []} name={item.name} onAdd={() => setEditing(true)} />
          ) : (
            <>
              <SheetPanel item={item} kind={kind} ensureSaved={async () => changed && form.brand_ids.length > 0 && (await save.mutateAsync())} />
              <SheetVersions item={item} kind={kind} />
            </>
          )}
        </div>
        {kind === "character" && !rail && (
          <div className="order-3 min-w-0">
            <LookSheets item={item} />
          </div>
        )}
        {/* On a phone the name and its sections come first, the sheet after (QA-3 on #1204: not 1,500 px down). */}
        <div className="order-1 min-w-0 max-w-[720px] space-y-0 lg:order-2">
      {!editing ? (
        <ItemView item={item} kind={kind} shared={others as string[]} brandNames={(item.brand_ids ?? []).map((id) => brands?.find((b) => b.id === id)?.name).filter((n): n is string => !!n)} onEdit={() => setEditing(true)} />
      ) : (
      <form onSubmit={submit} className={`${card} space-y-4`}>
        {kind === "prop" && (
        <div className="space-y-2">
          <div className="text-sm font-medium">Images</div>
          <ul className="flex flex-wrap gap-3">
            {form.image_file_ids.map((id, n) => (
              <li key={id} className="space-y-1 text-sm">
                <img src={fileUrl(id)} alt={`${item.name} ${n + 1}`} className="size-24 rounded-md border border-border bg-surface-2 object-cover" />
                <button
                  type="button"
                  className={linkText}
                  aria-label={`Remove image ${n + 1}`}
                  onClick={() => setForm({ ...form, image_file_ids: form.image_file_ids.filter((x) => x !== id) })}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
          <label className={`inline-block cursor-pointer text-sm ${linkText}`}>
            Add image
            <input type="file" accept="image/*" className="sr-only" aria-label="Add image" onChange={(e) => e.target.files?.[0] && addImage.mutate(e.target.files[0])} />
          </label>
          {addImage.isError && <p role="alert" className={errorClass}>{addImage.error.message}</p>}
        </div>
        )}
        <label className="block text-sm">
          Name
          <input className={input} required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </label>
        <fieldset className="space-y-1 text-sm">
          <legend className="font-medium">Brands</legend>
          {brands?.map((b) => (
            <label key={b.id} className="mr-4 inline-flex min-h-11 items-center gap-2 sm:min-h-0">
              <input type="checkbox" checked={form.brand_ids.includes(b.id)} onChange={() => toggleBrand(b.id)} />
              {b.name}
            </label>
          ))}
        </fieldset>
        <label className="block text-sm">
          Notes
          <textarea className={input} rows={4} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </label>
        {kind === "prop" && (
          <div className="space-y-3">
            <label className="block text-sm">
              What it is, in a line
              <input className={input} maxLength={500} placeholder="Grain-free salmon kibble for picky dogs" value={form.short_description} onChange={(e) => setForm({ ...form, short_description: e.target.value })} />
            </label>
            <label className="block text-sm">
              Main claim
              <input className={input} maxLength={500} placeholder="Dogs finish the bowl" value={form.main_claim} onChange={(e) => setForm({ ...form, main_claim: e.target.value })} />
            </label>
            {(item.advice ?? []).map((a) => (
              <p key={a} className="text-sm text-warning">{a}</p>
            ))}
          </div>
        )}
        {kind === "character" && (
          <CharacterExtras
            outfits={form.outfits}
            voiceFileId={form.voice_file_id}
            onOutfits={(outfits) => setForm({ ...form, outfits })}
            onVoice={(voice_file_id) => setForm({ ...form, voice_file_id })}
          />
        )}
        {save.isError && <p role="alert" className={errorClass}>{save.error.message}</p>}
        <div className="flex flex-wrap items-center gap-3">
          <button className={`${btnPrimary} min-h-control`} disabled={save.isPending || !changed || form.brand_ids.length === 0}>
            Save
          </button>
          {form.brand_ids.length === 0 && <span className="text-sm text-muted">Pick at least one brand.</span>}
          {form.brand_ids.length > 0 && item.brand_ids?.includes(brandId) && !form.brand_ids.includes(brandId) && (
            <span className="text-sm text-warning">This will remove {form.name} from {currentName}'s library.</span>
          )}
          <button type="button" className={`${btnSecondary} min-h-control`} onClick={() => { setForm(start); setEditing(false); }}>
            Cancel
          </button>
        </div>
      </form>
      )}
          {/* A character's sheets in other styles: a full-width row here, not squeezed under the house sheet. On a phone
              they come after the House sheet instead (QA-3 on #1204: name, sections, House sheet, other styles). */}
          {kind === "character" && rail && (
            <div className="border-t border-border pt-4">
              <LookSheets item={item} />
            </div>
          )}
          {/* History stays under the page and the form alike: a restore works from either. */}
          <History kind={kind} item={item} onRestored={refresh} />
        </div>
      </div>
    </main>
  );
}

function History({ kind, item, onRestored }: { kind: "character" | "place" | "prop"; item: Item; onRestored: () => void }) {
  const versions = useQuery({
    queryKey: ["library", kind, "versions", item.id, item.version],
    queryFn: async () => (await api.GET("/library/{kind}/{item_id}/versions", { params: { path: { kind, item_id: item.id } } })).data ?? [],
  });
  const members = useQuery({
    queryKey: ["team", "members"],
    queryFn: async () => (await api.GET("/team/members")).data ?? [],
  });
  const toast = useToast();
  const restoreCall = (version: number) =>
    must(api.POST("/library/{kind}/{item_id}/versions/{version}/restore", { params: { path: { kind, item_id: item.id, version } } }));
  const restore = useMutation({
    mutationFn: restoreCall,
    onSuccess: ({ data }, version) => {
      onRestored();
      // Undo = restore the version we were on, which makes one more version.
      toast(`Restored v${version} as v${data?.version}.`, () => restoreCall(item.version).then(onRestored));
    },
  });
  const who = (id: number | null) => members.data?.find((m) => m.id === id)?.name ?? "someone";
  // Nothing to restore yet (only the version in use): no History at all (QA-3 on #1204).
  if (!versions.data || versions.data.filter((v) => v.version !== item.version).length === 0) return null;
  return (
    <section className="space-y-2 border-t border-border pt-4">
      <h2 className="text-[length:var(--text-md)] font-semibold">History</h2>
      {restore.isError && <p role="alert" className={errorClass}>{restore.error.message}</p>}
      <ul className="divide-y divide-border text-sm">
        {versions.data?.map((v) => (
          <li key={v.version} className="flex items-center gap-3 py-2">
            <span className="flex-1">
              v{v.version} · {day(v.created_at)} by {who(v.saved_by_id)}
            </span>
            {v.version !== item.version && (
              <button className={`${linkText} min-h-11 sm:min-h-0`} aria-label={`Restore v${v.version}`} onClick={() => restore.mutate(v.version)}>
                Restore
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** A prop's pictures (G_Prop): the first large, the rest small; adding one opens Edit, where pictures are added and removed. */
function PropPictures({ ids, name, onAdd }: { ids: number[]; name: string; onAdd: () => void }) {
  return (
    <section aria-label="Pictures" className="space-y-3">
      {ids[0] ? (
        <img src={fileUrl(ids[0])} alt={name} className="aspect-square w-full rounded-md border border-border bg-surface-2 object-cover" />
      ) : (
        <div className="grid aspect-square w-full place-items-center rounded-md border border-border bg-surface-2 text-muted">No picture yet</div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        {ids.length > 1 && ids.map((id, n) => (
          <img key={id} src={fileUrl(id)} alt={`${name} ${n + 1}`} className="size-16 rounded-md border border-border bg-surface-2 object-cover" />
        ))}
        <Button variant="ghost" onClick={onAdd}>Add image</Button>
      </div>
    </section>
  );
}
