import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl, uploadFile } from "../api/upload";
import { btnPrimary, btnSecondary, card, errorText as errorClass, input, linkText, pageTitle } from "../ui";

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
      <ul className="grid grid-cols-3 gap-3 md:grid-cols-4 lg:grid-cols-6">
        {screens.data?.map((s) => (
          <li key={s.id} className="space-y-1 text-sm">
            <img src={fileUrl(s.file_id)} alt={s.name} className="aspect-[9/16] w-full rounded border border-border bg-surface-2 object-cover" />
            <div className="font-medium">{s.name}</div>
            {s.default_for.length > 0 && <div className="text-accent-text">★ Always used for: {s.default_for.join(", ")}</div>}
            {s.tags.length > 0 && <div className="text-muted">{s.tags.join(" · ")}</div>}
            <button
              className={linkText}
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

function AddScreen(props: { brandId: number; tagOptions: string[]; momentOptions: string[]; onCancel: () => void; onDone: () => void }) {
  const { brandId, onDone } = props;
  const [name, setName] = useState("");
  const [tags, setTags] = useState("");
  const [moments, setMoments] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const add = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose an image first.");
      const stored = await uploadFile(file);
      const { data, error } = await api.POST("/brands/{brand_id}/screens", {
        params: { path: { brand_id: brandId } },
        body: { name, file_id: stored.id, tags: slugs(tags), default_for: slugs(moments), product: "", variant: "" },
      });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => {
      setName("");
      setTags("");
      setMoments("");
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
            if (f && !name) setName(f.name.replace(/\.[^.]+$/, ""));
          }}
        />
      </label>
      <label className="block text-sm">
        Name
        <input className={box} required value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="block text-sm">
        What it shows (tags, separated by commas)
        <input className={box} list="screen-tags" value={tags} onChange={(e) => setTags(e.target.value)} />
        <span className="text-muted">e.g. trading, chart-up. Spaces become dashes.</span>
        <datalist id="screen-tags">{props.tagOptions.map((t) => <option key={t} value={t} />)}</datalist>
      </label>
      <label className="block text-sm">
        Use automatically for these moments (separated by commas)
        <input className={box} list="screen-moments" value={moments} onChange={(e) => setMoments(e.target.value)} />
        <span className="text-muted">e.g. buy-moment, win-moment. Pick an existing one so it is spelled the same way.</span>
        <datalist id="screen-moments">{props.momentOptions.map((t) => <option key={t} value={t} />)}</datalist>
      </label>
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
