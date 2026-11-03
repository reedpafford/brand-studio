import { useState, type FormEvent } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, NavLink, useParams } from "react-router-dom";
import { api, errorText, must } from "../api/client";
import { fileUrl, uploadFile } from "../api/upload";
import { useMe } from "../auth/useMe";
import { useToast } from "../toast";
import { btnPrimary, btnSecondary, card, errorText as errorClass, input, linkText } from "../ui";
import { KINDS, isKindSlug } from "./kinds";
import { Button, Menu, MenuItem, PageTop, pillClass } from "../components";
import { ChevronDown, Search } from "lucide-react";

const tab = ({ isActive }: { isActive: boolean }) => pillClass(isActive);

export function LibraryPage() {
  const { brandId, kindSlug } = useParams();
  if (!isKindSlug(kindSlug)) return <p className="p-6">That library doesn't exist.</p>;
  return <Library key={`${brandId}/${kindSlug}`} brandId={Number(brandId)} slug={kindSlug} />;
}

function Library({ brandId, slug }: { brandId: number; slug: keyof typeof KINDS }) {
  const { kind, one, them, title } = KINDS[slug];
  const [archived, setArchived] = useState(false);
  const [search, setSearch] = useState("");
  const [sheet, setSheet] = useState<Filter>("any");
  const [adding, setAdding] = useState(false);
  const { data: me } = useMe();
  const queryClient = useQueryClient();
  const toast = useToast();
  const load = (k: typeof kind, gone: boolean) => ({
    queryKey: ["library", k, brandId, gone],
    queryFn: async () => {
      const { data } = await api.GET("/library/{kind}", { params: { path: { kind: k }, query: { brand_id: brandId, archived: gone } } });
      if (!data) throw new Error("load");
      return data;
    },
  });
  const items = useQuery(load(kind, archived));
  // Each kind tab shows how many there are (W10); the same reads the kinds' own pages use.
  const counts = useQueries({ queries: Object.values(KINDS).map((k) => load(k.kind, false)) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["library", kind] });
  const unarchive = useMutation({
    mutationFn: (item_id: number) => must(api.POST("/library/{kind}/{item_id}/unarchive", { params: { path: { kind, item_id } } })),
    onSuccess: (_, item_id) => {
      refresh();
      const name = items.data?.find((i) => i.id === item_id)?.name ?? "Item";
      toast(`${name} is back.`, async () => {
        await must(api.DELETE("/library/{kind}/{item_id}", { params: { path: { kind, item_id } } }));
        refresh();
      });
    },
  });
  const purge = useMutation({
    mutationFn: (item_id: number) => must(api.DELETE("/library/{kind}/{item_id}/permanent", { params: { path: { kind, item_id } } })),
    onSuccess: refresh,
  });
  const shown = items.data?.filter((i) => i.name.toLowerCase().includes(search.trim().toLowerCase()) && (sheet === "any" || (SHEET[i.sheet_status] ?? SHEET.none).filter === sheet));

  return (
    <main className="mx-auto max-w-content p-4 sm:p-6">
      <PageTop title="Cast & places">
        {!archived && !adding && (
          <Button className="lg:min-h-9 lg:px-3" onClick={() => setAdding(true)}>
            + New {one}
          </Button>
        )}
      </PageTop>
      {/* One 44 px band: the kinds as pills, then search and the sheet filter on the right (v5 C_CastPlaces). */}
      <div className="-mx-4 mb-4 flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-4 sm:-mx-6 sm:px-6 lg:h-11 [&_button]:text-[13px] [&_button]:font-medium">
        <nav aria-label="Kinds" className="flex flex-wrap items-center gap-1">
          {Object.entries(KINDS).map(([s, k], n) => (
            <NavLink key={s} to={`/b/${brandId}/library/${s}`} className={tab}>
              {k.title}
              {counts[n].data && <span className="tabular-nums text-muted">{counts[n].data.length}</span>}
            </NavLink>
          ))}
        </nav>
        <span className="hidden flex-1 sm:block" />
        <label className="relative block w-full sm:w-60">
          <span className="sr-only">Search {them === "them" ? "characters" : title.toLowerCase()}</span>
          <Search size={16} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input className="min-h-11 w-full rounded-sm border border-border-strong bg-surface pl-9 pr-3 text-base text-text placeholder:text-muted lg:h-8 lg:min-h-0 lg:text-[13px]" type="search" placeholder={`Search ${title.toLowerCase()}`} value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
        {kind !== "prop" && (
          <Menu title="Sheet" align="right" trigger={(p) => (
            <Button variant="ghost" dense trailing={ChevronDown} {...p}>
              Sheet: {sheet === "any" ? "Any" : FILTERS[sheet]}
            </Button>
          )}>
            {(close) => Object.entries(FILTERS).map(([id, label]) => <MenuItem key={id} checked={sheet === id} onClick={() => { close(); setSheet(id as Filter); }}>{label}</MenuItem>)}
          </Menu>
        )}
        <Button variant="ghost" dense aria-pressed={archived} onClick={() => setArchived(!archived)}>
          {archived ? "Back" : "Archived"}
        </Button>
      </div>
      <div className="space-y-4">
      {!archived && adding && <NewItem brandId={brandId} kind={kind} one={one} onDone={refresh} onClose={() => setAdding(false)} />}
      {items.isError && <p role="alert" className={errorClass}>Could not load the library. Try again.</p>}
      {(unarchive.isError || purge.isError) && (
        <p role="alert" className={errorClass}>
          {(unarchive.error ?? purge.error)?.message}
        </p>
      )}
      {items.data?.length === 0 && (
        <div className={card}>
          <p className="text-[length:var(--text-xl)] font-semibold">{archived ? `Nothing archived.` : `No ${title.toLowerCase()} for this brand yet.`}</p>
          {!archived && <p className="text-muted">Add a {one} once, use {them} in every video.</p>}
        </div>
      )}
      {items.data && items.data.length > 0 && shown?.length === 0 && (
        <p>
          Nothing matches. <button className={linkText} onClick={() => { setSearch(""); setSheet("any"); }}>Clear filters</button>
        </p>
      )}
      <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6">
        {shown?.map((i) => (
          <li key={i.id} className="space-y-1 text-sm">
            {archived ? <Thumb id={cover(i)} name={i.name} faded /> : (
              <Link to={`/b/${brandId}/library/${slug}/${i.id}`} aria-label={i.name}>
                <Thumb id={cover(i)} name={i.name} />
              </Link>
            )}
            <div className="truncate pt-3 font-medium">{i.name}</div>
            {archived ? (
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-sm bg-surface-2 px-2 py-0.5 text-xs text-muted">Archived</span>
                <button className={linkText} aria-label={`Unarchive ${i.name}`} onClick={() => unarchive.mutate(i.id)}>
                  Unarchive
                </button>
                {me?.role === "owner" && (
                  <button
                    className="text-danger underline"
                    aria-label={`Delete ${i.name} forever`}
                    onClick={() => window.confirm(`Delete ${i.name} forever? This removes all versions and can't be undone.`) && purge.mutate(i.id)}
                  >
                    Delete forever
                  </button>
                )}
              </div>
            ) : (
              kind !== "prop" && <SheetLine status={i.sheet_status} used={i.used_in_count} />
            )}
          </li>
        ))}
      </ul>
      </div>
    </main>
  );
}

