import { useState, type FormEvent } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, NavLink, useParams } from "react-router-dom";
import { api, errorText, must } from "../api/client";
import { fileUrl, uploadFile } from "../api/upload";
import { useMe } from "../auth/useMe";
import { useToast } from "../toast";
import { useBrands } from "../shell/useBrands";
import { btnPrimary, btnSecondary, card, errorText as errorClass, input, linkText } from "../ui";
import { KINDS, isKindSlug } from "./kinds";
import { PageTop, pillClass } from "../components";

const tab = ({ isActive }: { isActive: boolean }) => pillClass(isActive);

export function LibraryPage() {
  const { brandId, kindSlug } = useParams();
  if (!isKindSlug(kindSlug)) return <p className="p-6">That library doesn't exist.</p>;
  return <Library key={`${brandId}/${kindSlug}`} brandId={Number(brandId)} slug={kindSlug} />;
}

function Library({ brandId, slug }: { brandId: number; slug: keyof typeof KINDS }) {
  const { kind, one, them, title } = KINDS[slug];
  const { data: brands } = useBrands();
  const [archived, setArchived] = useState(false);
  const [search, setSearch] = useState("");
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
  const shown = items.data?.filter((i) => i.name.toLowerCase().includes(search.trim().toLowerCase()));

  return (
    <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
      <PageTop title="Cast & places" line="The studio's reusable characters and places. Looks made for a video stay with that video.">
        {!archived && !adding && (
          <button className={`${btnPrimary} min-h-control`} onClick={() => setAdding(true)}>
            New {one}
          </button>
        )}
      </PageTop>
      {/* One bar: the kinds, then search and Show archived on the right (v4 board). */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border pb-2">
        <nav aria-label="Kinds" className="flex flex-wrap items-center gap-1">
          {Object.entries(KINDS).map(([s, k], n) => (
            <NavLink key={s} to={`/b/${brandId}/library/${s}`} className={tab}>
              {k.title}
              {counts[n].data && <span className="tabular-nums text-muted">{counts[n].data.length}</span>}
            </NavLink>
          ))}
        </nav>
        <span className="hidden flex-1 sm:block" />
        <input className={`${input} max-w-xs`} type="search" aria-label="Search" placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
        <label className="flex min-h-11 items-center gap-2 text-sm sm:min-h-0">
          <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
          Show archived
        </label>
      </div>
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
          Nothing matches "{search}". <button className={linkText} onClick={() => setSearch("")}>Clear search</button>
        </p>
      )}
      <ul className="grid grid-cols-2 gap-5 md:grid-cols-4 xl:grid-cols-5">
        {shown?.map((i) => (
          <li key={i.id} className="space-y-1 text-sm">
            {archived ? <Thumb id={cover(i)} name={i.name} faded /> : (
              <Link to={`/b/${brandId}/library/${slug}/${i.id}`} aria-label={i.name}>
                <Thumb id={cover(i)} name={i.name} />
              </Link>
            )}
            <div className="text-[length:var(--text-md)] font-semibold">{i.name}</div>
            <div className="flex items-center gap-2 text-muted">
              {i.brand_ids?.map((id) => {
                const b = brands?.find((x) => x.id === id);
                return b && <span key={id} title={b.name} className="size-2.5 rounded-full" style={{ background: b.colours?.[0] || "var(--accent)" }}><span className="sr-only">{b.name}</span></span>;
              })}
              v{i.version}
              {!archived && kind !== "prop" && i.sheet_status !== "approved" && <span className="rounded-sm bg-warning-soft px-2 py-0.5 text-xs text-warning">Needs a sheet</span>}
              {archived && <span className="rounded-sm bg-surface-2 px-2 py-0.5 text-xs">Archived</span>}
            </div>
            {archived && (
              <div className="flex gap-3">
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
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}

function Thumb({ id, name, faded }: { id?: number; name: string; faded?: boolean }) {
  const fade = faded ? " opacity-60" : "";
  return id ? (
    <img src={fileUrl(id)} alt={name} className={`aspect-square w-full rounded-md border border-border bg-surface-2 object-cover${fade}`} />
  ) : (
    <div className={`grid aspect-square w-full place-items-center rounded-md border border-border bg-surface-2 text-muted${fade}`}>No image</div>
  );
}

/** The picture on a card: the approved or latest sheet, else the source photo, else the first picture. */
const cover = (i: { sheet_file_id?: number | null; source_photo_file_id?: number | null; image_file_ids?: number[] }) => i.sheet_file_id ?? i.source_photo_file_id ?? i.image_file_ids?.[0];

function NewItem(props: { brandId: number; kind: "character" | "place" | "prop"; one: string; onDone: () => void; onClose: () => void }) {
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const create = useMutation({
    mutationFn: async () => {
      // A character's or place's picture is a source photo (the sheet is what videos use); a prop's picture is used as it is.
      const stored = file ? (await uploadFile(file)).id : null;
      const photo = props.kind !== "prop";
      const { data, error } = await api.POST("/library/{kind}", {
        params: { path: { kind: props.kind } },
        body: { name, notes: "", brand_ids: [props.brandId], image_file_ids: stored && !photo ? [stored] : [], source_photo_file_id: stored && photo ? stored : null, outfits: [] },
      });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => {
      setName("");
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
    <form onSubmit={submit} className={`${card} space-y-3`}>
      <label className="block text-sm">
        Name
        <input className={input} required value={name} onChange={(e) => setName(e.target.value)} />
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
