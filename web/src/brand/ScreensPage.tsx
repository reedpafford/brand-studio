import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl, uploadFile } from "../api/upload";
import { Sheet } from "../projects/Sheet";
import { btnPrimary, btnSecondary, card, errorText as errorClass, input, linkText, pageTitle } from "../ui";

type Screen = components["schemas"]["ScreenOut"];
type Fields = { name: string; tags: string; moments: string; product: string; variant: string };

const slugs = (s: string) => s.split(",").map((x) => x.trim().toLowerCase().replace(/\s+/g, "-")).filter(Boolean);

/** The brand's real screens. Tags say what a screen shows; "moments" say when it is used automatically. */
export function ScreensPage() {
  const brand_id = Number(useParams().brandId);
  const queryClient = useQueryClient();
  const key = ["screens", brand_id];
  const screens = useQuery({
    queryKey: key,
    queryFn: async () => (await api.GET("/brands/{brand_id}/screens", { params: { path: { brand_id } } })).data ?? [],
  });
  const remove = useMutation({
    mutationFn: (screen_id: number) => api.DELETE("/brands/{brand_id}/screens/{screen_id}", { params: { path: { brand_id, screen_id } } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Screen | null>(null);
  const products = [...new Set(screens.data?.map((s) => s.product).filter(Boolean) ?? [])];
  const used = (field: "tags" | "default_for") => [...new Set(screens.data?.flatMap((s) => s[field]) ?? [])];
  const addButton = (
    <button className={btnPrimary} onClick={() => setAdding(true)}>
      Add screen
    </button>
  );

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className={pageTitle}>Brand screens{screens.data ? ` (${screens.data.length})` : ""}</h1>
        {!adding && screens.data && screens.data.length > 0 && addButton}
      </div>
      {adding && (
        <AddScreen
          brandId={brand_id}
          tagOptions={used("tags")}
          momentOptions={used("default_for")}
          productOptions={products}
          onCancel={() => setAdding(false)}
          onDone={() => {
            setAdding(false);
            queryClient.invalidateQueries({ queryKey: key });
          }}
        />
      )}
      {screens.data?.length === 0 && !adding && (
        <div className={`${card} space-y-3`}>
          <p className="text-[length:var(--text-xl)] font-semibold">No brand screens yet.</p>
          <p className="text-muted">Add real app screens so videos show them exactly.</p>
          {addButton}
        </div>
      )}
      {editing && (
        <EditScreen
          key={editing.id}
          brandId={brand_id}
          screen={editing}
          tagOptions={used("tags")}
          momentOptions={used("default_for")}
          productOptions={products}
          onClose={() => setEditing(null)}
          onDone={() => {
            setEditing(null);
            queryClient.invalidateQueries({ queryKey: key });
          }}
        />
      )}
      <ul className="grid grid-cols-3 gap-3 md:grid-cols-4 lg:grid-cols-6">
        {screens.data?.map((s) => (
          <li key={s.id} className="space-y-1 text-sm">
            <img src={fileUrl(s.file_id)} alt={s.name} className="aspect-[9/16] w-full rounded border border-border bg-surface-2 object-cover" />
            <div className="font-medium">{s.name}</div>
            {s.default_for.length > 0 && <div className="text-accent-text">★ Always used for: {s.default_for.join(", ")}</div>}
            {s.product && <div className="text-muted">{s.product}{s.variant && ` · ${s.variant}`}</div>}
            {s.tags.length > 0 && <div className="text-muted">{s.tags.join(" · ")}</div>}
            <button className={`${linkText} mr-3 min-h-11 sm:min-h-0`} aria-label={`Edit ${s.name}`} onClick={() => setEditing(s)}>
              Edit
            </button>
            <button
              className={`${linkText} min-h-11 sm:min-h-0`}
              aria-label={`Delete ${s.name}`}
              onClick={() => window.confirm(`Delete the screen "${s.name}"?`) && remove.mutate(s.id)}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}

function AddScreen(props: { brandId: number; tagOptions: string[]; momentOptions: string[]; productOptions: string[]; onCancel: () => void; onDone: () => void }) {
  const { brandId, onDone } = props;
  const [values, setValues] = useState<Fields>({ name: "", tags: "", moments: "", product: "", variant: "" });
  const [file, setFile] = useState<File | null>(null);
  const add = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose an image first.");
      const stored = await uploadFile(file);
      const { data, error } = await api.POST("/brands/{brand_id}/screens", {
        params: { path: { brand_id: brandId } },
        body: { name: values.name, file_id: stored.id, tags: slugs(values.tags), default_for: slugs(values.moments), product: values.product.trim(), variant: values.variant.trim() },
      });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => {
      setValues({ name: "", tags: "", moments: "", product: "", variant: "" });
      setFile(null);
      onDone();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };
  const box = input;
  return (
    <form onSubmit={submit} className={`${card} space-y-3`}>
      <h2 className="text-[length:var(--text-md)] font-semibold">Add a screen</h2>
      <label className="block text-sm">
        Screen image
        <input
          type="file"
          accept="image/*"
          className={box}
          onChange={(e) => {
            const f = e.target.files?.[0] ?? null;
            setFile(f);
            if (f && !values.name) setValues({ ...values, name: f.name.replace(/\.[^.]+$/, "") });
          }}
        />
      </label>
      <ScreenFields values={values} onChange={setValues} tagOptions={props.tagOptions} momentOptions={props.momentOptions} productOptions={props.productOptions} />
      {add.isError && (
        <p role="alert" className={errorClass}>
          {add.error.message}
        </p>
      )}
      <div className="flex gap-2">
        <button className={btnPrimary} disabled={add.isPending}>
          Save screen
        </button>
        <button type="button" className={btnSecondary} onClick={props.onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function ScreenFields(props: { values: Fields; onChange: (v: Fields) => void; tagOptions: string[]; momentOptions: string[]; productOptions: string[] }) {
  const { values, onChange, tagOptions, momentOptions, productOptions } = props;
  return (
    <>
      <label className="block text-sm">
        Name
        <input className={input} required value={values.name} onChange={(e) => onChange({ ...values, name: e.target.value })} />
      </label>
      <label className="block text-sm">
        What it shows (tags, separated by commas)
        <input className={input} list="screen-tags" value={values.tags} onChange={(e) => onChange({ ...values, tags: e.target.value })} />
        <span className="text-muted">e.g. trading, chart-up. Spaces become dashes.</span>
        <datalist id="screen-tags">{tagOptions.map((t) => <option key={t} value={t} />)}</datalist>
      </label>
      <label className="block text-sm">
        Use automatically for these moments (separated by commas)
        <input className={input} list="screen-moments" value={values.moments} onChange={(e) => onChange({ ...values, moments: e.target.value })} />
        <span className="text-muted">e.g. buy-moment, win-moment. Pick an existing one so it is spelled the same way.</span>
        <datalist id="screen-moments">{momentOptions.map((t) => <option key={t} value={t} />)}</datalist>
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          Product (optional)
          <input className={input} list="screen-products" placeholder="e.g. bag" value={values.product} onChange={(e) => onChange({ ...values, product: e.target.value })} />
          <datalist id="screen-products">{productOptions.map((t) => <option key={t} value={t} />)}</datalist>
        </label>
        <label className="block text-sm">
          Variant (optional)
          <input className={input} placeholder="e.g. Chicken" value={values.variant} onChange={(e) => onChange({ ...values, variant: e.target.value })} />
        </label>
      </div>
      <p className="text-sm text-muted">Product and variant drive the brief's picker: a bag that comes in Chicken or Peanut butter, say.</p>
    </>
  );
}

/** Edit a screen's words in a side sheet (the picture stays the same). */
function EditScreen(props: { brandId: number; screen: Screen; tagOptions: string[]; momentOptions: string[]; productOptions: string[]; onClose: () => void; onDone: () => void }) {
  const { screen: sc } = props;
  const [values, setValues] = useState<Fields>({ name: sc.name, tags: sc.tags.join(", "), moments: sc.default_for.join(", "), product: sc.product, variant: sc.variant });
  const save = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.PATCH("/brands/{brand_id}/screens/{screen_id}", {
        params: { path: { brand_id: props.brandId, screen_id: sc.id } },
        body: { name: values.name, tags: slugs(values.tags), default_for: slugs(values.moments), product: values.product.trim(), variant: values.variant.trim() },
      });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: props.onDone,
  });
  return (
    <Sheet title={`Edit ${sc.name}`} closeLabel="Cancel" onClose={props.onClose}>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <img src={fileUrl(sc.file_id)} alt="" className="max-h-48 rounded border border-border bg-surface-2 object-contain" />
        <ScreenFields values={values} onChange={setValues} tagOptions={props.tagOptions} momentOptions={props.momentOptions} productOptions={props.productOptions} />
        {save.isError && <p role="alert" className={errorClass}>{save.error.message}</p>}
        <button className={`${btnPrimary} min-h-11 sm:min-h-9`} disabled={save.isPending}>
          Save changes
        </button>
      </form>
    </Sheet>
  );
}