const SHEET: Record<string, { text: string; dot: string; filter: string }> = {
  approved: { text: "Sheet approved", dot: "bg-success", filter: "approved" },
  needs_approval: { text: "Sheet to check", dot: "bg-warning", filter: "check" },
  drawing: { text: "Drawing the sheet", dot: "bg-accent", filter: "drawing" },
  waiting_for_owner: { text: "Waiting for the owner's OK", dot: "bg-accent", filter: "drawing" },
  none: { text: "No sheet yet", dot: "border border-muted", filter: "none" },
} as const;
const FILTERS = { any: "Any", approved: "Approved", check: "To check", drawing: "Drawing", none: "No sheet" } as const;
type Filter = keyof typeof FILTERS;

/** A card's status: a dot and words (a hollow ring for no sheet). */
function SheetLine({ status, used }: { status: string; used?: number }) {
  const line = SHEET[status] ?? SHEET.none;
  return (
    <p className="flex items-center gap-1.5 text-xs text-muted">
      <span aria-hidden className={`size-2 shrink-0 rounded-full ${line.dot}`} />
      {line.text}
      {status === "approved" && !!used && ` · in ${used} video${used === 1 ? "" : "s"}`}
    </p>
  );
}

function Thumb({ id, name, faded }: { id?: number; name: string; faded?: boolean }) {
  const fade = faded ? " opacity-60" : "";
  return id ? (
    <img src={fileUrl(id)} alt={name} className={`aspect-[3/4] w-full rounded-md border border-border bg-surface-2 object-cover${fade}`} />
  ) : (
    <div className={`grid aspect-[3/4] w-full place-items-center rounded-md border border-border bg-surface-2 text-muted${fade}`}>No image</div>
  );
}

/** The picture on a card: the approved or latest sheet, else the source photo, else the first picture. */
const cover = (i: { sheet_file_id?: number | null; source_photo_file_id?: number | null; image_file_ids?: number[] }) => i.sheet_file_id ?? i.source_photo_file_id ?? i.image_file_ids?.[0];

function NewItem(props: { brandId: number; kind: "character" | "place" | "prop"; one: string; onDone: () => void; onClose: () => void }) {
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const create = useMutation({
    mutationFn: async () => {
      // A character's or place's picture is a source photo (the sheet is what videos use); a prop's picture is used as it is.
      const stored = file ? (await uploadFile(file)).id : null;
      const photo = props.kind !== "prop";
      const { data, error } = await api.POST("/library/{kind}", {
        params: { path: { kind: props.kind } },
        body: { name, notes, brand_ids: [props.brandId], image_file_ids: stored && !photo ? [stored] : [], source_photo_file_id: stored && photo ? stored : null, outfits: [] },
      });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => {
      setName("");
      setNotes("");
      setFile(null);
      props.onClose();
      props.onDone();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  return (
    <form onSubmit={submit} className={`${card} max-w-[640px] space-y-3`}>
      <label className="block text-sm">
        Name
        <input className={input} required value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      {/* G_CharacterNew: the description, which makes the sheet when there's no photo. */}
      <label className="block text-sm">
        Description
        <textarea className={input} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
        {props.kind !== "prop" && <span className="mt-1 block text-muted">Used to make the sheet when there's no photo.</span>}
      </label>
      <label className="block text-sm">
        {props.kind === "prop" ? "Image (optional)" : "Photo (optional)"}
        <input className={input} type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
      {create.isError && <p role="alert" className={errorClass}>{create.error.message}</p>}
      <div className="flex gap-2">
        <button className={`${btnPrimary} min-h-control`} disabled={create.isPending}>
          Create {props.one}
        </button>
        <button type="button" className={btnSecondary} onClick={props.onClose}>
          Cancel
        </button>
      </div>
    </form>
  );
}
