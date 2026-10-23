import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, NavLink, useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl, uploadFile } from "../api/upload";
import { useMe } from "../auth/useMe";
import { useToast } from "../toast";
import { useBrands } from "../shell/useBrands";
import { btnPrimary, btnSecondary, card, errorText as errorClass, input, linkText, pageTitle } from "../ui";
import { KINDS, isKindSlug } from "./kinds";

const tab = ({ isActive }: { isActive: boolean }) =>
  `rounded-sm px-3 py-2 ${isActive ? "bg-accent-soft font-medium text-accent-text" : "text-muted"}`;

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
  const { data: me } = useMe();
  const queryClient = useQueryClient();
  const toast = useToast();
  const key = ["library", kind, brandId, archived];
  const items = useQuery({
    queryKey: key,
    queryFn: async () => {
      const { data } = await api.GET("/library/{kind}", { params: { path: { kind }, query: { brand_id: brandId, archived } } });
      if (!data) throw new Error("load");
      return data;
    },
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["library", kind] });
  const unarchive = useMutation({
    mutationFn: (item_id: number) => api.POST("/library/{kind}/{item_id}/unarchive", { params: { path: { kind, item_id } } }),
    onSuccess: (_, item_id) => {
      refresh();
      const name = items.data?.find((i) => i.id === item_id)?.name ?? "Item";
      toast(`${name} is back.`, async () => {
        await api.DELETE("/library/{kind}/{item_id}", { params: { path: { kind, item_id } } });
        refresh();
      });
    },
  });
  const purge = useMutation({
    mutationFn: (item_id: number) => api.DELETE("/library/{kind}/{item_id}/permanent", { params: { path: { kind, item_id } } }),
    onSuccess: refresh,
  });
  const shown = items.data?.filter((i) => i.name.toLowerCase().includes(search.trim().toLowerCase()));

  return (
    <main className="mx-auto max-w-5xl space-y-4 p-4 sm:p-6">
      <h1 className={pageTitle}>Library</h1>
      <div className="flex flex-wrap items-center gap-2">
        {Object.entries(KINDS).map(([s, k]) => (
          <NavLink key={s} to={`/b/${brandId}/library/${s}`} className={tab}>
            {k.title}
          </NavLink>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <input className={`${input} max-w-xs`} type="search" aria-label="Search" placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
          Show archived
        </label>
      </div>
      {!archived && <NewItem brandId={brandId} kind={kind} one={one} onDone={refresh} />}
      {items.isError && <p role="alert" className={errorClass}>Could not load the library. Try again.</p>}
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
      <ul className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {shown?.map((i) => (
          <li key={i.id} className="space-y-1 text-sm">
            {archived ? <Thumb id={i.image_file_ids?.[0]} name={i.name} faded /> : (
              <Link to={`/b/${brandId}/library/${slug}/${i.id}`}>
                <Thumb id={i.image_file_ids?.[0]} name={i.name} />
              </Link>
            )}
            <div className="text-[length:var(--text-md)] font-semibold">{i.name}</div>
            <div className="flex items-center gap-2 text-muted">
              {i.brand_ids?.map((id) => {
                const b = brands?.find((x) => x.id === id);
                return b && <span key={id} title={b.name} className="size-2.5 rounded-full" style={{ background: b.colours?.[0] || "var(--accent)" }}><span className="sr-only">{b.name}</span></span>;
              })}
              v{i.version}
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

function NewItem(props: { brandId: number; kind: "character" | "place" | "prop"; one: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const create = useMutation({
    mutationFn: async () => {
      const image_file_ids = file ? [(await uploadFile(file)).id] : [];
      const { data, error } = await api.POST("/library/{kind}", {
        params: { path: { kind: props.kind } },
        body: { name, notes: "", brand_ids: [props.brandId], image_file_ids, outfits: [] },
      });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => {
      setName("");
      setFile(null);
      setOpen(false);
      props.onDone();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  if (!open)
    return (
      <button className={btnPrimary} onClick={() => setOpen(true)}>
        New {props.one}
      </button>
    );
  return (
    <form onSubmit={submit} className={`${card} space-y-3`}>
      <label className="block text-sm">
        Name
        <input className={input} required value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="block text-sm">
        Image (optional)
        <input className={input} type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
      {create.isError && <p role="alert" className={errorClass}>{create.error.message}</p>}
      <div className="flex gap-2">
        <button className={btnPrimary} disabled={create.isPending}>
          Create {props.one}
        </button>
        <button type="button" className={btnSecondary} onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}
